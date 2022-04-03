import logging
from copy import copy
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional, TextIO

from ham_tools.adif.util import make_field, parse_date, parse_time, read_until

logger = logging.getLogger(__name__)


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

    def __str__(self) -> str:
        buf = ""
        for k, v in self.fields.items():
            buf += make_field(k, v) + " "
        buf += "<eor>"
        return buf

    def __getitem__(self, key: str) -> str:
        return self.fields[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.fields[key] = value

    def copy(self) -> "AdifRecord":
        new = copy(self)
        new.fields = self.fields.copy()
        return new

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
            self.fields.get("qso_date", ""),
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
