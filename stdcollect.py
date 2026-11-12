#!/usr/bin/env python3
"""stdcollect - collect engineering standards metadata from public sources and
list which standards bodies are free vs paid, by industry.

  stdcollect.py bodies [--industry oil-gas] [--access free|freemium|paid] [--format table|csv|md]
  stdcollect.py industries
  stdcollect.py collect [rfc|ecfr|lawresorg_bis ...] [--limit N] [--out DIR]
  stdcollect.py search TEXT [--out DIR]       # search collected catalogs
  stdcollect.py download CATALOG.csv --match TEXT [--max N]   # fetch free docs

Only metadata is collected by default; `download` fetches only documents from
sources the registry marks free. Paid standards are listed, never scraped.
"""
import argparse, csv, json, re, sys, time, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).parent
UA = "stdcollect/0.1 (personal research tool; polite, 1 req/s)"
FIELDS = ["source", "id", "title", "year", "status", "url", "access", "industries"]


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def registry():
    return json.loads((HERE / "registry.json").read_text())


# ---------------- collectors ----------------
def collect_rfc(limit):
    """IETF RFC index (free). Streams the 13 MB XML."""
    import io
    raw = get("https://www.rfc-editor.org/rfc-index.xml", binary=True)
    rows = []
    for _, el in ET.iterparse(io.BytesIO(raw)):
        if el.tag.endswith("rfc-entry"):
            ns = el.tag.split("}")[0] + "}"
            g = lambda t: (el.findtext(ns + t) or "").strip()
            num = g("doc-id")
            year = el.findtext(f"{ns}date/{ns}year") or ""
            rows.append(dict(source="ietf", id=num, title=g("title"), year=year,
                             status=g("current-status"),
                             url=f"https://www.rfc-editor.org/rfc/{num.lower()}.txt",
                             access="free", industries="it;telecom;it-security"))
            el.clear()
    return rows[:limit] if limit else rows


# CFR titles relevant to engineering, with industry tags
CFR_INDUSTRY = {
    10: "nuclear;energy", 14: "aviation;aerospace", 21: "food;medical;pharma",
    29: "safety;construction;process-safety", 30: "mining;oil-gas", 33: "maritime",
    40: "environment;chemicals;oil-gas", 46: "maritime", 47: "telecom",
    49: "transport;pipelines;rail;automotive", 18: "energy", 24: "buildings",
}


def collect_ecfr(limit):
    """US CFR titles via eCFR API (free); engineering-relevant titles only."""
    data = json.loads(get("https://www.ecfr.gov/api/versioner/v1/titles.json"))
    rows = []
    for t in data["titles"]:
        n = t["number"]
        if n in CFR_INDUSTRY:
            rows.append(dict(source="ecfr", id=f"CFR-{n}", title=t["name"],
                             year=(t.get("up_to_date_as_of") or "")[:4], status="in force",
                             url=f"https://www.ecfr.gov/current/title-{n}",
                             access="free", industries=CFR_INDUSTRY[n]))
    return rows[:limit] if limit else rows


BIS_DIV = {"ced": "civil;construction", "etd": "electrical", "med": "mechanical", "chd": "chemicals",
           "fad": "food", "txd": "textiles", "mtd": "metallurgy;steel", "pcd": "petroleum;oil-gas",
           "tbd": "transport;automotive", "lmd": "metrology", "mhd": "medical", "cmd": "management",
           "sed": "services", "wrd": "water", "eed": "environment", "ais": "automotive"}


def collect_lawresorg_bis(limit):
    """Indian Standards (BIS) republished by Public.Resource.Org (free, archive.org),
    walked via the per-committee manifest pages."""
    rows, seen = [], set()
    base = "https://law.resource.org/pub/in/bis/"
    names = sorted(set(re.findall(r'href="(manifest\.([a-z]+)[\w.]*\.html)"', get(base))))
    for href, div in names:
        time.sleep(1)
        try:
            page = get(base + href)
        except Exception as e:
            print(f"  skip {href}: {e}", file=sys.stderr); continue
        tags = BIS_DIV.get(div, div) + ";" + href[len("manifest."):-5]
        for url, label in re.findall(r'<a href="(https://archive\.org/details/gov\.in\.is\.[^"]+)">([^<]+) \(pdf\)</a>', page):
            if url in seen: continue
            seen.add(url)
            m = re.search(r"\.(\d{4})$", url)
            rows.append(dict(source="bis-public-resource", id=label, title=url.rsplit("/", 1)[1],
                             year=m.group(1) if m else "", status="as published", url=url,
                             access="free", industries=tags))
            if limit and len(rows) >= limit: return rows
    return rows


def _clean(t):
    import html
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).replace("\ufffd", "").strip()


ITU_SERIES = "ADEFGHIJKLMNOPQRSTUVXYZ"


