"""Load the bundled TraceLens dataset into a running instance."""
import argparse
import json
from urllib.request import Request, urlopen

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    with urlopen(Request(args.url.rstrip("/") + "/api/v1/logs/demo", method="POST"), timeout=120) as response:
        print(json.dumps(json.load(response), indent=2))
