#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Extract completion statistics for product over time, store them as CSV

python extract_product.py --path path_to_mozilla_firefox_clone
"""

from __future__ import annotations

import argparse
import csv
import json
import os

from typing import TypedDict

from functions import get_json_files, get_stats_path, get_version_from_filename


class BuildEntry(TypedDict):
    version: str
    completion: dict[str, float | int]


def main() -> None:
    cl_parser = argparse.ArgumentParser()
    cl_parser.add_argument(
        "--product",
        required=True,
        dest="product",
        help="Product name",
        choices=["fenix", "firefox"],
    )
    args = cl_parser.parse_args()

    product: str = args.product
    stats_path = get_stats_path()

    # List all JSON files starting with the product name
    json_files = get_json_files(product)

    raw_build_data: dict[str, BuildEntry] = {}
    locales: list[str] = []
    for json_file in json_files:
        with open(os.path.join(stats_path, json_file), "r") as f:
            data: dict[str, float | int] = json.load(f)
            version, major_version = get_version_from_filename(json_file)
            for locale, percentage in data.items():
                if major_version not in raw_build_data:
                    raw_build_data[major_version] = {
                        "version": version,
                        "completion": {},
                    }
                if locale not in locales:
                    locales.append(locale)
                raw_build_data[major_version]["completion"][locale] = percentage
    locales.sort()

    # Sort the dictionary by major version
    build_data: dict[str, BuildEntry] = {
        k: raw_build_data[k] for k in sorted(raw_build_data, key=lambda x: int(x))
    }

    csv_path = os.path.join(stats_path, f"{product}_locales.csv")
    with open(csv_path, "w") as csv_file:
        fieldnames: list[str] = ["Version", "Major version"] + locales
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, lineterminator="\n")

        writer.writeheader()
        for major_version, version_data in build_data.items():
            row: dict[str, object] = {
                "Version": f"'{version_data['version']}",  # Force string in Sheets
                "Major version": int(major_version),
            }
            row.update(version_data["completion"])
            writer.writerow(row)


if __name__ == "__main__":
    main()
