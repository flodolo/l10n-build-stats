#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Extract completion statistics for Firefox for Android (fenix)

python fenix_stats.py --path path_to_mozilla_firefox_clone
"""

from functions import (
    read_config,
    update_git_repository,
)
from moz.l10n.paths import L10nConfigPaths, get_android_locale
import xml.etree.ElementTree as ET
import argparse
import os
import sys


def parse_XML_file(file_path, source=False, version=None):
    """
    Parse the strings.xml file and return a list of string IDs.

    If it's the source locale, exclude strings with
    tools:ignore="UnusedResources", and strings where moz:removedIn is set
    to a version smaller than the version being checked.
    """
    string_ids = []

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        for string in root.findall("string"):
            string_id = string.attrib["name"]
            if source:
                tools_ignore = string.attrib.get(
                    "{http://schemas.android.com/tools}ignore", ""
                )

                removed_in = string.attrib.get(
                    "{http://mozac.org/tools}removedIn", None
                )
                removed = False
                if removed_in and int(removed_in) < int(version.split(".")[0]):
                    print(
                        f"Ignoring {string_id} because removed in version {removed_in}"
                    )
                    removed = True

                if "UnusedResources" not in tools_ignore.split(",") and not removed:
                    string_ids.append(string_id)
            else:
                string_ids.append(string_id)
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    return string_ids


def extract_string_list(source_path, version):
    toml_paths = {
        "fenix": os.path.join(source_path, "mobile", "android", "fenix", "l10n.toml"),
        "android-components": os.path.join(
            source_path, "mobile", "android", "android-components", "l10n.toml"
        ),
    }

    string_list = {}
    locale = "ro"
    for product, toml_path in toml_paths.items():
        if not os.path.exists(toml_path):
            sys.exit(f"Missing config file {os.path.relpath(toml_path, source_path)}.")

        project_config_paths = L10nConfigPaths(
            toml_path, locale_map={"android_locale": get_android_locale}
        )
        basedir = project_config_paths.base
        reference_files = [ref_path for ref_path in project_config_paths.ref_paths]

        for reference_file in reference_files:
            key = f"{product}:{os.path.relpath(reference_file, basedir)}"
            string_list[key] = {
                "source": parse_XML_file(reference_file, source=True, version=version),
            }

        all_files = [
            (ref_path, tgt_path)
            for (ref_path, tgt_path), _ in project_config_paths.all().items()
        ]
        locale_files = [
            (ref_path, tgt_path)
            for (ref_path, raw_tgt_path) in all_files
            if os.path.exists(
                tgt_path := project_config_paths.format_target_path(
                    raw_tgt_path, locale
                )
            )
        ]

        for source_file, l10n_file in locale_files:
            # Ignore missing files for locale
            if not os.path.exists(l10n_file):
                continue
            key = f"{product}:{os.path.relpath(source_file, basedir)}"
            if key not in string_list:
                print(
                    f"Extra file {os.path.relpath(l10n_file, basedir)} in {locale}"
                )
                continue
            # Remove extra strings not available in source
            string_list[key][locale] = [
                id
                for id in parse_XML_file(l10n_file)
                if id in string_list[key]["source"]
            ]

    return string_list


def main():
    cl_parser = argparse.ArgumentParser()
    cl_parser.add_argument(
        "--version",
        required=True,
        dest="version",
        help="Version of Firefox to check",
    )
    args = cl_parser.parse_args()

    tag = f"FIREFOX-ANDROID_142_0{args.version}_RELEASE"
    [source_path] = read_config(["mozilla_firefox_path"])

    # Update the repository to the tag
    update_git_repository(tag, source_path)

    # Extract list statistics
    string_list = extract_string_list(source_path, "142")

    source_stats = sum(len(values.get("source", [])) for values in string_list.values())
    locale_stats = sum(
        len(values.get("ro", [])) for values in string_list.values()
    )
    completion = round((locale_stats / source_stats), 4)
    print(f"ro: {round(completion * 100, 2)}%")

if __name__ == "__main__":
    main()
