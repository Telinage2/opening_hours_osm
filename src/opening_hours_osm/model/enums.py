import enum


class TimeEvent(enum.Enum):
    DAWN = enum.auto()
    SUNRISE = enum.auto()
    SUNSET = enum.auto()
    DUSK = enum.auto()

    def __str__(self) -> str:
        return self.name.lower()


class RuleKind(enum.Enum):
    OPEN = enum.auto()
    CLOSED = enum.auto()
    UNKNOWN = enum.auto()

    def __str__(self) -> str:
        return self.name.lower()


class HolidayKind(enum.Enum):
    PH = enum.auto()
    SH = enum.auto()

    def __str__(self) -> str:
        return self.name


class RuleOperator(enum.Enum):
    NORMAL = enum.auto()
    ADDITIONAL = enum.auto()
    FALLBACK = enum.auto()

    def _separator(self):
        match self:
            case self.NORMAL:
                return "; "
            case self.ADDITIONAL:
                return ", "
            case self.FALLBACK:
                return " | "
