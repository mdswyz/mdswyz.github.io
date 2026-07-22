import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scholarly import ProxyGenerator, scholarly


SECTIONS = ["basics", "indices", "counts"]


def query_author(scholar_id):
    author = scholarly.search_author_id(scholar_id)
    return scholarly.fill(author, sections=SECTIONS)


def fetch_author(scholar_id):
    try:
        return query_author(scholar_id)
    except Exception as error:
        last_error = error
        print(f"Direct Google Scholar request failed: {error}", file=sys.stderr)

    proxy = ProxyGenerator()
    if not proxy.FreeProxies():
        raise RuntimeError("No working proxy was available") from last_error

    scholarly.use_proxy(proxy)
    for attempt in range(1, 4):
        try:
            return query_author(scholar_id)
        except Exception as error:
            last_error = error
            print(f"Proxy attempt {attempt} failed: {error}", file=sys.stderr)
            if attempt < 3:
                time.sleep(attempt * 5)

    raise RuntimeError("Google Scholar could not be reached after retries") from last_error


author = fetch_author(os.environ["GOOGLE_SCHOLAR_ID"])
if "citedby" not in author:
    raise RuntimeError("Google Scholar returned no citation count")

author["updated"] = datetime.now(timezone.utc).isoformat()
publications = author.get("publications", [])
author["publications"] = {
    publication["author_pub_id"]: publication
    for publication in publications
    if "author_pub_id" in publication
}

print(json.dumps(author, indent=2, ensure_ascii=False))

results_dir = Path(__file__).resolve().parent / "results"
results_dir.mkdir(exist_ok=True)

with (results_dir / "gs_data.json").open("w", encoding="utf-8") as outfile:
    json.dump(author, outfile, ensure_ascii=False)

shieldio_data = {
    "schemaVersion": 1,
    "label": "citations",
    "message": str(author["citedby"]),
}
with (results_dir / "gs_data_shieldsio.json").open("w", encoding="utf-8") as outfile:
    json.dump(shieldio_data, outfile, ensure_ascii=False)
