"""Run timestamps, in the two forms sillon needs.

`date` has always been `"%Y-%m-%d-%H:%M:%S"` in local time with no offset. It
reads well in a table and sorts correctly as a string *within one machine*, so
nothing about it is wrong until two machines' runs end up in one project —
then a 14:00 logged in Paris sorts after a 13:00 logged in Boston that
actually happened four hours later. Chronology, `--older-than` and "last
activity" all quietly lie.

So a run now also records `started_at`: the same instant as ISO-8601 with an
offset, which is unambiguous and still sorts as a string once normalised to a
common form. `date` stays exactly as it was, because it is what people read
and what every existing project holds.
"""

from datetime import datetime, timezone

__all__ = ["DATE_FORMAT", "now_pair", "to_aware", "sort_key", "parse_bound"]

DATE_FORMAT = "%Y-%m-%d-%H:%M:%S"


def now_pair() -> tuple:
    """`(date, started_at)` for this instant.

    Returns:
        tuple[str, str]: The display string and the offset-aware ISO form.
    """
    now = datetime.now().astimezone()
    return now.strftime(DATE_FORMAT), now.isoformat(timespec="seconds")


def to_aware(date_str: str, started_at: str = None):
    """The instant a run started, as an aware datetime, or None.

    Prefers `started_at`. Falls back to interpreting the naive `date` in this
    machine's local timezone — using the offset that was in force *on that
    date*, so a summer run keeps its summer offset rather than today's.

    Args:
        date_str (str): The stored `date`, in `DATE_FORMAT`.
        started_at (str, optional): The stored ISO-8601 timestamp.

    Returns:
        datetime | None: An aware datetime, or None if neither parses.
    """
    if started_at:
        try:
            parsed = datetime.fromisoformat(str(started_at))
            if parsed.tzinfo is None:
                parsed = parsed.astimezone()
            return parsed
        except (ValueError, TypeError):
            pass

    try:
        return datetime.strptime(str(date_str), DATE_FORMAT).astimezone()
    except (ValueError, TypeError):
        return None


def sort_key(date_str: str, started_at: str = None) -> str:
    """A chronological sort key that is correct across timezones.

    Runs whose timestamp cannot be parsed sort first rather than raising, the
    same way the plain `date` sort has always treated a missing value.
    """
    moment = to_aware(date_str, started_at)
    if moment is None:
        return ""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def parse_bound(value) -> "datetime | None":
    """A user-supplied date bound (`--before` / `--after`), as an aware datetime.

    Accepts a full `DATE_FORMAT` stamp, an ISO-8601 string, or a bare
    `YYYY-MM-DD`. A bare date is taken as local midnight, which is what
    someone typing `--after 2026-01-01` means.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.astimezone()

    text = str(value).strip()
    for parse in (
        lambda t: datetime.strptime(t, DATE_FORMAT),
        datetime.fromisoformat,
        lambda t: datetime.strptime(t, "%Y-%m-%d"),
    ):
        try:
            parsed = parse(text)
        except (ValueError, TypeError):
            continue
        return parsed if parsed.tzinfo else parsed.astimezone()
    return None
