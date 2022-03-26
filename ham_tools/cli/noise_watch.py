"""
Print out the S-meter reading every 2 seconds, useful for noise hunting.

For example, you can SSH in to your computer from your phone, then run this, and start
running around the house unplugging things until the noise level goes down
"""

import time
from datetime import datetime

from serial import Serial

from ham_tools.constants import DEFAULT_BAUD, DEFAULT_PORT
from ham_tools.ft991a import FT991A


def main() -> None:
    port = Serial(DEFAULT_PORT, baudrate=DEFAULT_BAUD, timeout=0.25, exclusive=True)
    radio = FT991A(port)
    while True:
        iterations = 5
        val_sum = 0
        for _ in range(iterations):
            result = radio.send_cmd(b"RM1;")
            val_sum += int(result.decode().strip().strip(";")[-3:])

        avg = val_sum / iterations
        pct = 100 * avg / 255

        print(f"{datetime.now()} - {pct:.02f}%")
        time.sleep(2)


if __name__ == "__main__":
    main()
