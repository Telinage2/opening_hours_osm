from typing import Generator, Optional
import importlib.resources
import enum

import lark

from opening_hours_osm import model
from opening_hours_osm.model.util import Sign, Bitfield
from opening_hours_osm.util import map_opt, UniqueSortedList


def get_parser():
    grammar = importlib.resources.read_text("opening_hours_osm", "time_domain.lark")
    return lark.Lark(grammar, parser="earley")


PARSER = get_parser()


class Rules(enum.StrEnum):
    time_domain = enum.auto()
    rule_sequence = enum.auto()
    any_rule_separator = enum.auto()
    normal_rule_separator = enum.auto()
    additional_rule_separator = enum.auto()
    fallback_rule_separator = enum.auto()
    selector_sequence = enum.auto()
    rule_modifier = enum.auto()
    rule_kind = enum.auto()
    wide_range_selectors = enum.auto()
    small_range_selectors = enum.auto()
    year_selector = enum.auto()
    monthday_selector = enum.auto()
    week_selector = enum.auto()
    weekday_selector = enum.auto()
    separator_for_readability = enum.auto()
    time_selector = enum.auto()
    timespan = enum.auto()
    time = enum.auto()
    repeated_time = enum.auto()
    extended_time = enum.auto()
    hour_minutes = enum.auto()
    extended_hour_minutes = enum.auto()
    variable_time = enum.auto()
    event = enum.auto()
    weekday_sequence = enum.auto()
    weekday_range = enum.auto()
    holiday_sequence = enum.auto()
    holiday = enum.auto()
    nth_entry = enum.auto()
    day_offset = enum.auto()
    week = enum.auto()
    week_step = enum.auto()
    monthday_range = enum.auto()
    monthday_range_from = enum.auto()
    date_offset = enum.auto()
    date_from = enum.auto()
    date_to = enum.auto()
    variable_date = enum.auto()
    year_range = enum.auto()
    year_step = enum.auto()
    plus_or_minus = enum.auto()
    comment = enum.auto()

    @staticmethod
    def should_skip(val: str) -> bool:
        return val == Rules.separator_for_readability


class Tokens(enum.StrEnum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values) -> str:
        return name

    OPEN = enum.auto()
    CLOSED = enum.auto()
    UNKNOWN = enum.auto()
    CPART = enum.auto()
    CESCAPE = enum.auto()
    ALWAYS_OPEN = enum.auto()
    PLUS = enum.auto()
    MINUS = enum.auto()
    POSITIVE_NUMBER = enum.auto()
    WDAY = enum.auto()
    WEEKNUM = enum.auto()
    MONTH = enum.auto()
    DAYNUM = enum.auto()
    MDAY = enum.auto()
    HOUR = enum.auto()
    EXTENDED_HOUR = enum.auto()
    MINUTE = enum.auto()
    NTH = enum.auto()
    YEAR = enum.auto()


def parse_opening_hours_tree(opening_hours: str):
    tree = PARSER.parse(opening_hours)
    return tree


def build_opening_hours(tree: lark.Tree) -> model.OpeningHoursExpression:
    assert tree.data == Rules.time_domain
    rules = []
    last_sep = model.RuleOperator.NORMAL

    for child in subtrees(tree):
        match child.data:
            case "rule_sequence":
                rules.append(build_rule_sequence(child, last_sep))
            case "any_rule_separator":
                last_sep = build_any_rule_separator(child)
            case _:
                raise unexpected_token(child.data, Rules.time_domain)

    return model.OpeningHoursExpression(rules)


