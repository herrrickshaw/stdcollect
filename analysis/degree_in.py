"""Classify India's IS/ISO and IS/IEC adoptions as identical / modified / unknown by reading the
foreword of each standard's text on archive.org (Public.Resource.Org copies). 1 request/second."""
import csv, re, time, urllib.request, urllib.error, os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
rows = [r for r in csv.DictReader(open("catalog/lawresorg_bis.csv")) if re.match(r"IS/(ISO|IEC)", r["id"])]
out = "analysis/degree.csv"
done = {r["url"] for r in csv.DictReader(open(out))} if os.path.exists(out) else set()
fh = open(out, "a", newline=""); w = csv.writer(fh)
if not done: w.writerow(["national_id", "year", "degree", "evidence", "url"])
def fetch(item):
    u = f"https://archive.org/download/{item}/{item.replace('gov.in.', '', 1)}.txt"
    for a in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "stdcollect/0.1"}), timeout=60).read(40000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None  # withdrawn / absent item
            time.sleep(10 * 2 ** a)
        except Exception:
            time.sleep(5)
    return None
for r in rows:
    if r["url"] in done: continue
    item = r["url"].rsplit("/", 1)[1]
    txt = fetch(item); time.sleep(1)
    if not txt: deg, ev = "unknown", "text unavailable"
    else:
        t = re.sub(r"\s+", " ", txt)
        head = t[:12000]
        m = re.search(r"[^.]{0,80}\b(identical (?:with|to)|technically equivalent|modified|technical deviation|adapted|based on|not equivalent)\b[^.]{0,80}", head, re.I)
        if not m: deg, ev = "unknown", "no equivalence statement in first 12k chars"
        else:
            k = m.group(1).lower()
            deg = "identical" if k.startswith("identical") else "modified"
            ev = m.group(0).strip()[:160]
    w.writerow([r["id"], r["year"], deg, ev, r["url"]]); fh.flush()
print("degree rows:", sum(1 for _ in open(out)) - 1, "of", len(rows))
