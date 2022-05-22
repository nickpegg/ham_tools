"""
Display meters from rigctl

Assumes rigctld is listening on localhost
"""

import os
import shutil
import socket
import sys
import time
from dataclasses import dataclass

from colorama import Cursor, Fore, Style
from colorama.ansi import clear_screen as ansi_clear_screen

RIGCTLD_PORT = 4532

# Note: It usually takes 0.1 - 0.27 seconds to read four meters
INTERVAL_S = 0.5

# Over how many seconds to calculate the max value
MAX_HOLD_TIME = 2.0

# How many samples to hold on to for calculating the max over the last 1 second
MAX_SAMPLES = int(MAX_HOLD_TIME / INTERVAL_S)

# Width of the meter in characters
METER_WIDTH = 50


@dataclass
class Meter:
    name: str
    min_val: float
    max_val: float
    unit: str

    def scale_value(self, value: float) -> int:
        """
        Scale a value from its original range, as defined by the Meter object, to [0, 100]
        """
        scaled = (value - self.min_val) / (self.max_val - self.min_val) * 100
        return int(scaled)


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
    last_term_size = None
    while True:
        results = []
        start = time.time()

        # Clear the screen on startup and if the terminal size changes
        term_size = shutil.get_terminal_size()
        if term_size != last_term_size:
            clear_screen()
            last_term_size = term_size

        for meter in METERS.values():
            sock.send(f"\\get_level {meter.name}\n".encode())
            try:
                raw_val = float(sock.recv(32).strip())
            except Exception as e:
                raise RuntimeError(f"Unable to read meters from rigctld: {e}")

            # Get the max value over the last samples
            samples[meter.name].append(raw_val)
            if len(samples[meter.name]) > MAX_SAMPLES:
                samples[meter.name].pop(0)
            max_val = max(samples[meter.name])
            results.append(
                (
                    meter,
                    raw_val,
                    max_val,
                    meter.scale_value(raw_val),
                    meter.scale_value(max_val),
                )
            )

        end = time.time()

        print_meters(results)

        to_sleep = INTERVAL_S - (end - start)
        if to_sleep < 0:
            to_sleep = 0
        time.sleep(to_sleep)


def print_meters(results: list[tuple[Meter, float, float, int, int]]) -> None:
    lines = []

    for meter, raw_val, max_val, scaled_val, scaled_max in results:
        if scaled_val < 0:
            scaled_val = 0
        elif scaled_val > 100:
            scaled_val = 100

        scaling_factor = 100 / METER_WIDTH
        scaled_val = int(scaled_val / scaling_factor)
        scaled_max = int(scaled_max / scaling_factor)
        lines.append(meter.name)

        inner_meter = ""
        for i in range(METER_WIDTH):
            if i == scaled_max and scaled_val < scaled_max:
                inner_meter += "|"
            elif i <= scaled_val:
                inner_meter += "#"
            else:
                inner_meter += " "

        meter_str = f"[{inner_meter}] "

        # Make the meter value red if it's over the max val, e.g. a SWR too high
        if raw_val >= meter.max_val:
            meter_str += Fore.RED

        meter_str += f"{raw_val:0.2f}"
        meter_str += Style.RESET_ALL
        if meter.unit:
            meter_str += f" {meter.unit}"
        meter_str += f" (max: {max_val:0.2f}"
        if meter.unit:
            meter_str += f" {meter.unit}"
        meter_str += ")"

        # Add a few spaces at the end to clear out any junk, like if our meter_str line
        # got shorter from shorter values
        meter_str += 5 * " "

        lines.append(meter_str)

    print(Cursor.POS())  # move cursor to 0,0
    for line in lines:
        print(line)


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
