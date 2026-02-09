from typing import Optional, Iterator, Self
from dataclasses import dataclass, field
import datetime
import logging
import itertools

from opening_hours_osm.model import OpeningHoursExpression, RuleSequence
from opening_hours_osm.model.enums import RuleOperator, RuleKind
from opening_hours_osm.model.util import DateTimeRange
from opening_hours_osm.model.time import MIDNIGHT_00
from opening_hours_osm.context import Context
from opening_hours_osm.schedule import Schedule, TimeRange
from opening_hours_osm.parser import parse_opening_hours_tree, build_opening_hours
from opening_hours_osm.util import (
    DATE_START,
    DATE_END,
    DATE_ZERO,
    Peekable,
    map_opt,
    next_day_opt,
    prev_day_opt,
)

log = logging.getLogger(__name__)


@dataclass
class Interval:
    from_date: datetime.datetime
    to_date: Optional[datetime.datetime]
    unknown: bool
    comment: Optional[str]


@dataclass
class OpenDuration:
    open: int = 0
    unknown: int = 0


def rule_sequence_schedule_at(
    rule_sequence: RuleSequence, date: datetime.date, ctx: Context
) -> Optional[Schedule]:
    if rule_sequence.day_selector.filter(date, ctx):
        from_today = Schedule.from_ranges(
            rule_sequence.time_selector.intervals_at(date, ctx),
            rule_sequence.kind,
            rule_sequence.comments,
        )
    else:
        from_today = None

    prev_date = prev_day_opt(date)
    if prev_date is not None and rule_sequence.day_selector.filter(prev_date, ctx):
        from_yesterday = Schedule.from_ranges(
            rule_sequence.time_selector.intervals_at_next_day(date, ctx),
            rule_sequence.kind,
            rule_sequence.comments,
        )
    else:
        from_yesterday = None

    if from_today is not None and from_yesterday is not None:
        return from_today.addition(from_yesterday)
    elif from_today is not None:
        return from_today
    else:
        return from_yesterday


class TimeDomainIterator:
    def __init__(
        self,
        opening_hours: "OpeningHours",
        start_datetime: datetime.datetime,
        end_datetime: datetime.datetime,
    ) -> None:
        start_date = start_datetime.date()
        start_time = start_datetime.time()

        if start_datetime >= end_datetime:
            curr_schedule = Peekable([])
        else:
            curr_schedule = Peekable(opening_hours.schedule_at(start_date))

        while (tr := curr_schedule.peek()) is not None and not tr.contains_time(
            start_time
        ):
            next(curr_schedule)

        self.opening_hours = opening_hours
        self.end_datetime = end_datetime
        self.curr_date = start_date
        self.curr_schedule: Peekable[TimeRange] = curr_schedule

    def _consume_until_next_kind(self, curr_kind: RuleKind):
        start_date = self.curr_date

        while (tr := self.curr_schedule.peek()) is not None and tr.kind == curr_kind:
            max_interval_size = self.opening_hours.ctx.approx_bound_interval_size
            if (
                max_interval_size is not None
                and self.curr_date - start_date
                > max_interval_size + datetime.timedelta(days=1)
            ):
                return

            next(self.curr_schedule)

            if self.curr_schedule.peek() is None:
                next_change_hint = self.opening_hours._next_change_hint(
                    self.curr_date
                ) or next_day_opt(self.curr_date)
                assert next_change_hint, "reached invalid date"
                assert next_change_hint > self.curr_date, "infinite loop detected"
                self.curr_date = next_change_hint

                if (
                    self.curr_date <= self.end_datetime.date()
                    and self.curr_date < DATE_END.date()
                ):
                    self.curr_schedule = Peekable(
                        self.opening_hours.schedule_at(self.curr_date)
                    )

    def __iter__(self) -> Iterator[DateTimeRange]:
        return self

    def __next__(self) -> DateTimeRange:
        curr_tr = self.curr_schedule.peek()
        if curr_tr is None:
            raise StopIteration()

        start = datetime.datetime.combine(self.curr_date, curr_tr.start.to_sys())
        self._consume_until_next_kind(curr_tr.kind)
        end_date = self.curr_date
        end_time = map_opt(self.curr_schedule.peek(), lambda x: x.start) or MIDNIGHT_00
        end = min(
            self.end_datetime, datetime.datetime.combine(end_date, end_time.to_sys())
        )

        max_interval_size = self.opening_hours.ctx.approx_bound_interval_size
        if max_interval_size is not None and end - start > max_interval_size:
            return DateTimeRange(start, DATE_END, curr_tr.kind, curr_tr.comments)

        return DateTimeRange(start, end, curr_tr.kind, curr_tr.comments)