def build_rule_sequence(
    tree: lark.Tree, operator: model.RuleOperator
) -> model.RuleSequence:
    st = SubtreeProcessor(tree, Rules.rule_sequence)

    selector_sequence_tree = st.get_subtree_opt(Rules.selector_sequence)
    rule_modifier_tree = st.get_subtree_opt(Rules.rule_modifier)

    if not selector_sequence_tree and not rule_modifier_tree:
        raise Exception("empty rule sequence")

    if rule_modifier_tree:
        kind, comment = build_rule_modifier(rule_modifier_tree)
    else:
        kind, comment = model.RuleKind.OPEN, None

    if selector_sequence_tree:
        day_selector, time_selector, extra_comment = build_selector_sequence(
            selector_sequence_tree
        )
    else:
        day_selector, time_selector, extra_comment = (
            model.DaySelector(),
            model.TimeSelector(),
            None,
        )

    comments = []
    if comment:
        comments.append(comment)
    if extra_comment:
        comments.append(extra_comment)

    return model.RuleSequence(
        day_selector, time_selector, kind, operator, UniqueSortedList(comments)
    )


def build_any_rule_separator(tree: lark.Tree) -> model.RuleOperator:
    assert tree.data == Rules.any_rule_separator
    sep = only_subtree(tree)

    match sep.data:
        case Rules.normal_rule_separator:
            return model.RuleOperator.NORMAL
        case Rules.additional_rule_separator:
            return model.RuleOperator.ADDITIONAL
        case Rules.fallback_rule_separator:
            return model.RuleOperator.FALLBACK
        case _:
            raise unexpected_token(sep.data, Rules.any_rule_separator)


def build_rule_modifier(tree: lark.Tree) -> tuple[model.RuleKind, Optional[str]]:
    st = SubtreeProcessor(tree, Rules.rule_modifier)

    st_rule_kind = st.get_subtree_opt(Rules.rule_kind)
    rule_kind = model.RuleKind.OPEN
    if st_rule_kind:
        rule_kind = build_rule_kind(st_rule_kind)

    comment = map_opt(st.get_subtree_opt(Rules.comment), build_comment)

    return rule_kind, comment


def build_comment(tree: lark.Tree) -> str:
    st = SubtreeProcessor(tree, Rules.comment)
    res = ""
    while tk := st.next_token_opt():
        match tk.type:
            case Tokens.CPART:
                res += tk.value
            case Tokens.CESCAPE:
                res += tk.value.removeprefix("\\")
            case _:
                raise unexpected_token(tk, Rules.comment)
    return res


def build_rule_kind(tree: lark.Tree) -> model.RuleKind:
    st = SubtreeProcessor(tree, Rules.rule_kind)
    token = st.next_token()
    return model.RuleKind[token.type]


def build_selector_sequence(
    tree: lark.Tree,
) -> tuple[model.DaySelector, model.TimeSelector, Optional[str]]:
    st = SubtreeProcessor(tree, Rules.selector_sequence)
    if st.get_token_opt(Tokens.ALWAYS_OPEN, 1):
        return model.DaySelector(), model.TimeSelector(), None

    wrs = st.get_subtree(Rules.wide_range_selectors)
    year, monthday, week, comment = build_wide_range_selectors(wrs)
    if srs := st.get_subtree_opt(Rules.small_range_selectors):
        weekday, time = build_small_range_selectors(srs)
    else:
        weekday, time = [], []

    return (
        model.DaySelector(year, monthday, week, weekday),
        model.TimeSelector(time),
        comment,
    )


def build_wide_range_selectors(
    tree: lark.Tree,
) -> tuple[
    list[model.day.YearRange],
    list[model.day.MonthdayRange],
    list[model.day.WeekRange],
    Optional[str],
]:
    st = SubtreeProcessor(tree, Rules.wide_range_selectors)

    year_selector = []
    monthday_selector = []
    week_selector = []
    comment = None

    for child in st.iter_subtree():
        match child.data:
            case Rules.year_selector:
                year_selector = build_year_selector(child)
            case Rules.monthday_selector:
                monthday_selector = build_monthday_selector(child)
            case Rules.week_selector:
                week_selector = build_week_selector(child)
            case Rules.comment:
                comment = build_comment(child)
            case Rules.separator_for_readability:
                pass
            case _:
                raise unexpected_token(child.data, Rules.wide_range_selectors)

    return year_selector, monthday_selector, week_selector, comment


