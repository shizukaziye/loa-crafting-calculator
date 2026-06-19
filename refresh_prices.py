#!/usr/bin/env python3
"""Refresh the baked price snapshot inside index.html — no cloud, no proxy.

For every item the calculator needs (both regions) this records two prices:
  s = spot      — the current lowest listing (can be distorted when a market is
                  bought out, leaving only overpriced listings)
  m = median    — median of the last WINDOW daily average prices, a robust "fair"
                  price that ignores single-day spikes/dumps

The app defaults to the median; spot is a toggle. The market API works fine
server-side (CORS only blocks browsers), so this is 100% reliable with zero setup.

    python3 refresh_prices.py
"""
import json, re, subprocess, sys, time, datetime, statistics, pathlib

HTML   = pathlib.Path(__file__).with_name("index.html")
BASE   = "https://marketdata-api.yrzhao1068589.workers.dev/v1"
WINDOW = 7                       # days of history for the median
src    = HTML.read_text()

def grab(name):
    m = re.search(r'^const %s=(.*);\s*$' % name, src, re.M)
    if not m: sys.exit(f"could not find const {name} in index.html")
    return json.loads(m.group(1))

ITEMS = grab("ITEMS")
slugs = sorted({v["slug"] for v in ITEMS.values()})

def fetch_spot(region):
    body = json.dumps({"region_slug": region, "item_slugs": slugs})
    out = subprocess.check_output(
        ["curl","-s","-X","POST",f"{BASE}/prices/latest","-H","Content-Type: application/json","-d",body],
        timeout=40)
    return {row["item_slug"]: row["price"] for row in json.loads(out)}

END   = datetime.date.today()
START = END - datetime.timedelta(days=WINDOW + 5)   # extra cushion for missing days
def fetch_median(region, slug, spot):
    url = f"{BASE}/prices/historical/{region}/{slug}?start_date={START}&end_date={END}"
    try:
        days = json.loads(subprocess.check_output(["curl","-s",url], timeout=30))
        avgs = [d["avg_price"] for d in days if d.get("avg_price") is not None]
        if len(avgs) >= 2:
            return round(statistics.median(avgs[-WINDOW:]))
    except Exception:
        pass
    return spot                                     # fall back to spot if no history

snap = {}
for region in ("nae", "euc"):
    spot = fetch_spot(region)
    snap[region] = {}
    for slug in slugs:
        s = spot.get(slug, 0)
        snap[region][slug] = {"s": s, "m": fetch_median(region, slug, s)}
    print(f"  {region}: {len(snap[region])} items priced (spot + {WINDOW}-day median)")

if snap == grab("SNAPSHOT"):
    print("Prices unchanged since last snapshot — nothing to write.")
    sys.exit(0)

ts = int(time.time())
src = re.sub(r'^const SNAPSHOT=.*;\s*$',
             "const SNAPSHOT=" + json.dumps(snap, separators=(',', ':')) + ";", src, count=1, flags=re.M)
src = re.sub(r'^const SNAP_TS=.*;\s*$', f"const SNAP_TS={ts};", src, count=1, flags=re.M)
HTML.write_text(src)
print(f"Updated snapshot in {HTML.name} @ {time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))}. Reload the page.")
