"""
ADIF utilities - parsing, merging, writing, etc.

Reference: https://www.adif.org/adif
Description of the file format: http://www.adif.org/312/ADIF_312.htm#ADI_File_Format
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Optional, TextIO, Union


# Enums
class Band(Enum):
    _2190M = "2190m"
    _630M = "630m"
    _560M = "560m"
    _160M = "160m"
    _80M = "80m"
    _60M = "60m"
    _40M = "40m"
    _30M = "30m"
    _20M = "20m"
    _17M = "17m"
    _15M = "15m"
    _12M = "12m"
    _10M = "10m"
    _8M = "8m"
    _6M = "6m"
    _5M = "5m"
    _4M = "4m"
    _2M = "2m"
    _1_25M = "1.25m"
    _70CM = "70cm"
    _33CM = "33cm"
    _23CM = "23cm"
    _13CM = "13cm"
    _9CM = "9cm"
    _6CM = "6cm"
    _3CM = "3cm"
    _1_25CM = "1.25cm"
    _6MM = "6mm"
    _4MM = "4mm"
    _2_5MM = "2.5mm"
    _2MM = "2mm"
    _1MM = "1mm"


class Mode(Enum):
    AM = "AM"
    ARDOP = "ARDOP"
    ATV = "ATV"
    C4FM = "C4FM"
    CHIP = "CHIP"
    CLO = "CLO"
    CONTESTI = "CONTESTI"
    CW = "CW"
    DIGITALVOICE = "DIGITALVOICE"
    DOMINO = "DOMINO"
    DSTAR = "DSTAR"
    FAX = "FAX"
    FM = "FM"
    FSK441 = "FSK441"
    FT8 = "FT8"
    HELL = "HELL"
    ISCAT = "ISCAT"
    JT4 = "JT4"
    JT6M = "JT6M"
    JT9 = "JT9"
    JT44 = "JT44"
    JT65 = "JT65"
    MFSK = "MFSK"
    MSK144 = "MSK144"
    MT63 = "MT63"
    OLIVIA = "OLIVIA"
    OPERA = "OPERA"
    PAC = "PAC"
    PAX = "PAX"
    PKT = "PKT"
    PSK = "PSK"
    PSK2K = "PSK2K"
    Q15 = "Q15"
    QRA64 = "QRA64"
    ROS = "ROS"
    RTTY = "RTTY"
    RTTYM = "RTTYM"
    SSB = "SSB"
    SSTV = "SSTV"
    T10 = "T10"
    THOR = "THOR"
    THRB = "THRB"
    TOR = "TOR"
    V4 = "V4"
    VOI = "VOI"
    WINMOR = "WINMOR"
    WSPR = "WSPR"


@dataclass
class AdifFile:
    version: str = ""
    created: Optional[datetime] = None
    program_id: str = ""
    program_version: str = ""
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
                adif_file.records.append(AdifRecord(_fields=record))
                record = {}
            else:
                record[spec.field_name] = f.read(spec.length)
        return adif_file

    def merge(other: "AdifFile", time_match_min: int = 30) -> None:
        """
        Merge another ADIF file into this one, merging any duplicate records.

        A record is considered a duplicate of another if they match callsign, mode, band,
        and are within a certain time window of each other. This time window is controlled
        by `time_match_min`.

        Args:
            time_match_min: The time window to match records, in minutes.
        """
        # TODO
        pass


@dataclass
class AdifRecord:
    # Raw fields, as a dict
    _fields: dict[str, str] = field(default_factory=dict)

    call: str       = field(init=False)
    band: Band    = field(init=False)
    freq_mhz: str   = field(init=False)
    mode: Mode    = field(init=False)
    qso_date: date  = field(init=False)
    time_on: time   = field(init=False)
    time_off: time  = field(init=False)
    gridsquare: str = field(init=False)
    my_gridsquare: str  = field(init=False)
    tx_pwr: str         = field(init=False)
    rst_rcvd: str       = field(init=False)
    rst_sent: str       = field(init=False)
    comment: str        = field(init=False)

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

    def __post_init__(self) -> None:
        self._parse_fields()

    def __getitem__(self, key: str) -> str:
        return self._fields[key]

    def __setitem__(self, key: str, value: str) -> None:
        self._fields[key] = value
        self._parse_fields(field=key)

    def __setattr__(self, attr_name: str, value: Union[str, int, date, time, Band, Mode]) -> None:
        """
        Intercept attr sets, and update the raw fields dict if we need to
        """
        if attr_name in self.__dataclass_fields__.keys():
            if attr_name in self._string_fields and isinstance(value, str):
                self._fields[attr_name] = value
            elif attr_name == "band" and isinstance(value, Band):
                self._fields[attr_name] = value.value
            elif attr_name == "mode" and isinstance(value, Mode):
                self._fields[attr_name] = value.value
            elif attr_name == "qso_date" and isinstance(value, date):
                self._fields[attr_name] = value.strftime("%Y%m%d")
            elif attr_name in {"time_on", "time_off"} and isinstance(value, time):
                self._fields[attr_name] = value.strftime("%H%M%S")
        super().__setattr__(attr_name, value)

    def _parse_fields(self, field: str = "") -> None:
        """
        Parse out common fields. Errors with parsing are ignored, the field on the class
        is not set but the value remains in the raw fields dict.

        Args:
            field: If given, only parse this field
        """
        if field != "":
            to_parse = {field: self._fields[field]}
        else:
            to_parse = self._fields

        for field in self._string_fields:
            if field in to_parse:
                setattr(self, field, to_parse[field])

        if "band" in to_parse:
            try:
                self.band = Band(to_parse["band"].lower())
            except ValueError:
                pass
        if "mode" in to_parse:
            try:
                self.mode = Mode(to_parse["mode"].upper())
            except ValueError:
                pass
        if "qso_date" in to_parse:
            self.qso_date = parse_date(to_parse["qso_date"])
        if "time_on" in to_parse:
            self.time_on = parse_time(to_parse["time_on"])
        if "time_off" in to_parse:
            self.time_on = parse_time(to_parse["time_off"])

    def merge(self, other: "AdifRecord", force_overwrite: bool = False) -> None:
        """
        Merge another AdifRecord into this one. A field from the other record will
        replace a field in this record if it is longer (likely better data), or
        force_overwrite is set to True.
        """
        for k, v in other._fields.items():
            set_field = k not in self._fields
            set_field |= len(v) > len(self._fields.get(k, ""))
            set_field |= force_overwrite

            if set_field:
                self._fields[k] = v


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
