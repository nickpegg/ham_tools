"""
ADIF utilities - parsing, merging, writing, etc.

Reference: https://www.adif.org/adif
Description of the file format: http://www.adif.org/312/ADIF_312.htm#ADI_File_Format
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Optional, TextIO, Union

from ham_tools.version import VERSION


@dataclass
class AdifFile:
    version: str = "3.1.2"
    created: Optional[datetime] = None
    program_id: str = "N7PGG ham_tools"
    program_version: str = VERSION
    records: list["AdifRecord"] = field(default_factory=list)

    # Any text before the first specifier in the header
    comment: str = ""

    @classmethod
    def from_string(cls, contents: str) -> "AdifFile":
        """
        Parse from a string
        """
        return cls._from_file_obj(StringIO(contents))

    @classmethod
    def from_file(cls, file_path: Path) -> "AdifFile":
        """
        Parse from a file. Use this over from_string() when working with a large ADIF
        file, since this will read the file incrementally instad of loading the whole
        thing into memory.
        """
        with file_path.open() as f:
            return cls._from_file_obj(f)

    @classmethod
    def _from_file_obj(cls, f: TextIO) -> "AdifFile":
        """
        Parse incrementally from a file object
        """
        adif_file = cls()

        # Read everything before the first specifier as a comment
        adif_file.comment = read_until(f, "<")[:-1].strip()
        f.seek(f.tell() - 1)

        # Read the header, until we reach an <eoh>
        at_end = False
        while not at_end:
            spec = AdifSpecifier.read_next(f)
            if spec.field_name == "eoh":
                at_end = True
            elif spec.field_name == "adif_ver":
                adif_file.version = f.read(spec.length)
            elif spec.field_name == "created_timestamp":
                dt = f.read(spec.length)
                adif_file.created = datetime.strptime(dt, "%Y%m%d %H%M%S")
            elif spec.field_name == "programid":
                adif_file.program_id = f.read(spec.length)
            elif spec.field_name == "programversion":
                adif_file.program_version = f.read(spec.length)

        # Read records one at a time, each ending with <eor>
        record: dict[str, str] = {}
        while True:
            try:
                spec = AdifSpecifier.read_next(f)
            except ValueError:
                break

            if spec.field_name == "eor":
                adif_file.records.append(AdifRecord(fields=record))
                record = {}
            else:
                record[spec.field_name] = f.read(spec.length)
        return adif_file

    def merge(self, other: "AdifFile", time_match_min: int = 15) -> None:
        """
        Merge another ADIF file into this one, merging any duplicate records.

        A record is considered a duplicate of another if they match callsign, mode,
        band, and are within a certain time window of each other. This time window is
        controlled by `time_match_min`.

        Args:
            time_match_min: The time window to match records, in minutes.
        """
        # First, bucket QSOs from both files by date fields we match on, so comparison
        # is faster
        my_buckets = defaultdict(list)
        other_buckets = defaultdict(list)

        for record in self.records:
            my_buckets[record._match_key()].append(record)
        for record in other.records:
            other_buckets[record._match_key()].append(record)

        # For each date, merge any QSOs which are close enough to each other. If the
        # other record has no match, just append it to ours.
        for k, other_records in other_buckets.items():
            if k not in my_buckets:
                self.records.extend(other_records)
                continue

            for my_record in my_buckets[k]:
                for other_record in other_records:
                    if other_record.datetime is None or my_record.datetime is None:
                        # Can't compare missing times, skip
                        continue

                    min_time = my_record.datetime - timedelta(minutes=time_match_min)
                    max_time = my_record.datetime - timedelta(minutes=time_match_min)

                    if (
                        other_record.datetime <= max_time
                        and other_record.datetime >= min_time
                    ):
                        # We have a match!
                        my_record.merge(other_record)
                    else:
                        # No match, append other record to our list
                        self.records.append(other_record)

        # Sort all QSOs in this file by (date, time_on) ascending
        self.records = sorted(self.records, key=lambda r: (r.qso_date, r.time_on))


@dataclass
class AdifRecord:
    # Raw fields, as a dict
    fields: dict[str, str] = field(default_factory=dict)

    _string_fields = {
        "call",
        "freq",
        "gridsquare",
        "my_gridsquare",
        "tx_pwr",
        "rst_rcvd",
        "rst_sent",
        "comment",
    }

    def __getitem__(self, key: str) -> str:
        return self.fields[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.fields[key] = value

    def merge(self, other: "AdifRecord", force_overwrite: bool = False) -> None:
        """
        Merge another AdifRecord into this one. A field from the other record will
        replace a field in this record if it is longer (likely better data), or
        force_overwrite is set to True.
        """
        for k, v in other.fields.items():
            set_field = k not in self.fields
            set_field |= len(v) > len(self.fields.get(k, ""))
            set_field |= force_overwrite

            if set_field:
                self.fields[k] = v

    def _maybe_parse_date(self, field_name: str) -> Optional[date]:
        f = self.fields.get(field_name)
        if f:
            return parse_date(f)
        else:
            return None

    def _maybe_parse_time(self, field_name: str) -> Optional[time]:
        f = self.fields.get(field_name)
        if f:
            return parse_time(f)
        else:
            return None

    def _match_key(self) -> str:
        """
        Returns a string suitable as a dict key for telling if two QSOs likely match.
        You need to also separately check that the times match up in addition.
        """
        parts = [
            self.fields.get("callsign", "").upper(),
            self.fields.get("band", "").lower(),
            self.fields.get("mode", "").upper(),
        ]
        return "-".join(parts)

    # Accessor methods which parse fields into Python-native types, e.g. dates and times
    @property
    def qso_date(self) -> Optional[date]:
        return self._maybe_parse_date("qso_date")

    @property
    def time_on(self) -> Optional[time]:
        return self._maybe_parse_time("time_on")

    @property
    def time_off(self) -> Optional[time]:
        return self._maybe_parse_time("time_on")

    @property
    def datetime(self) -> Optional[datetime]:
        """
        Returns a datetime based on the qso_date and the time_on. Returns None if either
        of those are None.
        """
        d = self.qso_date
        t = self.time_on
        if d is None or t is None:
            return None

        return datetime(
            d.year, d.month, d.day, t.hour, t.minute, t.second, t.microsecond
        )


@dataclass
class AdifSpecifier:
    """
    Specifier for a ADIF field, like <name:4>jawn

    <field_name:length>
    <field_name:length:type>
    """

    field_name: str
    length: int = 0
    type_: str = ""

    @classmethod
    def parse(cls, spec: str) -> "AdifSpecifier":
        """
        Parse a specifier from a string
        """
        spec = spec.lower().strip("<>")
        parts = spec.split(":")

        if len(parts) == 1:
            # Something like <eoh> or <eor>
            return AdifSpecifier(parts[0])
        if len(parts) == 2:
            # Just a name and a length
            return AdifSpecifier(parts[0], int(parts[1]), "")
        elif len(parts) == 3:
            return AdifSpecifier(parts[0], int(parts[1]), parts[2])
        else:
            raise ValueError(f"Invalid specifier: {spec}")

    @classmethod
    def read_next(cls, f: TextIO) -> "AdifSpecifier":
        """
        Read the next specifier from the file. Will advance the position in the file.
        """
        read_until(f, "<")
        buf = "<" + read_until(f, ">")
        return cls.parse(buf)


# Util functions
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
