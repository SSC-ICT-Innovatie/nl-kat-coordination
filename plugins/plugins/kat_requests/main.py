# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests>=2.32.5",
#     "requests-har>=1.2.0",
# ]
# ///

import argparse
import json

import requests
from requests_har.har import HarDict


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("hostnames", nargs="*")
    args = parser.parse_args()

    har_dict = HarDict()

    # todo: perhaps try both http and https schemes?
    for hostname in args.hostnames:
        try:
            requests.get(f"http://{hostname}", hooks={"response": har_dict.on_response})
        except:
            pass
        else:
            print(json.dumps(har_dict, indent=4))


if __name__ == "__main__":
    main()
