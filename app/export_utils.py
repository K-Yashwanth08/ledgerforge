"""Shared helpers for authenticated CSV exports."""
import csv
from datetime import date
from io import StringIO

from fastapi import HTTPException
from fastapi.responses import StreamingResponse


def validate_date_filters(start_date: date | None, end_date: date | None,
                          since: date | None) -> None:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    if since and (start_date or end_date):
        raise HTTPException(422, "since cannot be combined with start_date or end_date")


def csv_download(filename: str, columns: tuple[str, ...], rows) -> StreamingResponse:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, (date,)):
                value = value.isoformat()
            elif value is None:
                value = ""
            # Prevent text cells from being interpreted as spreadsheet formulas.
            if isinstance(value, str) and value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