def collect_itu(limit):
    """ITU-T Recommendations (free) from each series index page."""
    rows = []
    for ser in ITU_SERIES:
        time.sleep(1)
        try:
            page = get(f"https://www.itu.int/rec/T-REC-{ser}/en")
        except Exception as e:
            print(f"  skip series {ser}: {e}", file=sys.stderr); continue
        for rid, cell in re.findall(
                r'parent=T-REC-([^"&]+)"><strong>[^<]*</strong></a></p>\s*</td>\s*<td[^>]*>(.*?)</td>', page, re.S):
            title = _clean(cell)
            st = "withdrawn" if "[Withdrawn]" in title else ("superseded" if "[Superseded]" in title else "in force")
            title = re.sub(r"^\[(Withdrawn|Superseded)\]\s*", "", title)
            rows.append(dict(source="itu-t", id=f"ITU-T {rid}", title=title, year="", status=st,
                             url=f"https://www.itu.int/rec/T-REC-{rid}/en", access="free",
                             industries=f"telecom;series-{ser}"))
            if limit and len(rows) >= limit: return rows
    return rows


NASA_BASE = "https://standards.nasa.gov/all-standards"


def collect_nasa(limit):
    """NASA Technical Standards System (free): paginated 'all standards' table."""
    rows, page_no = [], 0
    while True:
        html_ = get(f"{NASA_BASE}?page={page_no}")
        trs = re.findall(r"<tr>(.*?)</tr>", html_, re.S)
        got = 0
        for tr in trs:
            m = re.search(r'href="(/standard/[^"]+)"', tr)
            cells = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if not m or len(cells) < 4: continue
            got += 1
            d = re.search(r'datetime="(\d{4})', tr)
            rows.append(dict(source="nasa-ntss", id=cells[0] + (f" ({cells[1]})" if cells[1] else ""),
                             title=cells[3], year=d.group(1) if d else "", status="active",
                             url="https://standards.nasa.gov" + m.group(1), access="free",
                             industries="aerospace;space"))
            if limit and len(rows) >= limit: return rows
        if not got: return rows
        page_no += 1; time.sleep(1)


ETSI_KINDS = ["etsi_en", "etsi_ts", "etsi_tr", "etsi_es", "etsi_eg"]


def collect_etsi(limit):
    """ETSI (free) via the public /deliver directory tree: one row per document
    number (directory = number + version folders). Titles are not in the tree."""
    rows = []
    for kind in ETSI_KINDS:
        top = get(f"https://www.etsi.org/deliver/{kind}/")
        ranges = re.findall(rf'HREF="/deliver/{kind}/(\d+_\d+)/"', top, re.I)
        for rg in ranges:
            time.sleep(1)
            try:
                sub = get(f"https://www.etsi.org/deliver/{kind}/{rg}/")
            except Exception as e:
                print(f"  skip {kind}/{rg}: {e}", file=sys.stderr); continue
            for num in re.findall(rf'HREF="/deliver/{kind}/{rg}/(\d+)/"', sub, re.I):
                label = kind.split("_")[1].upper()
                rows.append(dict(source="etsi", id=f"ETSI {label} {num}", title="(see directory for versions/PDF)",
                                 year="", status="published", access="free",
                                 url=f"https://www.etsi.org/deliver/{kind}/{rg}/{num}/",
                                 industries="telecom;it"))
                if limit and len(rows) >= limit: return rows
    return rows


def collect_china(limit):
    """China national standards (GB, GB/T, GB/Z) from openstd.samr.gov.cn. The
    portal gives free *online reading* of metadata/text, not PDF download, so
    access is 'view-only'. ~72k records; 50/page, 1 req/s (~25 min for all)."""
    rows, page = [], 1
    while True:
        h = get(f"https://openstd.samr.gov.cn/bzgk/gb/std_list?p.p1=0&p.p90=circulation_date&p.p91=desc&page={page}&pageSize=50")
        found = 0
        for tr in re.findall(r"<tr>(.*?)</tr>", h, re.S):
            m = re.search(r"showInfo\('([0-9A-F]+)'\)", tr)
            cells = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if not m or len(cells) < 9: continue
            found += 1
            rows.append(dict(source="china-gb", id=cells[1], title=cells[4], year=cells[7][:4],
                             status=cells[6] or cells[5], access="view-only",
                             url=f"https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno={m.group(1)}",
                             industries="china;national-standard"))
            if limit and len(rows) >= limit: return rows
        if not found: return rows
        page += 1; time.sleep(1)


