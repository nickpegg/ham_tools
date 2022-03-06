"""
Simple tool for reading/writing memory and menu settings from a Yaesu FT-991a over the
CAT serial protocol.
"""

import sys
import re

from csv import DictReader, DictWriter
from enum import Enum
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

from serial import Serial, SerialException
from serial.tools.list_ports import grep as grep_ports
from serial.tools.list_ports_common import ListPortInfo

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


class Mode(Enum):
    AM_N = 13
    LSB = 1
    USB = 2
    CW = 3
    CW_R = 7

    RTTY_LSB = 6
    RTTY_USB = 9
    DATA_LSB = 8
    DATA_USB = 12
    DATA_FM = 10

    FM = 4
    FM_N = 11
    C4FM = 14


class SquelchMode(Enum):
    OFF = 0
    CTCSS_RX_TX = 1
    CTCSS_TX = 2
    DCS_RX_TX = 3
    DCS_TX = 4


class RepeaterShift(Enum):
    SIMPLEX = 0
    PLUS = 1
    MINUS = 2


@dataclass
class Memory:
    channel: int
    frequency_hz: int
    clarifier_direction: str
    clarifier_offset_hz: int
    clarifier_rx: bool
    clarifier_tx: bool
    mode: Mode
    squelch_mode: SquelchMode
    repeater_shift: RepeaterShift
    tag: str

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
                port = Serial(args.port, baudrate=args.baud, timeout=0.25)
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
                        read_memory(port)
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


def read_memory(port: Serial) -> None:
    """
    Read all memory from radio and dump to a CSV file.

    Uses the MT command, which gives us the tag (name) of the channel
    """
    # TODO: read CTCSS freq or DCS code - the MT command includes the mode but not the
    # value, so we might have to tune to that channel and read it from CAT

    memories = []

    # Fetch memory channels from radio
    for chan in range(1, MEMORY_CHANNELS + 1):
        cmd = f"MT{chan:03d};"
        port.write(cmd.encode())
        result = port.read_until(b";")
        if result == b"?;":
            continue

        print(result)
        mem = Memory.from_mt(chan, result)
        memories.append(mem)
        print(mem)

    # Dump to CSV file


if __name__ == "__main__":
    main()