def build_small_range_selectors(
    tree: lark.Tree,
) -> tuple[list[model.day.WeekDayRange], list[model.time.TimeSpan]]:
    st = SubtreeProcessor(tree, Rules.small_range_selectors)

    weekday_selector = []
    time_selector = []

    for child in st.iter_subtree():
        match child.data:
            case Rules.weekday_selector:
                weekday_selector.extend(build_weekday_selector(child))
            case Rules.time_selector:
                time_selector.extend(build_time_selector(child))
            case _:
                raise st.unexpected_token(child.data)

    return weekday_selector, time_selector


# Time selector


def build_time_selector(tree: lark.Tree) -> list[model.time.TimeSpan]:
    st = SubtreeProcessor(tree, Rules.time_selector)
    res = []

    for child in st.iter_subtree(Rules.timespan):
        res.append(build_timespan(child))
    return res


def build_timespan(tree: lark.Tree) -> model.time.TimeSpan:
    st = SubtreeProcessor(tree, Rules.timespan)
    start_time = build_time(st.get_subtree(Rules.time))
    end_time = map_opt(st.get_subtree_opt(Rules.extended_time), build_extended_time)
    open_end = False
    repeats = None

    tk_timespan_plus = st.get_token_opt(Tokens.PLUS)
    if tk_timespan_plus:
        open_end = True
        if end_time is None:
            end_time = model.time.MIDNIGHT_24

    if end_time is None:
        raise Exception(f"point in time ({start_time}) is not supported")

    st_repeated_time = st.get_subtree_opt(Rules.repeated_time)
    if st_repeated_time and st_repeated_time.children:
        child = st_repeated_time.children[0]
        if isinstance(child, lark.Tree) and child.data == Rules.hour_minutes:
            repeats = build_hour_minutes_as_duration(child)
        elif isinstance(child, lark.Token) and child.type == Tokens.POSITIVE_NUMBER:
            repeats = model.time.Duration(0, int(child.value))
        else:
            raise unexpected_token(child, Rules.repeated_time)

    return model.time.TimeSpan(start_time, end_time, open_end, repeats)


def build_time(tree: lark.Tree) -> model.time.TimeUnion:
    st = SubtreeProcessor(tree, Rules.time)
    child = st.next_subtree()
    match child.data:
        case Rules.hour_minutes:
            return build_hour_minutes(child)
        case Rules.variable_time:
            return build_variable_time(child)
        case _:
            raise st.unexpected_token(child.data)


def build_extended_time(tree: lark.Tree) -> model.time.TimeUnion:
    st = SubtreeProcessor(tree, Rules.extended_time)
    child = st.next_subtree()
    match child.data:
        case Rules.extended_hour_minutes:
            return build_extended_hour_minutes(child)
        case Rules.variable_time:
            return build_variable_time(child)
        case _:
            raise st.unexpected_token(child.data)


def build_variable_time(tree: lark.Tree) -> model.time.VariableTime:
    st = SubtreeProcessor(tree, Rules.variable_time)
    event = build_event(st.get_subtree(Rules.event))
    offset = 0
    st_plusminus = st.get_subtree_opt(Rules.plus_or_minus)
    if st_plusminus:
        sign = build_plus_or_minus(st_plusminus)
        diff = build_hour_minutes(st.get_subtree(Rules.hour_minutes))
        offset = diff.mins_from_midnight() * sign

    return model.time.VariableTime(event, offset)


def build_event(tree: lark.Tree) -> model.time.TimeEvent:
    st = SubtreeProcessor(tree, Rules.event)
    token = st.next_token()
    return model.time.TimeEvent[token.upper()]


# WeekDay selector


def build_weekday_selector(tree: lark.Tree) -> list[model.day.WeekDayRange]:
    st = SubtreeProcessor(tree, Rules.weekday_selector)
    res = []
    for child in st.iter_subtree():
        match child.data:
            case Rules.weekday_sequence:
                res.extend(build_weekday_sequence(child))
            case Rules.holiday_sequence:
                res.extend(build_holiday_sequence(child))
            case _:
                raise st.unexpected_token(child.data)

    return res


