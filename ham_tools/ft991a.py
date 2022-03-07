"""
Simple tool for reading/writing memory and menu settings from a Yaesu FT-991a over the
CAT serial protocol.
"""

import re
import sys
from argparse import ArgumentParser, Namespace
from csv import DictReader, DictWriter
from dataclasses import dataclass
from typing import Optional

from serial import Serial, SerialException
from serial.tools.list_ports import grep as grep_ports
from serial.tools.list_ports_common import ListPortInfo

from .enums import Mode, RepeaterShift, SquelchMode, CTCSS_TONES, DCS_CODES, ToneSquelch

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 38400

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

    ctcss_dhz: int = 0  # in decihertz
    dcs_code: int = 0

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


def main() -> None:
    args = parse_args()

    try:
        if args.action == "discover":
            print(discover().device)
        else:
            try:
                port = Serial(args.port, baudrate=args.baud, timeout=0.25, exclusive=True)
            except SerialException as e:
                raise RuntimeError(
                    f"Could not open {args.port}. Is the radio plugged in and powered "
                    "on?"
                )

            with port:
                if args.action == "shell":
                    repl(port)
                elif args.action == "read":
                    if args.thing == "memory":
                        read_memories(port)
    except Exception as e:
        if not args.v:
            print(e)
        else:
            raise


def parse_args() -> Namespace:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "-v",
        help="Verbose mode",
        action="store_true",
    )
    parser.add_argument(
        "-p",
        "--port",
        help=f"Serial port to connect to, default: {DEFAULT_PORT}",
        default=DEFAULT_PORT,
    )
    parser.add_argument(
        "-b",
        "--baud",
        help=f"Serial baud rate, default: {DEFAULT_BAUD}",
        default=DEFAULT_BAUD,
    )

    # TODO: make these subcommands instead of verb, noun
    # TODO: filename flag
    parser.add_argument("action", choices=("read", "write", "discover", "shell"))
    parser.add_argument("thing", choices=("memory", "menu"), nargs="?")
    return parser.parse_args()


def discover() -> ListPortInfo:
    """
    Find an FT-991a on one of the serial ports
    """
    ports = list(grep_ports("CP2105.+Enhanced"))
    if len(ports) == 0:
        raise RuntimeError("Unable to discover FT-991a serial port. Is it plugged in?")
    return ports[0]


def repl(port: Serial) -> None:
    """
    Enter a REPL shell with the radio
    """
    print("Press Enter or Ctrl-D to quit")
    while True:
        cmd = input(">>> ").rstrip()
        if cmd == "":
            break

        if not cmd.endswith(";"):
            cmd += ";"
        port.write(cmd.encode())
        print(port.read_until(b";").decode())


def read_memories(port: Serial) -> None:
    """
    Read all memory from radio and dump to a CSV file.

    Uses the MT command, which gives us the tag (name) of the channel
    """
    # TODO: read CTCSS freq or DCS code - the MT command includes the mode but not the
    # value, so we might have to tune to that channel and read it from CAT

    memories = []

    # Fetch memory channels from radio
    for chan in range(1, MEMORY_CHANNELS + 1):
        mem = read_memory(port, chan)
        if mem is None:
            continue
        print(mem)
        memories.append(mem)

    # TODO: Dump to CSV file


def read_memory(port: Serial, channel: int) -> Optional[Memory]:
    cmd = f"MT{channel:03d};"
    port.write(cmd.encode())
    result = port.read_until(b";")
    if result == b"?;":
        return None

    mem = Memory.from_mt(channel, result)
    mem.ctcss_dhz = read_tone(port, channel, ToneSquelch.CTCSS)
    mem.dcs_code = read_tone(port, channel, ToneSquelch.DCS)

    return Memory.from_mt(channel, result)


def read_tone(port: Serial, channel: int, tone_type: ToneSquelch) -> int:
    """
    Reads a CTCSS or DCS tone value from the particular channel

    Returns:
        If CTCSS, the frequency in decihertz. If DCS, the code value
    """
    port.write(f"MC{channel:03d};".encode())
    port.read_until(b";")
    port.write(f"CN0{tone_type.value};".encode())
    result = port.read_until(b";")

    num = int(result[4:7])
    if tone_type == ToneSquelch.CTCSS:
        return CTCSS_TONES[num]
    else:
        return DCS_CODES[num]


def write_memory(port: Serial, memory: Memory) -> None:
    # TODO: write CTCSS/DCS
    cmd = memory.to_mt()
    port.write(cmd)

    result = port.read_until(b";")
    if result == b"?;":
        raise RuntimeError(f"Radio did not like the cmd we sent: {cmd.decode()}")

def write_tone(port: Serial, channel: int, tone_type: ToneSquelch, tone: int) -> None:
    # Convert the tone to the numerical value that the radio wants
    if tone_type == ToneSquelch.CTCSS:
        mapping = {v: k for k, v in CTCSS_TONES.items()}
        if tone not in mapping:
            raise RuntimeError(f"Not a valid CTCSS frequency in decihertz: {tone}")
        num = mapping[tone]
    else:
        mapping = {v: k for k, v in DCS_CODES.items()}
        if tone not in mapping:
            raise RuntimeError(f"Not a valid DCS code: {tone}")
        num = mapping[tone]

    port.write(f"MC{channel:03d};".encode())
    port.read_until(b";")
    port.write(f"CN0{tone_type.value}{num:03d};".encode())
    result = port.read_until(b";")


if __name__ == "__main__":
    main()
