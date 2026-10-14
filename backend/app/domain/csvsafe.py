"""CSV export helpers that block spreadsheet formula injection (a product title like '=HYPERLINK(...)')."""

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, float):
        return f"{value:.2f}" if abs(value) < 1e15 else str(value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    # A leading quote makes Excel/Sheets treat the cell as text. Plain negative numbers are left alone.
    if text.startswith(_DANGEROUS) and not _looks_numeric(text):
        return "'" + text
    return text


def _looks_numeric(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def to_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow([cell(h) for h in header])
    for row in rows:
        writer.writerow([cell(v) for v in row])
    return out.getvalue()
