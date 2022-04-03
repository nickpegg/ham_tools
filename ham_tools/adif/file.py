import logging
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Optional, TextIO, Union

from ham_tools.adif.record import AdifRecord, AdifSpecifier
from ham_tools.adif.util import make_field, read_until
from ham_tools.version import VERSION

logger = logging.getLogger(__name__)


@dataclass
class AdifFile:
    version: str = "3.1.2"
    created: Optional[datetime] = None
    program_id: str = "N7PGG ham_tools"
    program_version: str = VERSION
    records: list["AdifRecord"] = field(default_factory=list)

    # Any text before the first specifier in the header
    comment: str = ""

    def __str__(self) -> str:
        s = StringIO()
        self._to_file_obj(s)
        return s.getvalue()

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

    # TODO: output methods - to string, to file
    def to_file(self, file_path: Path) -> None:
        with file_path.open() as f:
            self._to_file_obj(f)

    def _to_file_obj(self, f: TextIO) -> None:
        """
        Write the ADIF file to the given file object
        """
        f.write(f"{self.comment}\n")
        if self.version:
            f.write(make_field("adif_ver", self.version) + "\n")

        if not self.created:
            self.created = datetime.now()
        ts = self.created.strftime("%Y%m%d %H%M%S")
        f.write(make_field("created_timestamp", ts) + "\n")

        if self.program_id:
            f.write(make_field("programid", self.program_id) + "\n")

        if self.program_version:
            f.write(make_field("programversion", self.program_version))
        f.write("<eoh>\n")

        for record in self.records:
            f.write(str(record) + "\n")

    def copy(self) -> "AdifFile":
        """
        Return a copy of this AdifFile
        """
        new = copy(self)
        new.records = [r.copy() for r in self.records]
        return new

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
                logger.debug(f"{k} not found in my buckets")
                self.records.extend(other_records)
                continue

            for other_record in other_records:
                # Try to find a matching record in our records
                match = None
                for my_record in my_buckets[k]:
                    # Sanity check
                    if (
                        my_record.fields.get("callsign")
                        != other_record.fields.get("callsign")
                        or my_record.fields.get("mode")
                        != other_record.fields.get("mode")
                        or my_record.fields.get("band")
                        != other_record.fields.get("band")
                        or my_record.qso_date != other_record.qso_date
                    ):
                        raise ValueError(
                            "records differ despite having the same match key. This is "
                            "a bug"
                        )

                    if other_record.time_on == my_record.time_on:
                        match = my_record
                        break
                    elif other_record.datetime is None or my_record.datetime is None:
                        # Can't compare missing times, skip
                        continue

                    min_time = my_record.datetime - timedelta(minutes=time_match_min)
                    max_time = my_record.datetime + timedelta(minutes=time_match_min)
                    if (
                        other_record.datetime <= max_time
                        and other_record.datetime >= min_time
                    ):
                        match = my_record

                if match:
                    match.merge(other_record)
                else:
                    self.records.append(other_record)

        # Sort all QSOs in this file by (date, time_on) ascending
        self.records = sorted(self.records, key=lambda r: (r.qso_date, r.time_on))
