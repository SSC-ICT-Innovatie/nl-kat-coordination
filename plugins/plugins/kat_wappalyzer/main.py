# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx>=0.28.1",
#     "tanimachi>=0.0.6",
# ]
# ///

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
from tanimachi import Categories, Fingerprints, Groups, Har, Wappalyzer
from tanimachi.wappalyzer import Detection

BASE_DIR = Path(__file__).parent

fingerprints = Fingerprints.model_validate_pattern(BASE_DIR.joinpath("technologies/*.json").as_posix())
categories = Categories.model_validate_file(BASE_DIR / "categories.json")
groups = Groups.model_validate_file(BASE_DIR / "groups.json")


def download_file(file_id: str) -> bytes:
    token = os.getenv("OPENKAT_TOKEN")
    if not token:
        raise Exception("No OPENKAT_TOKEN env variable")

    base_url = os.getenv("OPENKAT_API")
    if not base_url:
        raise Exception("No OPENKAT_API env variable")

    headers = {"Authorization": "Token " + token}
    client = httpx.Client(base_url=base_url, headers=headers)

    res = client.get(f"/file/{file_id}/download/").raise_for_status()

    return res.content


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()

    for file in args.files:
        contents = download_file(file)
        data = json.loads(contents)

        # Traverse and fix timezone-naive expires in cookies
        for entry in data.get("log", {}).get("entries", []):
            for cookie in entry.get("response", {}).get("cookies", []):
                if "expires" in cookie and cookie["expires"]:
                    # Parse naive datetime and make it UTC-aware
                    naive_dt = datetime.fromisoformat(cookie["expires"])
                    aware_dt = naive_dt.replace(tzinfo=UTC)
                    cookie["expires"] = aware_dt.isoformat()

        har = Har.model_validate(data)

        wappalyzer = Wappalyzer(fingerprints, categories=categories, groups=groups)
        detections: list[Detection] = wappalyzer.analyze(har)

        for detection in detections:
            print(detection.model_dump_json(indent=4))  # noqa


if __name__ == "__main__":
    main()
