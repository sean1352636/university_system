"""Save a table as a new Google Sheet in the signed-in user's Drive.

Uses the Sheets API v4 via ``google-api-python-client`` with an OAuth2
"Desktop app" client file (``PLATFORM_GOOGLE_OAUTH_CLIENT_FILE``). The first
export opens a browser for sign-in; the token is cached owner-only in
``PLATFORM_GOOGLE_SHEETS_TOKEN_FILE`` and refreshed automatically after that.

The ``drive.file`` scope only lets the app see sheets it created itself.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Sequence

from education_system.paths import (
    PLATFORM_GOOGLE_OAUTH_CLIENT_FILE,
    PLATFORM_GOOGLE_SHEETS_TOKEN_FILE,
)

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleSheetsNotConfigured(RuntimeError):
    """No OAuth client file, so there is no way to sign in to Google."""


def setup_instructions() -> str:
    return (
        "Google Sheets export needs a Google OAuth client file.\n\n"
        "1. In Google Cloud Console, enable the Google Sheets API.\n"
        "2. Create an OAuth client ID of type \"Desktop app\".\n"
        "3. Download its JSON and save it as:\n"
        f"   {PLATFORM_GOOGLE_OAUTH_CLIENT_FILE}\n\n"
        "The first export opens your browser to sign in; later exports reuse it."
    )


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if PLATFORM_GOOGLE_SHEETS_TOKEN_FILE.is_file():
        creds = Credentials.from_authorized_user_file(
            str(PLATFORM_GOOGLE_SHEETS_TOKEN_FILE), _SCOPES)

    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            # Revoked or expired refresh token: fall through to a fresh sign-in.
            logger.info("Google token refresh failed; signing in again", exc_info=True)
            creds = None

    if not creds or not creds.valid:
        if not PLATFORM_GOOGLE_OAUTH_CLIENT_FILE.is_file():
            raise GoogleSheetsNotConfigured(setup_instructions())
        flow = InstalledAppFlow.from_client_secrets_file(
            str(PLATFORM_GOOGLE_OAUTH_CLIENT_FILE), _SCOPES)
        creds = flow.run_local_server(port=0)

    PLATFORM_GOOGLE_SHEETS_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(PLATFORM_GOOGLE_SHEETS_TOKEN_FILE,
                 os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(creds.to_json())
    return creds


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def export_table(title: str, headers: Sequence[str], rows: Sequence[Sequence[Any]],
                 *, wrap_columns: Sequence[int] = ()) -> str:
    """Create a spreadsheet holding ``headers`` + ``rows``; return its URL.

    ``wrap_columns`` are 0-based column indexes whose cells hold multi-line
    text (wrapped and top-aligned so every line shows).
    """
    from googleapiclient.discovery import build

    service = build("sheets", "v4", credentials=_credentials(), cache_discovery=False)
    sheets = service.spreadsheets()

    created = sheets.create(
        body={"properties": {"title": title},
              "sheets": [{"properties": {"title": "Students",
                                         "gridProperties": {"frozenRowCount": 1}}}]},
        fields="spreadsheetId,spreadsheetUrl,sheets.properties.sheetId",
    ).execute()
    spreadsheet_id = created["spreadsheetId"]
    sheet_id = created["sheets"][0]["properties"]["sheetId"]

    values = [list(headers)] + [[_cell(v) for v in row] for row in rows]
    # RAW keeps values literal: a cell starting with "=" is never run as a formula.
    sheets.values().update(
        spreadsheetId=spreadsheet_id, range="Students!A1",
        valueInputOption="RAW", body={"values": values},
    ).execute()

    requests: list[dict] = [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                           "verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat(textFormat,verticalAlignment)",
        }},
        {"autoResizeDimensions": {"dimensions": {
            "sheetId": sheet_id, "dimension": "COLUMNS",
            "startIndex": 0, "endIndex": len(headers)}}},
    ]
    for col in wrap_columns:
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1,
                      "startColumnIndex": col, "endColumnIndex": col + 1},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP",
                                           "verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)",
        }})
        # Auto-resize would stretch a wrapped column to its longest line.
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": col, "endIndex": col + 1},
            "properties": {"pixelSize": 320}, "fields": "pixelSize"}})
    sheets.batchUpdate(spreadsheetId=spreadsheet_id,
                       body={"requests": requests}).execute()

    return created["spreadsheetUrl"]
