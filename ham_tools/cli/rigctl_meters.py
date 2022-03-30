"""
Display meters from rigctl

Assumes rigctld is listening on localhost
"""

import socket
import time

RIGCTLD_PORT = 4532
INTERVAL_S = 0.5

# available meters can be found with the command:
# rigctl -r localhost get_level \?
METERS = [
    # name, min value, max value, unit
    ("STRENGTH", -54, 60, "dB"),
    ("ALC", 0.05, 0.6, ""),
    ("SWR", 1, 5, ""),
    ("RFPOWER_METER_WATTS", 0, 100, "W"),
]


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", RIGCTLD_PORT))

    while True:
        results = []
        for meter, min_val, max_val, unit in METERS:
            sock.send(f"\\get_level {meter}\n".encode())
            raw_val = float(sock.recvmsg(32)[0].strip())

            # Re-scale the value from original range to 0 to 100
            val = int((raw_val - min_val) / (max_val - min_val) * 100)
            results.append((meter, raw_val, val, unit))

        print_meters(results)
        time.sleep(INTERVAL_S)


def print_meters(meters: list[tuple[str, float, int, str]]) -> None:
    print("\033[2J")  # clear screen
    print("\033[0;0H")  # move cursor to 0,0

    for name, raw_val, val, unit in meters:
        if val < 0:
            val = 0
        elif val > 100:
            val = 100
        val = int(val / 2)
        print(name)
        print("[" + "#" * val + " " * (50 - val) + f"] {raw_val} {unit}")


if __name__ == "__main__":
    main()