def build_weekday_sequence(tree: lark.Tree) -> list[model.day.WeekDayRange]:
    st = SubtreeProcessor(tree, Rules.weekday_sequence)
    res = []
    for child in st.iter_subtree(Rules.weekday_range):
        res.append(build_weekday_range(child))
    return res


def build_holiday_sequence(tree: lark.Tree) -> list[model.day.WeekDayRange]:
    st = SubtreeProcessor(tree, Rules.holiday_sequence)
    res = []
    for child in st.iter_subtree(Rules.holiday):
        res.append(build_holiday(child))
    return res


def build_weekday_range(tree: lark.Tree) -> model.day.WeekDayRange:
    st = SubtreeProcessor(tree, Rules.weekday_range)
    wd_start = model.day.Weekday[st.get_token(Tokens.WDAY)]

    wd_end = wd_start
    tk_end = st.get_token_opt(Tokens.WDAY)
    if tk_end:
        wd_end = model.day.Weekday[tk_end]

    nth_from_start = Bitfield()
    nth_from_end = Bitfield()

    while True:
        st_nth_entry = st.get_subtree_opt(Rules.nth_entry)
        if st_nth_entry is None:
            break
        sign, start, end = build_nth_entry(st_nth_entry)
        if sign == Sign.PLUS:
            nth_array = nth_from_start
        else:
            nth_array = nth_from_end
        for i in range(start, end):
            nth_array.set(i - 1, True)

    if not nth_from_start.contains(True) and not nth_from_end.contains(True):
        nth_from_start.set_all(True)
        nth_from_end.set_all(True)

    offset = 0
    st_offset = st.get_subtree_opt(Rules.day_offset)
    if st_offset:
        offset = build_day_offset(st_offset)

    return model.day.WeekDayRange(
        wd_start, wd_end, offset, nth_from_start, nth_from_end
    )


def build_holiday(tree: lark.Tree) -> model.day.HolidayRange:
    st = SubtreeProcessor(tree, Rules.holiday)
    kind = model.day.HolidayKind[st.next_token(1).value]
    offset = map_opt(st.get_subtree_opt(Rules.day_offset), build_day_offset) or 0
    return model.day.HolidayRange(kind, offset)


def build_nth_entry(tree: lark.Tree) -> tuple[Sign, int, int]:
    st = SubtreeProcessor(tree, Rules.nth_entry)
    tk_sign = st.get_token_opt(Tokens.MINUS, 1)
    if tk_sign:
        sign = Sign.MINUS
    else:
        sign = Sign.PLUS

    start = int(st.get_token(Tokens.NTH))
    end = map_opt(st.get_token_opt(Tokens.NTH), int) or start
    return sign, start, end


def build_day_offset(tree: lark.Tree) -> int:
    st = SubtreeProcessor(tree, Rules.day_offset)
    sign = build_plus_or_minus(st.get_subtree(Rules.plus_or_minus))
    number = int(st.get_token(Tokens.POSITIVE_NUMBER))
    return number * sign


# Week selector


def build_week_selector(tree: lark.Tree) -> list[model.day.WeekRange]:
    st = SubtreeProcessor(tree, Rules.week_selector)
    res = []
    for child in st.iter_subtree():
        res.append(build_week(child))

    return res


def build_week(tree: lark.Tree) -> model.day.WeekRange:
    st = SubtreeProcessor(tree, Rules.week)
    start = int(st.get_token(Tokens.WEEKNUM))
    end = map_opt(st.get_token_opt(Tokens.WEEKNUM), int) or start
    st_step = st.get_subtree_opt(Rules.week_step)  #
    step = 1
    if st_step:
        st_step = SubtreeProcessor(st_step, Rules.week_step)
        step = int(st_step.get_token(Tokens.POSITIVE_NUMBER))
    return model.day.WeekRange(start, end, step)


