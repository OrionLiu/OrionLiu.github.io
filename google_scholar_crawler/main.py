from scholarly import scholarly, ProxyGenerator
import jsonpickle
import json
from datetime import datetime
import os

import re
import requests
from bs4 import BeautifulSoup
import os

#判断是否是反扒
def preflight_check(scholar_id: str):
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else None
    has_name = bool(soup.select_one("#gsc_prf_in"))          # 作者名元素
    has_metrics = bool(soup.select_one("#gsc_rsb_st"))       # 右侧指标表格
    canonical = soup.find("link", rel="canonical")
    looks_blocked = bool(re.search(r"unusual traffic|not a robot|recaptcha|sorry|consent", r.text, re.I))

    print("[preflight] status:", r.status_code)
    print("[preflight] final_url:", r.url)
    print("[preflight] title:", title)
    print("[preflight] has_name(#gsc_prf_in):", has_name)
    print("[preflight] has_metrics(#gsc_rsb_st):", has_metrics)
    print("[preflight] canonical:", bool(canonical))
    print("[preflight] looks_blocked:", looks_blocked)

preflight_check(os.environ["GOOGLE_SCHOLAR_ID"])


# Setup proxy
pg = ProxyGenerator()
pg.FreeProxies()  # Use free rotating proxies

ok = pg.FreeProxies()
print("FreeProxies ok:", ok)
if ok:
    scholarly.use_proxy(pg)
else:
    print("No free proxies available; continue without proxy")

scholarly.use_proxy(pg)

author: dict = scholarly.search_author_id(os.environ['GOOGLE_SCHOLAR_ID'])
scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
name = author['name']
author['updated'] = str(datetime.now())
author['publications'] = {v['author_pub_id']:v for v in author['publications']}
print(json.dumps(author, indent=2))
os.makedirs('results', exist_ok=True)
with open(f'results/gs_data.json', 'w') as outfile:
    json.dump(author, outfile, ensure_ascii=False)

shieldio_data = {
  "schemaVersion": 1,
  "label": "citations",
  "message": f"{author['citedby']}",
}
with open(f'results/gs_data_shieldsio.json', 'w') as outfile:
    json.dump(shieldio_data, outfile, ensure_ascii=False)