KS_CLASS = {"A": "basic", "B": "mechanical", "C": "electrical;electronics", "D": "metals;steel", "E": "mining",
            "F": "construction;civil", "G": "packaging;logistics", "H": "food", "I": "environment;safety",
            "J": "daily-life", "K": "textiles;chemicals", "L": "ceramics", "M": "chemicals", "P": "medical",
            "Q": "management;quality", "R": "transport;automotive", "S": "services", "T": "distribution",
            "V": "shipbuilding;maritime", "W": "aerospace", "X": "information-technology"}


def collect_korea(limit):
    """Korean Standards (KS) from KSSN standard.go.kr (free viewing, 34k records, 100/page)."""
    rows, page = [], 1
    while True:
        data = urllib.parse.urlencode({"pageUnit": "100", "pageIndex": str(page)}).encode()
        req = urllib.request.Request("https://standard.go.kr/KSCI/standardIntro/getStandardSearchList.do",
                                     data=data, headers={"User-Agent": UA})
        h = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
        found = 0
        for tr in re.findall(r"<tr class=\"mflex bottom\">(.*?)</tr>", h, re.S):
            m = re.search(r"fnGoStdView\('([^']+)','([^']+)','([^']+)'\)", tr)
            cells = [_clean(c) for c in re.findall(r'<td class="(?:mobiletd|tl mobiletd)"[^>]*>(.*?)</td>', tr, re.S)]
            if not m or len(cells) < 3: continue
            found += 1
            cls = re.match(r"KS\s+([A-Z])", cells[0])
            rows.append(dict(source="korea-ks", id=cells[0], title=cells[1], year=cells[2][:4],
                             status="abolished" if "폐지" in cells[1] else "in force", access="view-only",
                             url="https://standard.go.kr/KSCI/standardIntro/getStandardSearchList.do?ksNo=" + urllib.parse.quote(cells[0]),
                             industries=KS_CLASS.get(cls.group(1), "other") if cls else "other"))
            if limit and len(rows) >= limit: return rows
        if not found: return rows
        page += 1; time.sleep(1)


def collect_saudi(limit):
    """SASO (Saudi Arabia): the published standards catalogue is not publicly
    crawlable; this collects the draft standards open for public consultation
    ('public_multimedia' pages in the site map)."""
    h = get("https://www.saso.gov.sa/en/sitemap/Pages/default.aspx")
    rows = []
    pat = r'href="(/en/Laws-And-Regulations/public_multimedia/Pages/\d+_\d+\.aspx)"[^>]*>\s*([^<]{3,})'
    for path, title in re.findall(pat, h):
        num = re.search(r"/(\d+)_\d+\.aspx", path).group(1)
        rows.append(dict(source="saso-drafts", id=f"SASO-draft-{num}", title=_clean(title), year="",
                         status="draft for public consultation", access="free",
                         url="https://www.saso.gov.sa" + path, industries="saudi;draft"))
        if limit and len(rows) >= limit: break
    return rows


def collect_japan(limit):
    """JISC (Japan) JIS database. Not implemented: the site is in an extended
    maintenance outage (service-stop notice, HTTP 502). Re-probe later."""
    r = urllib.request.Request("https://www.jisc.go.jp/app/jis/general/GnrJISSearch.html", headers={"User-Agent": UA})
    try:
        urllib.request.urlopen(r, timeout=30)
    except Exception as e:
        raise RuntimeError(f"JISC unavailable ({e}); no JIS collector built while the site is down")
    raise NotImplementedError("JISC is reachable again - write the JIS search collector")


COLLECTORS = {"china": collect_china, "korea": collect_korea, "saudi": collect_saudi, "japan": collect_japan, "itu": collect_itu, "nasa": collect_nasa, "etsi": collect_etsi, "rfc": collect_rfc, "ecfr": collect_ecfr, "lawresorg_bis": collect_lawresorg_bis}


# ---------------- commands ----------------
def emit(rows, cols, fmt):
    if fmt == "csv":
        w = csv.writer(sys.stdout); w.writerow(cols)
        for r in rows: w.writerow([r.get(c, "") if isinstance(r, dict) else r for c in cols])
    elif fmt == "md":
        print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
        for r in rows: print("| " + " | ".join(str(r.get(c, "")).replace("|", "/") for c in cols) + " |")
    else:
        widths = [min(48, max(len(c), *(len(str(r.get(c, ""))) for r in rows))) for c in cols] if rows else []
        print("  ".join(c.upper().ljust(w) for c, w in zip(cols, widths)))
        for r in rows:
            print("  ".join(str(r.get(c, ""))[:w].ljust(w) for c, w in zip(cols, widths)))


def cmd_bodies(a):
    rows = []
    for b in registry():
        if a.industry and not any(a.industry.lower() in i for i in b["industries"]):
            continue
        if a.access and b["access"] != a.access: continue
        rows.append({**b, "industries": ";".join(b["industries"])})
    cols = ["id", "name", "region", "access", "typical_price", "free_part", "url"] if a.format != "table" \
        else ["id", "name", "region", "access", "typical_price", "industries"]
    emit(rows, cols, a.format)
    print(f"\n{len(rows)} bodies", file=sys.stderr)