# Month selector


def build_monthday_selector(tree: lark.Tree) -> list[model.day.MonthdayRange]:
    st = SubtreeProcessor(tree, Rules.monthday_selector)
    res = []
    for child in st.iter_subtree(Rules.monthday_range):
        res.append(build_monthday_range(child))

    return res


def build_monthday_range(tree: lark.Tree) -> model.day.MonthdayRange:
    st = SubtreeProcessor(tree, Rules.monthday_range)
    st_monthday_range_from = st.get_subtree_opt(Rules.monthday_range_from, 1)
    if st_monthday_range_from:
        st = SubtreeProcessor(st_monthday_range_from, Rules.monthday_range_from)
        start_date = build_date_from(st.get_subtree(Rules.date_from, 1))
        start_offset = (
            map_opt(st.get_subtree_opt(Rules.date_offset, 1), build_date_offset)
            or model.day.DateOffset()
        )

        if st.get_token_opt(Tokens.PLUS, 1):
            if start_date.year is not None:
                end_date = model.day.CalendarDate(9999, model.day.Month.Dec, 31)
            else:
                end_date = model.day.CalendarDate(None, model.day.Month.Dec, 31)
        elif st_end_date := st.get_subtree_opt(Rules.date_to, 1):
            end_date = build_date_to(st_end_date, start_date)
        else:
            return model.day.DateRange(
                start_date, start_offset, start_date, start_offset
            )

        end_offset = (
            map_opt(st.get_subtree_opt(Rules.date_offset), build_date_offset)
            or model.day.DateOffset()
        )

        return model.day.DateRange(start_date, start_offset, end_date, end_offset)
    else:
        year = map_opt(st.get_token_opt(Tokens.YEAR, 1), int)
        month_start = model.day.Month[st.get_token(Tokens.MONTH, 1)]
        month_end = (
            map_opt(st.get_token_opt(Tokens.MONTH, 1), lambda x: model.day.Month[x])
            or month_start
        )
        return model.day.MonthRange(month_start, month_end, year)


def build_date_offset(tree: lark.Tree) -> model.day.DateOffset:
    st = SubtreeProcessor(tree, Rules.date_offset)

    st_pm = st.get_subtree_opt(Rules.plus_or_minus, 1)
    if st_pm:
        sign = build_plus_or_minus(st_pm)
        if sign == Sign.PLUS:
            kind = model.day.WeekDayOffsetKind.NEXT
        else:
            kind = model.day.WeekDayOffsetKind.PREV
        wday = model.day.Weekday[st.get_token(Tokens.WDAY, 1)]
        wday_offset = model.day.WeekDayOffset(kind, wday)
    else:
        wday_offset = model.day.WeekDayOffset()

    day_offset = map_opt(st.get_subtree_opt(Rules.day_offset), build_day_offset) or 0
    return model.day.DateOffset(wday_offset, day_offset)


def build_date_from(tree: lark.Tree) -> model.day.DateUnion:
    st = SubtreeProcessor(tree, Rules.date_from)
    return __build_date_from(st)


def __build_date_from(st: "SubtreeProcessor") -> model.day.DateUnion:
    year = map_opt(st.get_token_opt(Tokens.YEAR, 1), int)

    st_variable_date = st.get_subtree_opt(Rules.variable_date)
    if st_variable_date:
        return build_variable_date(st_variable_date, year)

    month = model.day.Month[st.get_token(Tokens.MONTH, 1)]
    tk_day = st.next_token()
    match tk_day.type:
        case Tokens.DAYNUM:
            day = int(tk_day.value)
            return model.day.CalendarDate(year, month, day)
        # TODO: unexpected
        # case Tokens.WDAY:
        #     wday = model.day.Weekday[tk_day.value]
        #     nth = None
        #     tk_nth = st.next_token_opt(1)
        #     if tk_nth:
        #         minus = tk_nth.type == Tokens.MINUS
        #         if minus:
        #             tk_nth = st.next_token(1)
        #         nth = int(tk_nth.value)
        #     raise NotImplementedError(
        #         f"date_from based on weekday not implemented; wday={wday} nth={nth}"
        #     )
        case _:
            raise st.unexpected_token(tk_day.type)


