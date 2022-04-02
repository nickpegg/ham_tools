from datetime import date, datetime, time
from io import StringIO
from pathlib import Path
from typing import Optional, Type, Union

import pytest

from ham_tools.adif import (
    AdifFile,
    AdifRecord,
    AdifSpecifier,
    parse_date,
    parse_time,
    read_until,
)


def test_load_file() -> None:
    """
    Basic test to see if we can load a test file
    """
    path = Path(Path(__file__).parent, "data/test.adi")
    adif = AdifFile.from_file(path)
    assert adif.version == "3.1.1"
    assert adif.created == datetime(2022, 3, 12, 18, 21, 9)
    assert adif.program_id == "WSJT-X"
    assert adif.comment == "ADIF Export"

    assert len(adif.records) == 3
    assert adif.records[0]["call"] == "NU6V"


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


def test_read_until() -> None:
    assert read_until(StringIO("foo <bar> baz"), "<") == "foo <"
    with pytest.raises(ValueError):
        assert read_until(StringIO("foo lol"), "<") == "foo lol"
    with pytest.raises(ValueError):
        assert read_until(StringIO(""), "<") == ""


def test_record_merge() -> None:
    base_fields = {"foo": "bar", "bar": "baz"}

    # no overwrite, no new fields
    r1 = AdifRecord(fields=base_fields.copy())
    r2 = AdifRecord(fields={"foo": "x"})
    r1.merge(r2)
    assert r1.fields == base_fields

    # no overwrite, new field
    r1 = AdifRecord(fields=base_fields.copy())
    r2 = AdifRecord(fields={"lol": "wut"})
    r1.merge(r2)
    assert r1.fields == {
        "foo": "bar",
        "bar": "baz",
        "lol": "wut",
    }

    # better data
    r1 = AdifRecord(fields=base_fields.copy())
    r2 = AdifRecord(fields={"foo": "better data"})
    r1.merge(r2)
    assert r1["foo"] == "better data"

    # force_overwrite, worse data
    r1 = AdifRecord(fields=base_fields.copy())
    r2 = AdifRecord(fields={"foo": "x"})
    r1.merge(r2, force_overwrite=True)
    assert r1["foo"] == "x"


def test_file_merge() -> None:
    # TODO
    pass


@pytest.mark.parametrize(
    "given,expected",
    [
        ("2022", ValueError),
        ("", ValueError),
        ("20220401", date(2022, 4, 1)),
    ],
)
def test_parse_date(given: str, expected: Union[date, Type[Exception]]) -> None:
    if isinstance(expected, date):
        assert parse_date(given) == expected
    elif issubclass(expected, BaseException):
        with pytest.raises(expected):
            parse_date(given)
    else:
        assert False, f"Unexpected expected: {expected}"


@pytest.mark.parametrize(
    "given,expected",
    [
        ("", ValueError),
        ("2503", ValueError),
        ("0244", time(2, 44)),
        ("2359", time(23, 59)),
        ("235905", time(23, 59, 5)),
    ],
)
def test_parse_time(given: str, expected: Union[time, Type[Exception]]) -> None:
    if isinstance(expected, time):
        assert parse_time(given) == expected
    elif issubclass(expected, BaseException):
        with pytest.raises(expected):
            parse_time(given)
    else:
        assert False, f"Unexpected expected: {expected}"

@pytest.mark.parametrize(
    "given, expected",
    [
        (
            AdifRecord(
                fields={"callsign": "n0foo", "band": "10m", "mode": "ssb", "qso_date": "20220401"}
            ),
            "N0FOO-10m-SSB-20220401"
        ),
        (AdifRecord(fields={"callsign": "n0foo", "mode": "ssb"}), "N0FOO--SSB-"),
        (AdifRecord(), "---"),
    ],
)
def test_record_match_key(given: AdifRecord, expected: str) -> None:
    assert given._match_key() == expected
