"""
ADIF utilities - parsing, merging, writing, etc.

Reference: https://www.adif.org/adif
Description of the file format: http://www.adif.org/312/ADIF_312.htm#ADI_File_Format
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class AdifFile:
    version = str
    created = datetime
    program_id = str
    program_version = str
    entries: list[AdifEntry] = field(default_factory=list)

    @classmethod
    def from_string(cls, contents: str) -> AdifFile:
        """
        Parse from a string
        """

    @classmethod
    def from_file(cls, file_path: Path) -> AdifFile:
        """
        Parse from a file. Use this over from_string() when working with a large ADIF
        file, since this will read the file incrementally instad of loading the whole
        thing into memory.
        """


@dataclass
class AdifEntry:
    # Raw fields, as a dict
    fields: dict[str, str] = field(default_factory=dict)

    def merge(self, other: AdifEntry, overwrite: bool = False) -> None:
        """
        Merge another AdifEntry into this one

        Args:
            overwrite: If True, any fields in the other entry will overwrite fields in
                       this entry
        """
        if overwrite:
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
    length: int
    type_: str

    @classmethod
    def parse(cls, spec: str) -> AdifSpecifier:
        """
        Parse a specifier from a string
        """
        spec = spec.lower().strip("<>")
        parts = spec.split(":")

        if len(parts) == 2:
            # Just a name and a length
            return AdifSpecifier(parts[0], int(parts[1]), "")
        elif len(parts) == 3:
            return AdifSpecifier(parts[0], int(parts[1]), parts[2])
        else:
            raise ValueError(f"Invalid specifier: {spec}")
