"""Compute sector chains: which international (ISO/IEC) standards recur inside each sector, and which
standards bridge several sectors. Sector comes from the catalog's own taxonomy:
Korea KS class letter, EU harmonised legislation, BIS technical committee, eCFR part."""
import csv, glob, re, os, collections, importlib.util
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
src = open("analysis/link_standards.py").read().split("SRC_COUNTRY")[0]  # reuse key() only
ns = {}; exec(src.replace('os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")', ""), ns); key = ns["key"]
KS = {"basic": "basic", "mechanical": "mechanical", "electrical;electronics": "electrical-electronics", "metals;steel": "metals-steel",
      "mining": "mining", "construction;civil": "construction-civil", "packaging;logistics": "packaging-logistics", "food": "food",
      "environment;safety": "environment-safety", "daily-life": "daily-life", "textiles;chemicals": "textiles-chemicals",
      "ceramics": "ceramics", "chemicals": "chemicals", "medical": "medical", "management;quality": "management-quality",
      "transport;automotive": "transport-automotive", "services": "services", "distribution": "distribution",
      "shipbuilding;maritime": "shipbuilding-maritime", "aerospace": "aerospace", "information-technology": "information-technology"}
sectors = collections.defaultdict(collections.Counter)   # (family, sector) -> Counter(intl std)
ibr = collections.defaultdict(collections.Counter)       # cfr section -> Counter(body)
for f in glob.glob("catalog/*.csv"):
    for r in csv.DictReader(open(f)):
        s = r["source"]
        if s == "korea-ks": fam, sec = "Korea KS", KS.get(r["industries"], r["industries"])
        elif s == "eu-harmonised": fam, sec = "EU harmonised", "eu-" + r["industries"].split(";")[1]
        elif s == "bis-public-resource": fam, sec = "India BIS", "bis-" + r["industries"].split(";")[-1].replace("ced.", "ced-")
        elif s == "ecfr-ibr":
            parts = r["industries"].split(";"); ibr[parts[-1]][parts[-2].upper()] += 1; continue
        else: continue
        for k in key(r["id"] + " " + r["title"][:60]): sectors[(fam, sec)][k] += 1
rows = sorted(((fam, sec, len(c), "; ".join(f"{k} ({n})" for k, n in c.most_common(12))) for (fam, sec), c in sectors.items() if c),
              key=lambda x: -x[2])
with open("analysis/sector_chains.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["catalog", "sector", "n_intl_standards", "most_recurring_intl_standards"]); w.writerows(rows)
bridge = collections.defaultdict(set)
for (fam, sec), c in sectors.items():
    for k in c: bridge[k].add(f"{fam}:{sec}")
b = sorted(((k, len(v), "; ".join(sorted(v))[:300]) for k, v in bridge.items() if len(v) >= 2), key=lambda x: (-x[1], x[0]))
with open("analysis/sector_bridges.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["intl_standard", "n_sectors", "sectors"]); w.writerows(b)
with open("analysis/ibr_sector_bodies.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["cfr_section", "bodies_incorporated"])
    for sec, c in sorted(ibr.items()): w.writerow([sec, "; ".join(f"{k} ({n})" for k, n in c.most_common())])
print(len(rows), "sector rows;", len(b), "bridge standards;", len(ibr), "CFR sections")
