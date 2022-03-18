from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional, Type

import pytest

from ham_tools.adif import AdifFile, AdifSpecifier


def test_load_file() -> None:
    """
    Basic test to see if we can load a test file
    """
    path = Path(Path(__file__).parent, "data/test.adi")
    adif = AdifFile.from_file(path)
    assert adif.version == "3.1.1"
    assert adif.created == datetime(2022, 3, 12, 18, 21, 9)
    assert adif.program_id == "WSJT-X"


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("<call:4>", AdifSpecifier(field_name="call", length=4)),
        ("<qso_date:8>", AdifSpecifier(field_name="qso_date", length=8)),
        (
            "<some_number:11:N>",
            AdifSpecifier(field_name="some_number", length=11, type_="n"),
        ),
        ("<eor>", AdifSpecifier(field_name="eor")),
    ],
)
def test_specifier_parse(spec: str, expected: AdifSpecifier) -> None:
    """
    Test parsing a specifier
    """
    assert AdifSpecifier.parse(spec) == expected


@pytest.mark.parametrize(
    "buf,expected,error",
    [
        ("oh no", "", ValueError),
        # Dangling specifier
        ("blah<adif_ver:5", "", ValueError),
        ("<adif_ver:5>asdfg", AdifSpecifier("adif_ver", 5), None),
        ("blah <adif_ver:5>asdfg", AdifSpecifier("adif_ver", 5), None),
    ],
)
def test_read_next_specifier(
    buf: str, expected: AdifSpecifier, error: Optional[Type[Exception]]
) -> None:
    if error is None:
        assert AdifSpecifier.read_next(StringIO(buf)) == expected
    else:
        with pytest.raises(error):
            AdifSpecifier.read_next(StringIO(buf))