def build_date_to(
    tree: lark.Tree, date_from: model.day.DateUnion
) -> model.day.DateUnion:
    st = SubtreeProcessor(tree, Rules.date_to)
    tk_day = st.get_token_opt(Tokens.DAYNUM, 1)
    if tk_day:
        daynum = int(tk_day)
        if isinstance(date_from, model.day.VariableDate):
            raise Exception(
                f"Variable date ({date_from.kind}) followed by a day number"
            )

        month = date_from.month
        year = date_from.year

        if date_from.day > daynum:
            month = month.next()
            if month == model.day.Month.Jan and year is not None:
                year += 1
        return model.day.CalendarDate(year, month, daynum)

    else:
        return __build_date_from(SubtreeProcessor(st.get_subtree(Rules.date_from)))


def build_variable_date(tree: lark.Tree, year: Optional[int]) -> model.day.VariableDate:
    st = SubtreeProcessor(tree, Rules.variable_date)
    kind = model.day.VariableDateKind[st.next_token(1).type]
    return model.day.VariableDate(kind, year)


# Year selector


def build_year_selector(tree: lark.Tree) -> list[model.day.YearRange]:
    st = SubtreeProcessor(tree, Rules.year_selector)
    res = []
    for child in st.iter_subtree(Rules.year_range):
        res.append(build_year_range(child))
    return res


def build_year_range(tree: lark.Tree) -> model.day.YearRange:
    st = SubtreeProcessor(tree, Rules.year_range)
    year_start = int(st.get_token(Tokens.YEAR, 1))
    year_end = year_start
    step = 1

    nt = st.next_token_opt(1)
    if nt:
        match nt.type:
            case Tokens.YEAR:
                year_end = int(nt.value)
                st_year_step = st.get_subtree_opt(Rules.year_step, 1)
                if st_year_step:
                    st_year_step = SubtreeProcessor(st_year_step, Rules.year_step)
                    step = int(st_year_step.get_token(Tokens.POSITIVE_NUMBER))
            case Tokens.PLUS:
                year_end = None
            case _:
                raise st.unexpected_token(nt.type)

    return model.day.YearRange(year_start, year_end, step)


# Basic elements


def build_plus_or_minus(tree: lark.Tree) -> Sign:
    st = SubtreeProcessor(tree)
    token = st.next_token()
    return Sign[token.type]


def build_hour_minutes(tree: lark.Tree) -> model.time.ExtendedTime:
    st = SubtreeProcessor(tree, Rules.hour_minutes)
    hour = int(st.get_token(Tokens.HOUR))
    minute = int(st.get_token(Tokens.MINUTE))
    return model.time.ExtendedTime(hour, minute)


def build_extended_hour_minutes(tree: lark.Tree) -> model.time.ExtendedTime:
    st = SubtreeProcessor(tree, Rules.extended_hour_minutes)
    hour = int(st.get_token(Tokens.EXTENDED_HOUR))
    minute = int(st.get_token(Tokens.MINUTE))
    return model.time.ExtendedTime(hour, minute)


def build_hour_minutes_as_duration(tree: lark.Tree) -> model.time.Duration:
    hm = build_hour_minutes(tree)
    return model.time.Duration(hm.hour, hm.minute)


# utils


def subtrees(tree: lark.Tree) -> Generator[lark.Tree]:
    for child in tree.children:
        if isinstance(child, lark.Tree):
            yield child


def get_subtree(tree: lark.Tree, n: int) -> lark.Tree:
    subtree = get_subtree_opt(tree, n)
    if subtree is None:
        raise Exception(
            f"could not get child {n} of {tree.data}; len={len(tree.children)}"
        )
    return subtree


