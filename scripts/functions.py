import json
import os
import re
import subprocess
import sys

from typing import (
    Match,
    Optional,
    Pattern,
)


StringList = dict[str, dict[str, list[str]]]


def read_config(params: list[str]) -> list[str]:
    # Get absolute path of the repository's root from the script location
    root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    config_file = os.path.join(root_folder, "config", "config")

    # Abort if config file is missing
    if not os.path.exists(config_file):
        sys.exit("ERROR: config file is missing")

    # Read all available paths in the config file
    paths: dict[str, str] = {}
    with open(config_file, "r") as cfg_file:
        for line in cfg_file:
            line = line.strip()
            # Ignore comments and empty lines
            if line == "" or line.startswith("#"):
                continue
            paths[line.split("=")[0]] = line.split("=")[1].strip('"')

    results: list[str] = []
    for param in params:
        if param not in paths:
            sys.exit("{} is not defined in the config file".format(param))
        else:
            if not os.path.exists(paths[param]):
                sys.exit(
                    "Path defined for {} ({}) does not exist".format(
                        param, paths[param]
                    )
                )
        results.append(paths[param])

    return results


def store_completion(
    string_list: dict[str, dict[str, list[str]]],
    version: str,
    locales: list[str],
    product: str,
) -> None:
    completion: dict[str, float] = {}
    stats_path = get_stats_path()
    source_stats: int = sum(
        len(values.get("source", [])) for values in string_list.values()
    )

    for locale in locales:
        if locale == "source":
            continue
        locale_stats: int = sum(
            len(values.get(locale, [])) for values in string_list.values()
        )
        completion[locale] = round((locale_stats / source_stats), 4)

    for locale, percentage in completion.items():
        print(f"{locale}: {round(percentage * 100, 2)}%")

    output_file: str = os.path.join(
        stats_path, f"{product}_{version.replace('.', '_')}.json"
    )
    with open(output_file, "w") as f:
        json.dump(completion, f)


def get_firefox_releases(repo_path: str) -> dict[str, str]:
    try:
        print("Extracting tags from repository")
        result = subprocess.run(
            ["git", "-C", repo_path, "tag", "-l", "FIREFOX_*"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Error running git tag: {result.stderr}")

        # Filter output using regex
        output: str = result.stdout
        tag_re: Pattern[str] = re.compile(r"(FIREFOX_([0-9_]*)_RELEASE)")
        filtered_lines: list[str] = [
            line for line in output.splitlines() if tag_re.search(line)
        ]

        # Process the filtered lines to extract version
        releases: dict[str, str] = {}
        for line in filtered_lines:
            match: Optional[Match[str]] = tag_re.search(line)
            if match:
                tag_name: str = match.group(1)
                version: str = match.group(2).replace("_", ".")
                releases[version] = tag_name

        return releases
    except Exception as e:
        print(f"An error occurred: {e}")
        return {}


def get_stats_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "stats"))


def update_git_repository(changeset: str, repo_path: str) -> None:
    try:
        print(f"Updating git repository to changeset: {changeset}")
        result = subprocess.run(
            ["git", "-C", repo_path, "checkout", changeset],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error git updating repository to {changeset}: {result.stderr}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_json_files(product: str) -> list[str]:
    # List all JSON files starting with the product name
    stats_path = get_stats_path()
    json_files = [
        f
        for f in os.listdir(stats_path)
        if f.startswith(product) and f.endswith(".json")
    ]
    json_files.sort()

    return json_files


def get_version_from_filename(filename: str) -> tuple[str, str]:
    version_re = re.compile(r"_([\d_]*)")
    match: Optional[Match[str]] = version_re.search(filename)
    assert match is not None
    version: str = match.group(1).replace("_", ".")
    major_version: str = version.split(".")[0]

    return version, major_version
