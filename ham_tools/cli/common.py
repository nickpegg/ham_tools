from argparse import ArgumentParser, Namespace

from ham_tools.constants import DEFAULT_BAUD, DEFAULT_PORT


def add_common_args(parser: ArgumentParser) -> None:
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