def get_subtree_opt(tree: lark.Tree, n: int) -> Optional[lark.Tree]:
    if len(tree.children) <= n:
        return None
    child = tree.children[n]
    if not isinstance(child, lark.Tree):
        if isinstance(child, lark.Token):
            print("token", repr(child))
        raise Exception(f"{tree.data}: child {n} is not a tree; {type(child)}")
    return child


def only_subtree(tree: lark.Tree) -> lark.Tree:
    if len(tree.children) != 1:
        raise Exception(f"{tree.data} has {len(tree.children)}, expected 1")
    return get_subtree(tree, 0)


def unexpected_token(token: str | lark.Tree | lark.Token, parent: str) -> Exception:
    if isinstance(token, lark.Tree):
        token_name = token.data
    elif isinstance(token, lark.Token):
        token_name = token.type
    else:
        token_name = str(token)
    return Exception(f"Grammar error: found {token_name} inside of {parent}")


class SubtreeProcessor:
    def __init__(self, tree: lark.Tree, expect: Optional[Rules] = None) -> None:
        if expect is not None and tree.data != expect:
            raise Exception(f"Grammar error: expected {expect}; got {tree.data}")
        self.tree = tree
        self.offset = 0

    def __get_max(self, peek: int):
        if peek > 0:
            return min(self.offset + peek, len(self.tree.children))
        return len(self.tree.children)

    def get_subtree_opt(self, rule: Rules, peek: int = 0) -> Optional[lark.Tree]:
        i = self.offset
        while i < self.__get_max(peek):
            child = self.tree.children[i]
            i += 1
            if isinstance(child, lark.Tree) and child.data == rule:
                self.offset = i
                return child

    def get_subtree(self, rule: Rules, peek: int = 0) -> lark.Tree:
        child = self.get_subtree_opt(rule, peek)
        if child is None:
            raise Exception(f"{self.tree.data} has no {rule}")
        return child

    def iter_subtree(self, rule: Optional[Rules] = None) -> Generator[lark.Tree]:
        i = self.offset
        while i < len(self.tree.children):
            child = self.tree.children[i]
            i += 1
            if isinstance(child, lark.Tree) and (
                (rule is None and not Rules.should_skip(child.data))
                or child.data == rule
            ):
                self.offset = i
                yield child

    def get_token_opt(self, token: Tokens, peek: int = 0) -> Optional[str]:
        i = self.offset
        while i < self.__get_max(peek):
            child = self.tree.children[i]
            i += 1
            if isinstance(child, lark.Token) and child.type == token:
                self.offset = i
                return child.value

    def get_token(self, token: Tokens, peek: int = 0) -> str:
        child = self.get_token_opt(token, peek)
        if child is None:
            raise Exception(f"{self.tree.data} has no {token}")
        return child

    def next_token_opt(self, peek: int = 0) -> Optional[lark.Token]:
        i = self.offset
        while i < self.__get_max(peek):
            child = self.tree.children[i]
            i += 1
            if isinstance(child, lark.Token):
                self.offset = i
                return child

    def next_token(self, peek: int = 0) -> lark.Token:
        token = self.next_token_opt(peek)
        if token is None:
            raise Exception(f"{self.tree.data} is empty")
        return token

    def next_subtree_opt(self, peek: int = 0) -> Optional[lark.Tree]:
        i = self.offset
        while i < self.__get_max(peek):
            child = self.tree.children[i]
            i += 1
            if isinstance(child, lark.Tree) and not Rules.should_skip(child.data):
                self.offset = i
                return child

    def next_subtree(self, peek: int = 0) -> lark.Tree:
        token = self.next_subtree_opt(peek)
        if token is None:
            raise Exception(f"{self.tree.data} is empty")
        return token

    def unexpected_token(self, token: Optional[str]) -> Exception:
        if token is None:
            return Exception(f"Grammar error: {self.tree.data} empty")
        return Exception(f"Grammar error: found {token} inside of {self.tree.data}")

    def __repr__(self) -> str:
        return f"{self.tree.data} {self.tree.children}"
