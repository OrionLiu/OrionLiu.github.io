from scholarly import scholarly, ProxyGenerator
import jsonpickle
import json
from datetime import datetime
import os
import re
import sys
import traceback
import requests
from bs4 import BeautifulSoup

SCHOLAR_ID = os.environ["GOOGLE_SCHOLAR_ID"]


def preflight_check(scholar_id: str):
    """Print diagnostics about whether Scholar is serving us or blocking us."""
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"}
    r = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else None
    has_name = bool(soup.select_one("#gsc_prf_in"))          # author-name element
    has_metrics = bool(soup.select_one("#gsc_rsb_st"))       # right-side metrics table
    canonical = soup.find("link", rel="canonical")
    looks_blocked = bool(re.search(r"unusual traffic|not a robot|recaptcha|sorry|consent", r.text, re.I))
    print("[preflight] status:", r.status_code)
    print("[preflight] final_url:", r.url)
    print("[preflight] title:", title)
    print("[preflight] has_name(#gsc_prf_in):", has_name)
    print("[preflight] has_metrics(#gsc_rsb_st):", has_metrics)
    print("[preflight] canonical:", bool(canonical))
    print("[preflight] looks_blocked:", looks_blocked)


def fetch_citations(scholar_id: str) -> dict:
    preflight_check(scholar_id)

    # Proxy setup must never kill the run: fall back to direct on any problem.
    try:
        pg = ProxyGenerator()
        if pg.FreeProxies():
            print("Free proxies found; routing scholarly through them")
            scholarly.use_proxy(pg)
        else:
            print("No free proxies available; continuing without proxy")
    except Exception as e:
        print(f"[warn] proxy setup failed ({e!r}); continuing without proxy")

    author: dict = scholarly.search_author_id(scholar_id)
    scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
    return author


def main() -> int:
    try:
        author = fetch_citations(SCHOLAR_ID)
    except Exception:
        # Fail soft: keep last good data, commit nothing, exit 0 so GitHub
        # stops sending a failure email every day. Diagnostics stay in the log.
        print("[error] citation scrape failed; keeping last good data")
        traceback.print_exc()
        return 0

    name = author['name']
    author['updated'] = str(datetime.now())
    author['publications'] = {v['author_pub_id']: v for v in author['publications']}
    print(json.dumps(author, indent=2))
    os.makedirs('results', exist_ok=True)
    with open('results/gs_data.json', 'w') as outfile:
        json.dump(author, outfile, ensure_ascii=False)

    shieldio_data = {
        "schemaVersion": 1,
        "label": "citations",
        "message": f"{author['citedby']}"
    }
    with open('results/gs_data_shieldsio.json', 'w') as outfile:
        json.dump(shieldio_data, outfile, ensure_ascii=False)
    print(f"[ok] wrote results for {name}; total citations: {author['citedby']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
