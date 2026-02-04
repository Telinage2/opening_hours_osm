from typing import (
    Optional,
    TypeVar,
    Iterable,
    Iterator,
    Callable,
    Protocol,
    Any,
    TypeAlias,
    Self,
)
import datetime
import bisect

DATE_START = datetime.datetime(1900, 1, 1)
DATE_END = datetime.datetime(9_999, 1, 1)


T = TypeVar("T")


class _PeekableSentinel:
    pass


_peekable_sentinel = _PeekableSentinel()


class Peekable[T]:
    def __init__(self, iterable: Iterable[T]):
        self._it = iter(iterable)
        self._peeked: T | _PeekableSentinel = _peekable_sentinel

    def peek(self) -> Optional[T]:
        if isinstance(self._peeked, _PeekableSentinel):
            self._peeked = next(self._it, _peekable_sentinel)
        return None if isinstance(self._peeked, _PeekableSentinel) else self._peeked

    def next_if(self, cb: Callable[[T], bool]) -> Optional[T]:
        ni = next(self, ...)
        if ni is ...:
            return None
        if cb(ni):
            return ni
        else:
            assert self._peeked == _peekable_sentinel
            self._peeked = ni
            return None

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        if not isinstance(self._peeked, _PeekableSentinel):
            value = self._peeked
            self._peeked = _peekable_sentinel
            return value
        return next(self._it)


def create_date_opt(y: int, m: int, d: int) -> Optional[datetime.date]:
    try:
        return datetime.date(y, m, d)
    except ValueError:
        return None


def next_day_opt(day: datetime.date) -> Optional[datetime.date]:
    try:
        return day + datetime.timedelta(days=1)
    except Exception:
        return None


def next_day(day: datetime.date) -> datetime.date:
    try:
        return day + datetime.timedelta(days=1)
    except Exception:
        return DATE_END


def prev_day_opt(day: datetime.date) -> Optional[datetime.date]:
    try:
        return day - datetime.timedelta(days=1)
    except Exception:
        return None


def wrapping_contains(start: int, end: int, val: int) -> bool:
    if start <= end:
        return val >= start and val <= end
    else:
        return start <= val or val <= end


_T = TypeVar("_T")
_To = TypeVar("_To")


def map_opt(val: Optional[_T], mapper: Callable[[_T], _To]) -> Optional[_To]:
    if val is None:
        return None
    return mapper(val)


# Comparison protocols
_T_contra = TypeVar("_T_contra", contravariant=True)


class SupportsEq(Protocol):
    def __eq__(self, other: object, /) -> bool: ...


class SupportsDunderLT(Protocol[_T_contra]):
    def __lt__(self, other: _T_contra, /) -> bool: ...


class SupportsDunderGT(Protocol[_T_contra]):
    def __gt__(self, other: _T_contra, /) -> bool: ...


class SupportsDunderLE(Protocol[_T_contra]):
    def __le__(self, other: _T_contra, /) -> bool: ...


class SupportsDunderGE(Protocol[_T_contra]):
    def __ge__(self, other: _T_contra, /) -> bool: ...


class SupportsAllComparisons(
    SupportsEq,
    SupportsDunderLT[Any],
    SupportsDunderGT[Any],
    SupportsDunderLE[Any],
    SupportsDunderGE[Any],
    Protocol,
): ...


SupportsRichComparison: TypeAlias = SupportsAllComparisons
SupportsRichComparisonT = TypeVar(
    "SupportsRichComparisonT", bound=SupportsRichComparison
)


def ranges_union(
    ranges: Iterable[tuple[SupportsRichComparisonT, SupportsRichComparisonT]],
) -> Iterator[tuple[SupportsRichComparisonT, SupportsRichComparisonT]]:
    rg = list(ranges)
    rg.sort(key=lambda r: r[0])

    rg = iter(rg)
    current = next(rg, None)
    if current is None:
        return

    while (item := next(rg, None)) is not None:
        if current[1] >= item[0]:
            if item[1] > current[1]:
                current = current[0], item[1]
        else:
            yield current
            current = item

    if current is not None:
        yield current


def range_intersection(
    range_1: tuple[SupportsRichComparisonT, SupportsRichComparisonT],
    range_2: tuple[SupportsRichComparisonT, SupportsRichComparisonT],
) -> Optional[tuple[SupportsRichComparisonT, SupportsRichComparisonT]]:
    result = max(range_1[0], range_2[0]), min(range_1[1], range_2[1])
    if result[0] < result[1]:
        return result
    else:
        return None


class UniqueSortedList:
    def __init__(self, content: Iterable[str] = []):
        self.content = sorted(set(content))

    def union(self, other: Self) -> Self:
        def _union(x: list[str], y: list[str]) -> list[str]:
            if not y:
                return x
            if not x:
                return y

            head_x = x[0]
            head_y = y[0]
            tail_x = x[-1]
            tail_y = y[-1]

            if tail_x < head_y:
                x.extend(y)
                return x
            if tail_y < head_x:
                y.extend(x)
                return y

            if tail_x > tail_y:
                last = x.pop()
            elif tail_x < tail_y:
                last = y.pop()
            else:
                y.pop()
                last = x.pop()

            new_head = _union(x, y)
            new_head.append(last)
            return new_head

        x = list(self.content)
        y = list(other.content)
        return type(self)(_union(x, y))

    def __eq__(self, value: object) -> bool:
        if isinstance(value, UniqueSortedList):
            return self.content == value.content
        if isinstance(value, list):
            return self.content == value
        return False

    def __len__(self):
        return len(self.content)

    def __contains__(self, item):
        pos = bisect.bisect_left(self.content, item)
        return pos < len(self.content) and self.content[pos] == item

    def __repr__(self) -> str:
        return repr(self.content)

    def __str__(self) -> str:
        return str(self.content)
