from enum import Enum


class Mode(Enum):
    AM_N = 13
    LSB = 1
    USB = 2
    CW = 3
    CW_R = 7

    RTTY_LSB = 6
    RTTY_USB = 9
    DATA_LSB = 8
    DATA_USB = 12
    DATA_FM = 10

    FM = 4
    FM_N = 11
    C4FM = 14


class SquelchMode(Enum):
    OFF = 0
    CTCSS_RX_TX = 1
    CTCSS_TX = 2
    DCS_RX_TX = 3
    DCS_TX = 4


class RepeaterShift(Enum):
    SIMPLEX = 0
    PLUS = 1
    MINUS = 2
