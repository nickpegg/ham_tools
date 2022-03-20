"""
ADIF utilities - parsing, merging, writing, etc.

Reference: https://www.adif.org/adif
Description of the file format: http://www.adif.org/312/ADIF_312.htm#ADI_File_Format
"""

# TODO: Support JMESPath for querying Records: https://jmespath.org/examples.html

from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional, TextIO


@dataclass
class AdifFile:
    version: str = ""
    created: Optional[datetime] = None
    program_id: str = ""
    program_version: str = ""
    records: list["AdifRecord"] = field(default_factory=list)

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
        # TODO: Store everything before the first specifier as a file comment
        adif_file = cls()

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


@dataclass
class AdifRecord:
    # Raw fields, as a dict
    fields: dict[str, str] = field(default_factory=dict)

    def __getitem__(self, key: str) -> str:
        return self.fields[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.fields[key] = value

    def merge(self, other: "AdifRecord", overwrite: bool = False) -> None:
        """
        Merge another AdifRecord into this one

        Args:
            overwrite: If True, any fields in the other record will overwrite fields in
                       this record
        """
        if overwrite:
            # TODO: If our record is longer, assume it has better information
            self.fields.update(other.fields)
        else:
            for k, v in other.fields.items():
                if k not in self.fields:
                    self.fields[k] = v


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
        buf = ""

        # Seek until we hit a "<"
        char = f.read(1)
        while char != "<":
            if char == "":
                raise ValueError("No specifier found")
            char = f.read(1)

        # include the "<" in our output
        buf += char

        # read until we hit a ">"
        char = f.read(1)
        while char != ">":
            if char == "":
                raise ValueError("Found start of specifier, but no end")
            buf += char
            char = f.read(1)
        buf += char

        return cls.parse(buf)
