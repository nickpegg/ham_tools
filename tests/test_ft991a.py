from warnings import warn

from serial import Serial

from ham_tools.enums import Mode, RepeaterShift, SquelchMode
from ham_tools.ft991a import DEFAULT_BAUD, Memory, discover, read_memory, write_memory


def test_memory() -> None:
    """
    Test parsing of MT things to/from memory
    """
    responses = [
        b"MT001145150000+0000004030020SF ARC      ;",
        b"MT001432002000+0000004000000            ;",
        b"MT001028074000+000000C00000010M FT8     ;",
    ]

    # Test that the round-trip through Memory yields the same result
    for response in responses:
        m = Memory.from_mt(1, response)
        assert m.to_mt() == response

    m = Memory.from_mt(3, responses[0])
    assert m.channel == 3
    assert m.frequency_hz == 145_150_000
    assert m.mode == Mode.FM
    assert m.squelch_mode == SquelchMode.DCS_RX_TX
    assert m.repeater_shift == RepeaterShift.MINUS
    assert m.tag == "SF ARC"

    m = Memory.from_mt(5, responses[2])
    assert m.channel == 5
    assert m.frequency_hz == 28_074_000
    assert m.mode == Mode.DATA_USB
    assert m.squelch_mode == SquelchMode.OFF
    assert m.repeater_shift == RepeaterShift.SIMPLEX
    assert m.tag == "10M FT8"


def test_integration() -> None:
    """
    Integration test with a real FT-991a - start with defaults, write to memory using
    the CLI's utility functions, go back to VFO with defaults, then read from memory
    using the CLI's utility functions and make sure what we read is what we wrote.
    """
    try:
        port_info = discover()
        port = Serial(port_info.device, baudrate=DEFAULT_BAUD, timeout=0.5)
    except Exception as e:
        warn(RuntimeWarning(f"Unable to use radio for integration test: {e}"))
        return

    original = Memory(
        channel=99,
        frequency_hz=146_520_000,
        mode=Mode.FM,
        squelch_mode=SquelchMode.CTCSS_RX_TX,
        ctcss_dhz=1318,
        dcs_code=332,
    )

    with port:
        write_memory(port, original)

        # Tune to some random freq and mess with the CTCSS/DCS
        port.write(b"FA144000000;")
        port.read_until(b";")
        port.write(b"CN0000;")
        port.read_until(b";")
        port.write(b"CN1000;")
        port.read_until(b";")

        written = read_memory(port, original.channel)
        assert written == original

        # Clean up after ourselves. AM (VFO-A to Memory Channel) has the effect of
        # clearing the selected memory channel.
        port.write(f"MC{original.channel:03d};".encode())
        port.write(b"AM;")