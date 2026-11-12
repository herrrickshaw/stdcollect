"""Link standards across catalogs by the international (ISO/IEC) standard they adopt.
Output: analysis/links.csv (one row per catalog entry -> intl key) and
analysis/clusters.csv (one row per intl standard with the countries/bodies carrying it)."""
import csv, re, glob, collections, os
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
NUM = r"(\d{1,6}(?:[-–.]\d{1,3}){0,3})"
PATS = [  # (regex, family)
    (re.compile(r"\b(?:EN\s+)?ISO\s*/\s*IEC\s*" + NUM), "ISO/IEC"),
    (re.compile(r"\b(?:EN\s+|IS\s*/\s*|KS\s+[A-Z]\s+|BS\s+EN\s+)?ISO\s*" + NUM), "ISO"),
    (re.compile(r"\b(?:EN\s+|IS\s*/\s*|KS\s+[A-Z]\s+)?IEC\s*" + NUM), "IEC"),
    (re.compile(r"\bEN\s+(6\d{4}(?:[-–.]\d{1,3}){0,3})"), "IEC"),   # EN 6xxxx are IEC adoptions
]
def key(text):
    out = set()
    for rx, fam in PATS:
        for m in rx.finditer(text):
            n = m.group(1).replace("–", "-").replace(".", "-").strip("-")
            out.add(f"{fam} {n}")
        if fam == "ISO/IEC":  # blank joint standards so they are not re-read as plain ISO or IEC
            text = rx.sub(" ", text)
    return out
SRC_COUNTRY = {"bis-public-resource": "India", "korea-ks": "South Korea", "eu-harmonised": "EU (CEN/CENELEC)",
               "saso-drafts": "Saudi Arabia", "china-gb": "China", "ietf": "IETF", "itu-t": "ITU",
               "pro-jp": "Japan", "pro-th": "Thailand", "pro-ec": "Ecuador", "pro-nz": "New Zealand",
               "pro-za": "South Africa", "pro-au": "Australia", "pro-ke": "Kenya", "pro-ph": "Philippines",
               "pro-et": "Ethiopia", "pro-gso": "GCC", "pro-ars": "ARSO (Africa)", "pro-com": "COMESA", "pro-ug": "Uganda"}
links, clusters = [], collections.defaultdict(lambda: collections.defaultdict(set))
for f in sorted(glob.glob("catalog/*.csv")):
    for r in csv.DictReader(open(f)):
        # ids only (titles of national standards mention ISO in narrative)
        for k in key(r["id"] + " " + r["title"] if r["source"] in ("eu-harmonised", "saso-drafts") else r["id"] + " " + r["title"][:60]):
            links.append((k, SRC_COUNTRY.get(r["source"], r["source"]), r["source"], r["id"], r["title"][:90], r["url"]))
            clusters[k][SRC_COUNTRY.get(r["source"], r["source"])].add(r["id"])
with open("analysis/links.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["intl_standard", "country_or_bloc", "source", "national_id", "title", "url"]); w.writerows(links)
rows = [(k, len(v), "; ".join(sorted(v)), " | ".join(sorted(i for s in v.values() for i in s))[:300]) for k, v in clusters.items()]
rows.sort(key=lambda x: (-x[1], x[0]))
with open("analysis/clusters.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["intl_standard", "n_countries", "countries", "national_ids"]); w.writerows(rows)
print(len(links), "links;", len(rows), "intl standards;", sum(1 for r in rows if r[1] >= 2), "in >=2 countries/blocs;", sum(1 for r in rows if r[1] >= 3), ">=3")
