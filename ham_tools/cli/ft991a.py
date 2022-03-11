"""
Simple tool for reading/writing memory and menu settings from a Yaesu FT-991a over the
CAT serial protocol.
"""

from argparse import ArgumentParser, Namespace
from pathlib import Path

from serial import Serial, SerialException

from ham_tools.cli.common import add_common_args
from ham_tools.constants import DEFAULT_BAUD, DEFAULT_MEMORIES_FILE, DEFAULT_PORT
from ham_tools.ft991a import FT991A, discover


def main() -> None:
    args = parse_args()

    try:
        if args.action == "discover":
            print(discover().device)
        else:
            try:
                port = Serial(
                    args.port, baudrate=args.baud, timeout=0.25, exclusive=True
                )
            except SerialException as e:
                raise RuntimeError(
                    f"Could not open {args.port}. Is the radio plugged in and powered "
                    "on?"
                )

            with port:
                radio = FT991A(port)
                if args.action == "read":
                    if args.thing == "memory":
                        radio.read_memories(Path(args.m))
                elif args.action == "write":
                    if args.thing == "memory":
                        radio.write_memories(Path(args.m))
                # TODO: read/write settings
    except Exception as e:
        if not args.v:
            print(e)
        else:
            raise


def parse_args() -> Namespace:
    parser = ArgumentParser(description=__doc__)
    add_common_args(parser)

    parser.add_argument(
        "-m",
        default=DEFAULT_MEMORIES_FILE,
        metavar="MEMORIES_FILENAME",
        help=(
            f"Filename to read/write channel memories from/to, default: "
            f"{DEFAULT_MEMORIES_FILE}"
        ),
    )

    # TODO: make these subcommands instead of verb, noun
    parser.add_argument("action", choices=("read", "write", "discover", "shell"))
    parser.add_argument("thing", choices=("memory", "menu"), nargs="?")
    return parser.parse_args()


if __name__ == "__main__":
    main()
