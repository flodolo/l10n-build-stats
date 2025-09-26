#!/usr/bin/env python3

"""
Upload a local CSV to a Google Sheet worksheet and
resize/update a named range (same name as the sheet) to cover the full data.
"""

from __future__ import annotations

import configparser
import csv
import os

from typing import Any, Mapping, Optional, TypedDict

import gspread

from gspread.utils import ValueInputOption


class ServiceAccountDict(TypedDict):
    type: str
    project_id: str
    private_key_id: str
    private_key: str
    client_id: str
    client_email: str
    auth_uri: str
    token_uri: str
    auth_provider_x509_cert_url: str
    client_x509_cert_url: str


def read_config(root_path: str) -> dict[str, str]:
    # Read config file in the parent folder
    config_file = os.path.join(
        root_path,
        "api_config.env",
    )
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_file)

    return dict(config.items("GDOCS"))


def read_csv(csv_path: str) -> list[list[str]]:
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        data: list[list[str]] = [row for row in reader]
    # Guarantee at least a 1x1 range for empty files
    return data if data else [[""]]


def a1_from_rc(row: int, col: int) -> str:
    """Convert 1-based row/col to A1 notation (e.g., 1,1 -> A1)."""
    letters = ""
    n = col
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def main() -> None:
    root_path = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    )

    config: dict[str, str] = read_config(root_path)
    credentials: ServiceAccountDict = {
        "type": "service_account",
        "project_id": config["gspread_project_id"],
        "private_key_id": config["gspread_private_key_id"],
        "private_key": config["gspread_private_key"].replace("\\n", "\n"),
        "client_id": config["gspread_client_id"],
        "client_email": config["gspread_client_email"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": config["client_x509_cert_url"],
    }

    connection: gspread.Client = gspread.service_account_from_dict(credentials)
    sh: gspread.Spreadsheet = connection.open_by_key(config["spreadsheet_key"])

    for target_name in ("raw_firefox", "raw_fenix"):
        csv_path = os.path.join(
            root_path,
            "stats",
            target_name.removeprefix("raw_") + "_locales.csv",
        )
        data: list[list[str]] = read_csv(csv_path)
        rows = len(data)
        cols = max(len(r) for r in data) if data else 1

        # Ensure worksheet exists with sufficient size
        try:
            ws: gspread.Worksheet = sh.worksheet(target_name)
            ws.resize(rows=rows, cols=cols)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(
                title=target_name, rows=max(rows, 1), cols=max(cols, 1)
            )

        # Write data starting at A1
        ws.update(data, "A1", value_input_option=ValueInputOption.user_entered)

        # Compute end A1 and update or add the named range on the spreadsheet
        end_a1: str = a1_from_rc(rows, cols)
        sheet_id: int = ws.id
        range: dict[str, int] = {
            "sheetId": sheet_id,
            "startRowIndex": 0,
            "startColumnIndex": 0,
            "endRowIndex": rows,
            "endColumnIndex": cols,
        }

        # Discover existing named ranges to get the ID (if present)
        meta: Mapping[str, Any] = sh.fetch_sheet_metadata()
        named_ranges: list[Mapping[str, Any]] = meta.get("namedRanges", []) or []
        target: Optional[Mapping[str, Any]] = next(
            (nr for nr in named_ranges if nr.get("name") == target_name), None
        )

        requests: list[dict[str, Any]] = []
        if target and target.get("namedRangeId"):
            requests.append(
                {
                    "updateNamedRange": {
                        "namedRange": {
                            "namedRangeId": target["namedRangeId"],
                            "name": target_name,
                            "range": range,
                        },
                        "fields": "range",
                    }
                }
            )
        else:
            requests.append(
                {
                    "addNamedRange": {
                        "namedRange": {
                            "name": target_name,
                            "range": range,
                        }
                    }
                }
            )

        sh.batch_update({"requests": requests})

        print(f"Uploaded {rows} rows x {cols} cols to sheet '{target_name}'.")
        print(f"Named range '{target_name}' now refers to A1:{end_a1}.")


if __name__ == "__main__":
    main()
