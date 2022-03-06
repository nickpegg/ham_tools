"""
Simple tool for reading/writing memory and menu settings from a Yaesu FT-991a over the
CAT serial protocol.
"""

import re
from csv import DictReader, DictWriter
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

from serial import Serial
from serial.tools.list_ports import grep as grep_ports
from serial.tools.list_ports_common import ListPortInfo

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 4800

# How many memory channels are there
#
# 001 - 099 are standard memory channels
# 100 - 117 are L/U channels for bounded scanning
MEMORY_CHANNELS = 117

# Regex for parsing the answer of MT commands
MT_RE = (
    r"MT\d{3}"
    # frequencxy in Hz
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
    r"(?P<vfo_memory>\d)"
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
    # TODO: Translate text from regex into typed data
    @classmethod
    def from_mt(cls, line: bytes) -> "Memory":
        match = re.match(MT_RE, line.decode())
        if not match:
            raise ValueError(f"Unable to parse line: {line.decode()}")

        # TODO: return a real Memory object
        print(match.groups())
        return cls()


def main():
    args = parse_args()

    try:
        if args.action == "discover":
            print(discover().device)
        else:
            with Serial(args.port, baudrate=args.baud, timeout=0.25) as port:
                if args.action == "read":
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
    parser.add_argument("action", choices=("read", "write", "discover"))
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


def read_memory(port: Serial) -> None:
    """
    Read all memory from radio and dump to a CSV file.

    Uses the MT command, which gives us the tag (name) of the channel
    """
    # TODO: read CTCSS freq or DCS code - the MT command includes the mode but not the
    # value, so we might have to tune to that channel and read it from CAT

    # Fetch memory channels from radio
    for chan in range(1, MEMORY_CHANNELS + 1):
        cmd = f"MT{chan:03d};"
        port.write(cmd.encode())
        result = port.read_until(b";")
        if result == b"?;":
            continue

        print(cmd)
        print(result.decode())

        # parse each one
        Memory.from_mt(result)

    # Dump to CSV file


if __name__ == "__main__":
    main()
