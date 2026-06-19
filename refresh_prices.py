#!/usr/bin/env python3
"""Refresh the baked price snapshot inside index.html — no cloud, no proxy.

The market API can't be called from the browser on another domain (CORS), but it
works fine server-side. This pulls current prices for every item the calculator
needs (both regions) and rewrites the SNAPSHOT in index.html in place. Run it
whenever you want fresh prices, then reload the page:

    python3 refresh_prices.py
"""
import json, re, subprocess, sys, time, pathlib

HTML = pathlib.Path(__file__).with_name("index.html")
API  = "https://marketdata-api.yrzhao1068589.workers.dev/v1/prices/latest"
src  = HTML.read_text()

def grab(name):
    m = re.search(r'^const %s=(.*);\s*$' % name, src, re.M)
    if not m: sys.exit(f"could not find const {name} in index.html")
    return json.loads(m.group(1))

ITEMS = grab("ITEMS")
slugs = sorted({v["slug"] for v in ITEMS.values()})

def fetch(region):
    body = json.dumps({"region_slug": region, "item_slugs": slugs})
    # curl, because the API rejects the default python-urllib user-agent (403)
    out = subprocess.check_output(
        ["curl", "-s", "-X", "POST", API, "-H", "Content-Type: application/json", "-d", body],
        timeout=40)
    return {row["item_slug"]: row["price"] for row in json.loads(out)}

snap = {}
for reg in ("nae", "euc"):
    snap[reg] = fetch(reg)
    print(f"  {reg}: {len(snap[reg])}/{len(slugs)} prices")
    time.sleep(0.3)

ts = int(time.time())
src = re.sub(r'^const SNAPSHOT=.*;\s*$',
             "const SNAPSHOT=" + json.dumps(snap, separators=(',', ':')) + ";", src, count=1, flags=re.M)
src = re.sub(r'^const SNAP_TS=.*;\s*$', f"const SNAP_TS={ts};", src, count=1, flags=re.M)
HTML.write_text(src)
print(f"Updated snapshot in {HTML.name} @ {time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))}. Reload the page.")
