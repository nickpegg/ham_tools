"""
ADIF utility functions
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import TextIO

logger = logging.getLogger(__name__)


def read_until(f: TextIO, char: str) -> str:
    """
    Returns the text from the current position in the file up to and including the given
    char. If we hit the end of the file before finding our character, a ValueError is
    raised.
    """
    buf = ""

    cur = ""
    while cur != char:
        cur = f.read(1)
        buf += cur
        if cur == "":
            raise ValueError(f"Hit end of file before finding '{char}'")

    return buf


def parse_date(date_str: str) -> date:
    """
    Parse an ADIF date - YYYYMMDD
    """
    return datetime.strptime(date_str, "%Y%m%d").date()


def parse_time(time_str: str) -> time:
    """
    Parse an ADIF time - HHMM or HHMMSS
    """
    if len(time_str) == 4:
        return datetime.strptime(time_str, "%H%M").time()
    else:
        return datetime.strptime(time_str, "%H%M%S").time()


def make_field(name: str, value: str) -> str:
    """
    Return an ADIF field/value, like "<adif_ver:5>value"
    """
    return f"<{name}:{len(value)}>{value}"
