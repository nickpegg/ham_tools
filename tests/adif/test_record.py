from io import StringIO
from typing import Optional, Type

import pytest

from ham_tools.adif.record import AdifRecord, AdifSpecifier


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


@pytest.mark.parametrize(
    "given, expected",
    [
        (
            AdifRecord(
                fields={
                    "callsign": "n0foo",
                    "band": "10m",
                    "mode": "ssb",
                    "qso_date": "20220401",
                }
            ),
            "N0FOO-10m-SSB-20220401",
        ),
        (AdifRecord(fields={"callsign": "n0foo", "mode": "ssb"}), "N0FOO--SSB-"),
        (AdifRecord(), "---"),
    ],
)
def test_record_match_key(given: AdifRecord, expected: str) -> None:
    assert given._match_key() == expected
