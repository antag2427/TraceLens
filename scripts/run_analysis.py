"""Run the TraceLens analysis pipeline against a running instance."""
import argparse
import json
from urllib.request import Request, urlopen

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    with urlopen(Request(args.url.rstrip("/") + "/api/v1/analysis/run", method="POST"), timeout=180) as response:
        print(json.dumps(json.load(response), indent=2))
