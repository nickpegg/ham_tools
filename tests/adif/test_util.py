from datetime import date, time
from io import StringIO
from typing import Type, Union

import pytest

from ham_tools.adif.util import parse_date, parse_time, read_until


def test_read_until() -> None:
    assert read_until(StringIO("foo <bar> baz"), "<") == "foo <"
    with pytest.raises(ValueError):
        assert read_until(StringIO("foo lol"), "<") == "foo lol"
    with pytest.raises(ValueError):
        assert read_until(StringIO(""), "<") == ""


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