@dataclass
class OpeningHours:
    expr: OpeningHoursExpression
    ctx: Context = field(default_factory=Context)

    @classmethod
    def parse(cls, input: str, ctx: Optional[Context] = None) -> Self:
        """Parse opening hours from a OSM-formatted string."""
        tree = parse_opening_hours_tree(input)
        expr = build_opening_hours(tree)
        return cls(expr, ctx or Context())

    def _next_change_hint(self, date: datetime.date) -> Optional[datetime.date]:
        """Provide a lower bound to the next date when a different set of rules could match."""
        if date < DATE_START.date():
            return DATE_START.date()

        if self.expr.is_constant():
            return DATE_END.date()

        first_date = None
        for rule in self.expr.rules:
            if (
                rule.time_selector.is_immutable_full_day()
                or not rule.day_selector.filter(date, self.ctx)
            ):
                d = rule.day_selector.next_change_hint(date, self.ctx)
            else:
                d = next_day_opt(date)
            if d is None:
                d = DATE_ZERO
            if first_date is None or d < first_date:
                first_date = d

        if first_date == DATE_ZERO:
            return None
        return first_date

    def schedule_at(self, date: datetime.date) -> Schedule:
        """Get the schedule at a given day"""
        if date < DATE_START.date() or date > DATE_END.date():
            return Schedule([])

        prev_match = False
        prev_eval: Optional[Schedule] = None

        for rules_seq in self.expr.rules:
            curr_match = rules_seq.day_selector.filter(date, self.ctx)
            curr_eval = rule_sequence_schedule_at(rules_seq, date, self.ctx)

            if rules_seq.operator == RuleOperator.NORMAL and (
                rules_seq.kind == RuleKind.OPEN or rules_seq.kind == RuleKind.UNKNOWN
            ):
                # The normal rule acts like the additional rule when the kind is "closed".
                new_match = curr_match or prev_match
                if curr_match:
                    new_eval = curr_eval
                else:
                    new_eval = prev_eval or curr_eval
            elif rules_seq.operator == RuleOperator.ADDITIONAL or (
                rules_seq.operator == RuleOperator.NORMAL
                and rules_seq.kind == RuleKind.CLOSED
            ):
                new_match = curr_match or prev_match
                if prev_eval and curr_eval:
                    new_eval = prev_eval.addition(curr_eval)
                else:
                    new_eval = prev_eval or curr_eval
            else:
                if prev_match and (not prev_eval or not prev_eval.is_always_closed()):
                    new_match = prev_match
                    new_eval = prev_eval
                else:
                    new_match = curr_match
                    new_eval = curr_eval

            prev_match = new_match
            prev_eval = new_eval

        return prev_eval or Schedule([])

    def iter_range_naive(
        self, date_from: datetime.datetime, date_to: datetime.datetime
    ) -> Iterator[DateTimeRange]:
        """Same as [`iter_range`], but with naive date input and outputs."""
        d_from = min(DATE_END, date_from)
        d_to = min(DATE_END, date_to)

        return (
            DateTimeRange(
                max(dtr.start, d_from), min(dtr.end, d_to), dtr.kind, dtr.comments
            )
            for dtr in itertools.takewhile(
                lambda dtr: dtr.start < d_to, TimeDomainIterator(self, d_from, d_to)
            )
        )

    def iter_range(
        self, date_from: datetime.datetime, date_to: datetime.datetime
    ) -> Iterator[DateTimeRange]:
        """Iterate over disjoint intervals of different state restricted to the time interval `from..to`."""
        naive_from = min(DATE_END, self.ctx.locale.naive(date_from))
        naive_to = min(DATE_END, self.ctx.locale.naive(date_to))

        return (
            DateTimeRange(
                self.ctx.locale.localized_datetime(dtr.start),
                self.ctx.locale.localized_datetime(dtr.end),
                dtr.kind,
                dtr.comments,
            )
            for dtr in self.iter_range_naive(naive_from, naive_to)
        )

    def iter_from(self, date_from: datetime.datetime) -> Iterator[DateTimeRange]:
        """Same as iter_range but with an open end"""
        return self.iter_range(date_from, self.ctx.locale.localized_datetime(DATE_END))

    def next_change(
        self, current_time: datetime.datetime
    ) -> Optional[datetime.datetime]:
        """Get the next time where the state will change."""
        try:
            interval = next(self.iter_from(current_time))
        except StopIteration:
            return None

        if self.ctx.locale.naive(interval.end) >= DATE_END:
            return None
        else:
            return interval.end

    def state(self, current_time: datetime.datetime) -> RuleKind:
        """Get the state at given time."""
        try:
            dtr = next(
                self.iter_range(
                    current_time, current_time + datetime.timedelta(minutes=1)
                )
            )
            return dtr.kind
        except StopIteration:
            return RuleKind.CLOSED

    def is_open(self, current_time: datetime.datetime) -> bool:
        """Check if this is open at a given time."""
        return self.state(current_time) == RuleKind.OPEN

    def is_closed(self, current_time: datetime.datetime) -> bool:
        """Check if this is closed at a given time."""
        return self.state(current_time) == RuleKind.CLOSED

    def is_unknown(self, current_time: datetime.datetime) -> bool:
        """Check if this is unknown at a given time."""
        return self.state(current_time) == RuleKind.UNKNOWN
