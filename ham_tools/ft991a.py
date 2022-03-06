"""
Simple tool for reading/writing memory and menu settings from a Yaesu FT-991a over the
CAT serial protocol.
"""

from csv import DictReader, DictWriter
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

from serial import Serial

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 4800

# How many memory channels are there
#
# 001 - 099 are standard memory channels
# 100 - 117 are L/U channels for bounded scanning
MEMORY_CHANNELS = 117

# Regex for parsing the answer of MT commands
MT_RE = (
    r'MT\d{3}(?P<freq>\d{9})(?P<clar_dir>[\-\+])(?P<clar_offset>\d{4})(?P<clar_rx>\d)'
    r'(?P<clar_tx>\d)(?P<mode>\w)(?P<vfo_memory>\d)(?P<sql_mode>\d)00(?P<shift>\d)0'
    r'(?P<tag>.{12});'
)


@dataclass
class Memory:
    pass


def main():
    args = parse_args()

    port = Serial(args.port, args.baud)

    if args.thing == "memory":
        if args.action == "read":
            read_memory(port)


def parse_args() -> Namespace:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port", "-p", help=f"Serial port to connect to, default: {DEFAULT_PORT}", default=DEFAULT_PORT
    )
    parser.add_argument(
        "--baud", "-b", help=f"Serial baud rate, default: {DEFAULT_BAUD}", default=DEFAULT_BAUD
    )

    # TODO: make these subcommands instead of verb, noun
    # TODO: filename flag
    parser.add_argument("action", choices=("read", "write"))
    parser.add_argument("thing", choices=("memory", "menu"))
    return parser.parse_args()


def read_memory(port: Serial):
    """
    Read all memory from radio and dump to a CSV file.

    Uses the MT command, which gives us the tag (name) of the channel
    """
    # TODO: read CTCSS freq or DCS code

    # Fetch memory channels from radio
    for chan in range(1, MEMORY_CHANNELS+1):
        cmd = f"MT{chan:03d};"
        port.write(cmd.encode())
        result = port.read_until(b';')
        if result != b"?;":
            print(cmd)
            print(result.decode())

        # parse each one

    # Dump to CSV file


if __name__ == "__main__":
    main()
