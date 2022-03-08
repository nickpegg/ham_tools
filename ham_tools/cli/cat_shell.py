"""
CAT Shell
"""

from argparse import ArgumentParser, Namespace

from serial import Serial, SerialException

from ham_tools.cli.common import add_common_args
from ham_tools.constants import DEFAULT_BAUD, DEFAULT_PORT


def main() -> None:
    args = parse_args()
    try:
        try:
            port = Serial(args.port, baudrate=args.baud, timeout=0.25, exclusive=True)
        except SerialException as e:
            raise RuntimeError(
                f"Could not open {args.port}. Is the radio plugged in and powered " "on?"
            )

        with port:
            repl(port)
    except Exception as e:
        if not args.v:
            print(e)
        else:
            raise


def parse_args() -> Namespace:
    parser = ArgumentParser(description=__doc__)
    add_common_args(parser)
    return parser.parse_args()


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


if __name__ == "__main__":
    main()
