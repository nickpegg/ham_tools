"""
Simple tool for reading/writing memory and menu settings from a Yaesu FT-991a over the
CAT serial protocol.
"""

import re
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
    r'MT\d{3}'
    r'(?P<freq>\d{9})'          # frequency in Hz
    r'(?P<clar_dir>[\-\+])'     # Clarifier direction, + or -
    r'(?P<clar_offset>\d{4})'   # Clarifier offset, in Hz. 0000 - 9999
    r'(?P<clar_rx>\d)'          # Apply clarifier to receive, bool
    r'(?P<clar_tx>\d)'          # Apply clarifier to transmit, bool
    r'(?P<mode>\w)'             # Mode: 1=LSB 2=USB 3=CW 4=FM 5=AM 6=RTTY-LSB 7=CW-R
                                #       8=DATA-LSB 9=RTTY-USB A=DATA-FM B=FM-N C=DATA-USB
                                #       D=AM-N E=C4FM
    r'(?P<vfo_memory>\d)'       # 0=VFO 1=Memory - ???
    r'(?P<sql_mode>\d)'         # Squelch mode: 0=off 1=CTCSS TX/RX, 2=CTCSS TX
                                #               3=DCS TX/RX, 4=DCS TX
    r'00(?P<shift>\d)0'         # Repeater shift, 0=simplex, 1=+, 2=-
    r'(?P<tag>.{12});'          # Tag - the text description, up to 12 chars
)


@dataclass
class Memory:
    # TODO: Translate text from regex into typed data
    @classmethod
    def from_mt(cls, line: bytes) -> "Memory":
        match = re.match(MT_RE, line.decode())
        if not match:
            raise ValueError(f"Unable to parse line: {result.decode()}")

        # TODO: return a real Memory object
        print(match.groups())
        return cls()



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
    # TODO: read CTCSS freq or DCS code - the MT command includes the mode but not the
    # value, so we might have to tune to that channel and read it from CAT

    # Fetch memory channels from radio
    for chan in range(1, MEMORY_CHANNELS+1):
        cmd = f"MT{chan:03d};"
        port.write(cmd.encode())
        result = port.read_until(b';')
        if result == b"?;":
            continue

        print(cmd)
        print(result.decode())

        # parse each one
        Memory.from_mt(result)


    # Dump to CSV file


if __name__ == "__main__":
    main()
