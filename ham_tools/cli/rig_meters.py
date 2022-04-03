"""
Display meters from rigctl

Assumes rigctld is listening on localhost
"""

import os
import socket
import sys
import time
from dataclasses import dataclass

from colorama import Cursor, Fore, Style
from colorama.ansi import clear_screen as ansi_clear_screen

RIGCTLD_PORT = 4532

# Note: It usually takes 0.1 - 0.27 seconds to read four meters
INTERVAL_S = 0.5

AVERAGE_SAMPLES = 4


@dataclass
class Meter:
    name: str
    min_val: float
    max_val: float
    unit: str


# available meters can be found with the command:
# rigctl -r localhost get_level \?
METERS = {
    "STRENGTH": Meter("STRENGTH", -54, 60, "dB"),
    "ALC": Meter("ALC", 0.05, 0.6, ""),
    "SWR": Meter("SWR", 1, 3, ""),
    "RFPOWER_METER_WATTS": Meter("RFPOWER_METER_WATTS", 0, 100, "W"),
}


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", RIGCTLD_PORT))

    samples: dict[str, list[float]] = {name: [] for name in METERS.keys()}
    while True:
        results = []
        start = time.time()
        for meter in METERS.values():
            sock.send(f"\\get_level {meter.name}\n".encode())
            raw_val = float(sock.recv(32).strip())

            # Average the value over the last samples
            samples[meter.name].append(raw_val)
            if len(samples[meter.name]) > AVERAGE_SAMPLES:
                samples[meter.name].pop(0)
            avg_val = sum(samples[meter.name]) / len(samples[meter.name])

            # Re-scale the value from original range to 0 to 100
            val = int((avg_val - meter.min_val) / (meter.max_val - meter.min_val) * 100)

            results.append((meter, avg_val, val))
        end = time.time()

        print_meters(results)

        to_sleep = INTERVAL_S - (end - start)
        if to_sleep < 0:
            to_sleep = 0
        time.sleep(to_sleep)


def print_meters(results: list[tuple[Meter, float, int]]) -> None:
    clear_screen()
    print(Cursor.POS())  # move cursor to 0,0

    for meter, raw_val, val in results:
        if val < 0:
            val = 0
        elif val > 100:
            val = 100
        val = int(val / 2)
        print(meter.name)

        meter_str = "["
        meter_str += "#" * val
        meter_str += " " * (50 - val)
        meter_str += "] "

        # Make the meter value red if it's over the max val, e.g. a SWR too high
        if raw_val >= meter.max_val:
            meter_str += Fore.RED

        meter_str += f"{raw_val:0.2f}"
        meter_str += Style.RESET_ALL
        meter_str += f" {meter.unit}"
        print(meter_str)


def clear_screen() -> None:
    """
    Clear the screen in a platform-independent way, since colorama doesn't support win32
    for this.
    """
    if sys.platform == "win32":
        os.system("cls")
    else:
        print(ansi_clear_screen())


if __name__ == "__main__":
    main()
