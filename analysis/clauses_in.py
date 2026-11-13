"""Extract the clause structure (numbered clauses + headings) and quantitative specifications
(sentences with 'shall'/'not less than'... plus a number and unit) from the free full texts of
Indian adoptions of ISO/IEC standards (Public.Resource.Org on archive.org). 1 request/second.
Outputs: analysis/clauses.csv, analysis/specs.csv. Resumable."""
import csv, re, time, urllib.request, urllib.error, os
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
rows = [r for r in csv.DictReader(open("catalog/lawresorg_bis.csv")) if re.match(r"IS/(ISO|IEC)", r["id"])]
CL, SP = "analysis/clauses.csv", "analysis/specs.csv"
done = {r["url"] for r in csv.DictReader(open(CL))} if os.path.exists(CL) else set()
newf = not done
fc, fs = open(CL, "a", newline=""), open(SP, "a", newline="")
wc, ws = csv.writer(fc), csv.writer(fs)
if newf:
    wc.writerow(["national_id", "clause", "heading", "url"]); ws.writerow(["national_id", "clause", "spec_snippet", "value_unit", "url"])
    fc.flush(); fs.flush()
HEAD = re.compile(r"^\s{0,6}((?:\d{1,2}|[A-Z])(?:\.\d{1,3}){0,4})\s{1,6}([A-Z][^\n]{2,90})$", re.M)
SPEC = re.compile(r"[^.\n]{0,70}\b(?:shall|should|not (?:less|more|greater|exceed)|at least|maximum|minimum|within)\b[^.\n]{0,60}?(\d+(?:[.,]\d+)?\s?(?:%|°C|mm|cm|m|kg|g|mg|ml|mL|l|Pa|kPa|MPa|bar|N|kN|V|kV|A|mA|W|kW|Hz|s|min|h|dB|µm|mol|ppm))\b[^.\n]{0,40}")
def fetch(item):
    u = f"https://archive.org/download/{item}/{item.replace('gov.in.', '', 1)}.txt"
    for a in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "stdcollect/0.1"}), timeout=90).read(3_000_000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
            time.sleep(10 * 2 ** a)
        except Exception: time.sleep(5)
    return None
for r in rows:
    if r["url"] in done: continue
    txt = fetch(r["url"].rsplit("/", 1)[1]); time.sleep(1)
    if txt:
        seen = set()
        for m in HEAD.finditer(txt):
            c, h = m.group(1), m.group(2).strip()
            if (c, h) in seen or re.search(r"\.{4,}|\d{3,}\s*$", h): continue
            seen.add((c, h)); wc.writerow([r["id"], c, h[:90], r["url"]])
        n = 0
        for m in SPEC.finditer(txt):
            ws.writerow([r["id"], "", re.sub(r"\s+", " ", m.group(0)).strip()[:130], m.group(1), r["url"]]); n += 1
            if n >= 40: break
        if not seen: wc.writerow([r["id"], "", "(no numbered clauses recognised)", r["url"]])
    else:
        wc.writerow([r["id"], "", "(text unavailable)", r["url"]])
    fc.flush(); fs.flush()
print("done", len(rows))
