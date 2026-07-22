import json
import os
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ScholarMetricsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture_metric = False
        self.metrics = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = attributes.get("class", "").split()
        if tag == "td" and "gsc_rsb_std" in classes:
            self.capture_metric = True

    def handle_endtag(self, tag):
        if tag == "td":
            self.capture_metric = False

    def handle_data(self, data):
        if self.capture_metric and data.strip():
            self.metrics.append(data.strip())


def fetch_direct_citations(scholar_id):
    query = urlencode({"user": scholar_id, "hl": "en"})
    request = Request(
        f"https://scholar.google.com/citations?{query}",
        headers={
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0 Safari/537.36"
            ),
        },
    )

    with urlopen(request, timeout=25) as response:
        html = response.read().decode("utf-8", errors="replace")

    if 'id="gsc_prf_in"' not in html:
        raise RuntimeError("Google Scholar returned a blocked or unexpected page")

    parser = ScholarMetricsParser()
    parser.feed(html)
    if not parser.metrics:
        raise RuntimeError("Google Scholar returned no citation metrics")

    return int(parser.metrics[0].replace(",", ""))


def fetch_serpapi_citations(scholar_id, api_key):
    query = urlencode(
        {
            "engine": "google_scholar_author",
            "author_id": scholar_id,
            "hl": "en",
            "api_key": api_key,
        }
    )
    request = Request(
        f"https://serpapi.com/search.json?{query}",
        headers={"User-Agent": "mdswyz.github.io citation updater"},
    )

    with urlopen(request, timeout=25) as response:
        data = json.loads(response.read().decode("utf-8"))

    if data.get("error"):
        raise RuntimeError("SerpApi request failed")

    for metric in data.get("cited_by", {}).get("table", []):
        citations = metric.get("citations")
        if isinstance(citations, dict) and "all" in citations:
            return int(citations["all"])

    raise RuntimeError("SerpApi returned no citation metrics")


def fetch_citations(scholar_id, api_key):
    if api_key:
        return fetch_serpapi_citations(scholar_id, api_key)
    return fetch_direct_citations(scholar_id)


scholar_id = os.environ["GOOGLE_SCHOLAR_ID"]
serpapi_key = os.environ.get("SERPAPI_API_KEY", "").strip()
citation_count = fetch_citations(scholar_id, serpapi_key)
author = {
    "scholar_id": scholar_id,
    "citedby": citation_count,
    "updated": datetime.now(timezone.utc).isoformat(),
    "automatic": bool(serpapi_key),
    "publications": {},
}

print(json.dumps(author, indent=2, ensure_ascii=False))

results_dir = Path(__file__).resolve().parent / "results"
results_dir.mkdir(exist_ok=True)

with (results_dir / "gs_data.json").open("w", encoding="utf-8") as outfile:
    json.dump(author, outfile, ensure_ascii=False)

shieldio_data = {
    "schemaVersion": 1,
    "label": "citations",
    "message": str(citation_count),
}
with (results_dir / "gs_data_shieldsio.json").open("w", encoding="utf-8") as outfile:
    json.dump(shieldio_data, outfile, ensure_ascii=False)
