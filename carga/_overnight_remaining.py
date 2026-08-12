import os
import urllib.request
import json
import sys

k = os.environ.get("API_FOOTBALL_KEY")
if not k:
    print("?/?")
    sys.exit(0)
try:
    req = urllib.request.Request(
        "https://v3.football.api-sports.io/status",
        headers={"x-apisports-key": k},
    )
    raw = urllib.request.urlopen(req, timeout=30).read().decode()
    d = json.loads(raw)
    r = (d.get("response") or {}).get("requests") or {}
    print("%s/%s" % (r.get("current", "?"), r.get("limit_day", "?")))
except Exception:
    print("error")
    sys.exit(0)
