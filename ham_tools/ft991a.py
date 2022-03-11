import logging
import re
import sys
from csv import DictReader, DictWriter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

from serial import Serial, SerialException
from serial.tools.list_ports import grep as grep_ports
from serial.tools.list_ports_common import ListPortInfo
from tqdm import tqdm

from .enums import CTCSS_TONES, DCS_CODES, Mode, RepeaterShift, SquelchMode, ToneSquelch

logger = logging.getLogger("ft991a")

# How many memory channels are there
#
# 001 - 099 are standard memory channels
# 100 - 117 are L/U channels for bounded scanning
MEMORY_CHANNELS = 117

# Regex for parsing the answer of MT commands
MT_RE = (
    r"MT\d{3}"
    # frequency in Hz
    r"(?P<freq>\d{9})"
    # Clarifier direction, + or -
    r"(?P<clar_dir>[\-\+])"
    # Clarifier offset, in Hz. 0000 - 9999
    r"(?P<clar_offset>\d{4})"
    # Apply clarifier to receive, bool
    r"(?P<clar_rx>\d)"
    # Apply clarifier to transmit, bool
    r"(?P<clar_tx>\d)"
    # Mode: 1=LSB 2=USB 3=CW 4=FM 5=AM 6=RTTY-LSB 7=CW-R
    #       8=DATA-LSB 9=RTTY-USB A=DATA-FM B=FM-N C=DATA-USB
    #       D=AM-N E=C4FM
    r"(?P<mode>\w)"
    # 0=VFO 1=Memory - ???
    # r"(?P<vfo_memory>\d)"
    r"\d"
    # Squelch mode: 0=off 1=CTCSS TX/RX, 2=CTCSS TX
    #               3=DCS TX/RX, 4=DCS TX
    r"(?P<sql_mode>\d)"
    # Repeater shift, 0=simplex, 1=+, 2=-
    r"00(?P<shift>\d)0"
    # Tag - the text description, up to 12 chars
    r"(?P<tag>.{12});"
)

# Order that the Memory fields will be written in each CSV row
CSV_FIELDS = (
    "channel",
    "tag",
    "frequency_hz",
    "mode",
    "squelch_mode",
    "ctcss_dhz",
    "dcs_code",
    "repeater_shift",
    "clarifier_direction",
    "clarifier_offset_hz",
    "clarifier_rx",
    "clarifier_tx",
)


@dataclass
class Memory:
    channel: int
    frequency_hz: int
    mode: Mode

    clarifier_direction: str = "+"
    clarifier_offset_hz: int = 0
    clarifier_rx: bool = False
    clarifier_tx: bool = False
    squelch_mode: SquelchMode = SquelchMode.OFF
    repeater_shift: RepeaterShift = RepeaterShift.SIMPLEX
    tag: str = ""

    ctcss_dhz: Optional[int] = None  # in decihertz
    dcs_code: Optional[int] = None

    @classmethod
    def from_mt(cls, channel: int, line: bytes) -> "Memory":
        """
        Parse from a MT answer
        """
        match = re.match(MT_RE, line.decode())
        if not match:
            raise ValueError(f"Unable to parse line: {line.decode()}")

        return cls(
            channel=channel,
            frequency_hz=int(match.group("freq")),
            clarifier_direction=match.group("clar_dir"),
            clarifier_offset_hz=int(match.group("clar_offset")),
            clarifier_rx=bool(int(match.group("clar_rx"))),
            clarifier_tx=bool(int(match.group("clar_tx"))),
            mode=Mode(int(match.group("mode"), base=16)),
            squelch_mode=SquelchMode(int(match.group("sql_mode"))),
            repeater_shift=RepeaterShift(int(match.group("shift"))),
            tag=match.group("tag").strip(),
        )

    def to_mt(self) -> bytes:
        """
        Turn into an MT command we can send to the serial port
        """
        # TODO: write a test for this
        buf = f"MT{self.channel:03d}"
        buf += f"{self.frequency_hz:09d}"
        buf += self.clarifier_direction
        buf += f"{self.clarifier_offset_hz:04d}"
        buf += str(int(self.clarifier_rx))
        buf += str(int(self.clarifier_tx))
        buf += f"{self.mode.value:x}".upper()
        buf += "0"
        buf += str(self.squelch_mode.value)
        buf += "00"
        buf += str(self.repeater_shift.value)
        buf += "0"
        buf += self.tag[:12].ljust(12)
        buf += ";"

        return buf.encode()