def cmd_countries(a):
    rows = json.loads((HERE / "countries.json").read_text())
    rows = [r for r in rows if (not a.region or a.region.lower() in r["region"].lower())
            and (not a.access or r["access"] == a.access)
            and (not a.country or a.country.lower() in (r["code"] + r["country"]).lower())]
    emit(rows, ["code", "country", "body", "access", "region", "url"], a.format)


def cmd_sectors(a):
    sec = json.loads((HERE / "sectors.json").read_text())
    reg = {b["id"]: b for b in registry()}
    for name, ids in sec.items():
        if a.sector and a.sector.lower() not in name: continue
        print(f"\n== {name} ==")
        rows = [{"id": i, "name": reg[i]["name"][:44], "access": reg[i]["access"], "price": reg[i]["typical_price"]}
                for i in ids if i in reg]
        emit(rows, ["id", "name", "access", "price"], a.format)
        free = [r["id"] for r in rows if r["access"] == "free"]
        print(f"  free: {', '.join(free) or 'none'}")


def cmd_industries(a):
    cnt = {}
    for b in registry():
        for i in b["industries"]: cnt[i] = cnt.get(i, 0) + 1
    for i, n in sorted(cnt.items(), key=lambda x: (-x[1], x[0])): print(f"{n:3d}  {i}")


def cmd_collect(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for name in a.sources or COLLECTORS:
        print(f"collecting {name} ...", file=sys.stderr)
        try:
            rows = COLLECTORS[name](a.limit)
        except Exception as e:
            print(f"  FAILED {name}: {e}", file=sys.stderr); continue
        p = out / f"{name}.csv"
        with p.open("w", newline="") as f:
            w = csv.DictWriter(f, FIELDS); w.writeheader(); w.writerows(rows)
        print(f"  {len(rows)} rows -> {p}", file=sys.stderr)


def cmd_search(a):
    q = a.text.lower(); n = 0
    for p in sorted(Path(a.out).glob("*.csv")):
        for r in csv.DictReader(p.open()):
            if q in (r["id"] + " " + r["title"] + " " + r["industries"]).lower():
                print(f"[{r['source']}] {r['id']}  {r['title'][:80]}  {r['url']}"); n += 1
    print(f"{n} hits", file=sys.stderr)


def cmd_download(a):
    dest = Path(a.dest); dest.mkdir(parents=True, exist_ok=True); n = 0
    for r in csv.DictReader(open(a.catalog)):
        if r["access"] != "free" or a.match.lower() not in (r["id"] + r["title"]).lower(): continue
        url = r["url"]
        if "archive.org/details/" in url:  # resolve to the PDF
            ident = url.rsplit("/", 1)[1]
            url = url.replace("/details/", "/download/") + "/" + ident.replace("gov.in.", "", 1) + ".pdf"
        fn = dest / re.sub(r"[^\w.-]+", "_", r["id"] + "_" + Path(urllib.parse.urlparse(url).path).name)
        try:
            fn.write_bytes(get(url, binary=True)); print("saved", fn)
        except Exception as e:
            print("fail", url, e, file=sys.stderr)
        n += 1; time.sleep(1)
        if n >= a.max: break


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("bodies"); s.add_argument("--industry"); s.add_argument("--access", choices=["free", "freemium", "paid"])
    s.add_argument("--format", choices=["table", "csv", "md"], default="table"); s.set_defaults(f=cmd_bodies)
    s = sp.add_parser("countries"); s.add_argument("--region"); s.add_argument("--country")
    s.add_argument("--access", choices=["free", "freemium", "paid"]); s.add_argument("--format", choices=["table", "csv", "md"], default="table"); s.set_defaults(f=cmd_countries)
    s = sp.add_parser("sectors"); s.add_argument("--sector"); s.add_argument("--format", choices=["table", "csv", "md"], default="table"); s.set_defaults(f=cmd_sectors)
    sp.add_parser("industries").set_defaults(f=cmd_industries)
    s = sp.add_parser("collect"); s.add_argument("sources", nargs="*", choices=list(COLLECTORS))
    s.add_argument("--limit", type=int); s.add_argument("--out", default="catalog"); s.set_defaults(f=cmd_collect)
    s = sp.add_parser("search"); s.add_argument("text"); s.add_argument("--out", default="catalog"); s.set_defaults(f=cmd_search)
    s = sp.add_parser("download"); s.add_argument("catalog"); s.add_argument("--match", required=True)
    s.add_argument("--max", type=int, default=5); s.add_argument("--dest", default="downloads"); s.set_defaults(f=cmd_download)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