def discover() -> ListPortInfo:
    """
    Find an FT-991a on one of the serial ports
    """
    ports = list(grep_ports("CP2105.+Enhanced"))
    if len(ports) == 0:
        raise RuntimeError("Unable to discover FT-991a serial port. Is it plugged in?")
    return ports[0]


@dataclass
class FT991A:
    port: Serial

    def send_cmd(self, cmd: bytes) -> bytes:
        """
        Send a command to the serial port and return the response
        """
        logger.debug(f"Sending to radio: {cmd!r}")
        self.port.write(cmd)
        result = bytes(self.port.read_until(b";"))
        logger.debug(f"Got from radio: {result!r}")
        return result

    def read_memories(self, csv_path: Path) -> None:
        """
        Read all memory from radio and dump to a CSV file.

        Uses the MT command, which gives us the tag (name) of the channel
        """
        memories = []

        # Fetch memory channels from radio
        for chan in tqdm(range(1, MEMORY_CHANNELS + 1)):
            mem = self.read_memory(chan)
            if mem is None:
                continue
            memories.append(mem)

        # Dump to CSV
        with csv_path.open("w") as csv_file:
            writer = DictWriter(csv_file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for memory in memories:
                d = asdict(memory)

                # massage the data a bit
                for enum_key in ("mode", "squelch_mode", "repeater_shift"):
                    d[enum_key] = d[enum_key].name

                writer.writerow(d)

    def read_memory(self, channel: int) -> Optional[Memory]:
        cmd = f"MT{channel:03d};"
        result = self.send_cmd(cmd.encode())
        if result == b"?;":
            return None

        mem = Memory.from_mt(channel, result)
        mem.ctcss_dhz, mem.dcs_code = self.read_tones(channel)

        return mem

    def read_tones(self, channel: int) -> Tuple[int, int]:
        """
        Reads a CTCSS or DCS tone value from the particular channel

        Returns:
            A tuple of the CTCSS tone and the DCS code
        """
        self.send_cmd(f"MC{channel:03d};".encode())

        results = []
        for tone_type in (ToneSquelch.CTCSS, ToneSquelch.DCS):
            result = self.send_cmd(f"CN0{tone_type.value};".encode())

            num = int(result[4:7])
            if tone_type == ToneSquelch.CTCSS:
                results.append(CTCSS_TONES[num])
            else:
                results.append(DCS_CODES[num])

        return (results[0], results[1])

    def write_memory(self, memory: Memory) -> None:
        cmd = memory.to_mt()
        result = self.send_cmd(cmd)
        if result == b"?;":
            raise RuntimeError(f"Radio did not like the cmd we sent: {cmd.decode()}")

        self.write_tones(memory)

    def write_tones(self, memory: Memory) -> None:
        if memory.ctcss_dhz is None and memory.dcs_code is None:
            logger.debug("No tones to write")
            return

        logger.debug(f"Writing CTCSS {memory.ctcss_dhz} DCS {memory.dcs_code}")
        self.send_cmd(f"MC{memory.channel:03d};".encode())
        if memory.ctcss_dhz is not None:
            mapping = {v: k for k, v in CTCSS_TONES.items()}
            if memory.ctcss_dhz not in mapping:
                raise RuntimeError(
                    f"Not a valid CTCSS frequency in decihertz: {memory.ctcss_dhz}"
                )
            num = mapping[memory.ctcss_dhz]
            self.send_cmd(f"CN0{ToneSquelch.CTCSS.value}{num:03d};".encode())
        if memory.dcs_code is not None:
            mapping = {v: k for k, v in DCS_CODES.items()}
            if memory.dcs_code not in mapping:
                raise RuntimeError(f"Not a valid DCS code: {memory.dcs_code}")
            num = mapping[memory.dcs_code]
            self.send_cmd(f"CN0{ToneSquelch.DCS.value}{num:03d};".encode())
