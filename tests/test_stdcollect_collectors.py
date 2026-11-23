import csv
import gzip
import io
import json
import sys
import types
import urllib.error

import pytest

import stdcollect as sc


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(sc.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


def fake_get(monkeypatch, pages, default=""):
    """pages: url -> text|bytes|Exception. Unlisted URLs return `default`."""
    seen = []

    def g(url, binary=False):
        seen.append(url)
        v = pages.get(url, default)
        if isinstance(v, Exception):
            raise v
        if binary and isinstance(v, str):
            return v.encode()
        return v

    monkeypatch.setattr(sc, "get", g)
    return seen


# ---------------- get() ----------------
class _Resp:
    def __init__(self, data):
        self.data = data

    def read(self, *a):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, retry_after=None):
    class H(dict):
        def get(self, k, d=None):
            return super().get(k, d)

    hdrs = H({"Retry-After": retry_after} if retry_after is not None else {})
    return urllib.error.HTTPError("u", code, "x", hdrs, None)


def test_get_text_binary_and_user_agent(monkeypatch):
    seen = {}

    def fake_open(req, timeout):
        seen["ua"] = req.get_header("User-agent")
        seen["timeout"] = timeout
        return _Resp("héllo".encode())

    monkeypatch.setattr(sc.urllib.request, "urlopen", fake_open)
    assert sc.get("http://x") == "héllo" and seen == {"ua": sc.UA, "timeout": 60}
    assert sc.get("http://x", binary=True) == "héllo".encode()
    monkeypatch.setattr(sc.urllib.request, "urlopen", lambda r, timeout: _Resp(b"\xff\xfeok"))
    assert sc.get("http://x").endswith("ok") and "�" in sc.get("http://x")


def test_get_retries_429_503_with_backoff(monkeypatch, _no_sleep):
    seq = iter([_http_error(429, "7"), _http_error(503), _http_error(429, "abc"), _Resp(b"fine")])

    def fake_open(req, timeout):
        v = next(seq)
        if isinstance(v, Exception):
            raise v
        return v

    monkeypatch.setattr(sc.urllib.request, "urlopen", fake_open)
    assert sc.get("http://u") == "fine"
    # max(Retry-After, 10*2**attempt): 10 (7<10), 20, 40 (bad header -> 0)
    assert _no_sleep == [10, 20, 40]


def test_get_retry_after_larger_than_backoff(monkeypatch, _no_sleep):
    seq = iter([_http_error(429, "99"), _Resp(b"ok")])
    monkeypatch.setattr(sc.urllib.request, "urlopen",
                        lambda r, timeout: (lambda v: (_ for _ in ()).throw(v) if isinstance(v, Exception) else v)(next(seq)))
    sc.get("http://u")
    assert _no_sleep == [99]


def test_get_gives_up_on_fifth_failure_and_on_other_codes(monkeypatch, _no_sleep):
    n = []

    def always(req, timeout):
        n.append(1)
        raise _http_error(503)

    monkeypatch.setattr(sc.urllib.request, "urlopen", always)
    with pytest.raises(urllib.error.HTTPError):
        sc.get("http://u")
    assert len(n) == 5 and _no_sleep == [10, 20, 40, 80]
    n.clear()
    _no_sleep.clear()

    def notfound(req, timeout):
        n.append(1)
        raise _http_error(404)

    monkeypatch.setattr(sc.urllib.request, "urlopen", notfound)
    with pytest.raises(urllib.error.HTTPError):
        sc.get("http://u")
    assert len(n) == 1 and _no_sleep == []


def test_registry_reads_json(tmp_path, monkeypatch):
    (tmp_path / "registry.json").write_text('[{"id": "x"}]')
    monkeypatch.setattr(sc, "HERE", tmp_path)
    assert sc.registry() == [{"id": "x"}]


# ---------------- rfc ----------------
RFC_XML = """<rfc-index xmlns="http://www.rfc-editor.org/rfc-index">
<rfc-entry><doc-id>RFC0001</doc-id><title> Host Software </title><date><month>April</month><year>1969</year></date>
<current-status>UNKNOWN</current-status></rfc-entry>
<rfc-entry><doc-id>RFC9000</doc-id><title>QUIC</title><date><month>May</month></date><current-status>PROPOSED STANDARD</current-status></rfc-entry>
<rfc-entry><doc-id>RFC9001</doc-id><title>TLS</title><date><year>2021</year></date><current-status>PROPOSED STANDARD</current-status></rfc-entry>
</rfc-index>"""


def test_collect_rfc(monkeypatch):
    seen = fake_get(monkeypatch, {"https://www.rfc-editor.org/rfc-index.xml": RFC_XML})
    rows = sc.collect_rfc(None)
    assert [r["id"] for r in rows] == ["RFC0001", "RFC9000", "RFC9001"]
    r0 = rows[0]
    assert r0 == dict(source="ietf", id="RFC0001", title="Host Software", year="1969", status="UNKNOWN",
                      url="https://www.rfc-editor.org/rfc/rfc0001.txt", access="free", industries="it;telecom;it-security")
    assert rows[1]["year"] == ""
    assert len(sc.collect_rfc(2)) == 2 and len(sc.collect_rfc(0)) == 3
    assert seen[0].endswith("rfc-index.xml")


# ---------------- ecfr ----------------
def test_collect_ecfr(monkeypatch):
    titles = {"titles": [{"number": 10, "name": "Energy", "up_to_date_as_of": "2026-03-04"},
                         {"number": 1, "name": "General Provisions", "up_to_date_as_of": "2026-01-01"},
                         {"number": 49, "name": "Transportation"}]}
    fake_get(monkeypatch, {"https://www.ecfr.gov/api/versioner/v1/titles.json": json.dumps(titles)})
    rows = sc.collect_ecfr(None)
    assert [r["id"] for r in rows] == ["CFR-10", "CFR-49"]
    assert rows[0] == dict(source="ecfr", id="CFR-10", title="Energy", year="2026", status="in force",
                           url="https://www.ecfr.gov/current/title-10", access="free", industries="nuclear;energy")
    assert rows[1]["year"] == "" and rows[1]["industries"] == "transport;pipelines;rail;automotive"
    assert len(sc.collect_ecfr(1)) == 1


# ---------------- lawresorg_bis ----------------
BIS_BASE = "https://law.resource.org/pub/in/bis/"
BIS_INDEX = '<a href="manifest.ced.html">x</a> <a href="manifest.etd.part2.html">y</a> <a href="manifest.zzz.html">z</a> <a href="manifest.ced.html">dup</a>'
BIS_CED = ('<a href="https://archive.org/details/gov.in.is.456.2000">IS 456 (pdf)</a>'
           '<a href="https://archive.org/details/gov.in.is.456.2000">IS 456 (pdf)</a>'
           '<a href="https://archive.org/details/gov.in.is.sp16">SP 16 (pdf)</a>')


def test_collect_lawresorg_bis(monkeypatch, capsys):
    seen = fake_get(monkeypatch, {BIS_BASE: BIS_INDEX, BIS_BASE + "manifest.ced.html": BIS_CED,
                                  BIS_BASE + "manifest.etd.part2.html": RuntimeError("down"),
                                  BIS_BASE + "manifest.zzz.html": '<a href="https://archive.org/details/gov.in.is.9.1999">IS 9 (pdf)</a>'})
    rows = sc.collect_lawresorg_bis(None)
    assert [r["id"] for r in rows] == ["IS 456", "SP 16", "IS 9"]
    assert rows[0] == dict(source="bis-public-resource", id="IS 456", title="gov.in.is.456.2000", year="2000",
                           status="as published", url="https://archive.org/details/gov.in.is.456.2000",
                           access="free", industries="civil;construction;ced")
    assert rows[1]["year"] == "" and rows[2]["industries"] == "zzz;zzz"        # unknown division keeps its own code
    assert "skip manifest.etd.part2.html: down" in capsys.readouterr().err
    assert seen.count(BIS_BASE + "manifest.ced.html") == 1                    # duplicate manifest link fetched once
    assert len(sc.collect_lawresorg_bis(1)) == 1


def test_bis_division_tag_includes_manifest_suffix(monkeypatch):
    fake_get(monkeypatch, {BIS_BASE: '<a href="manifest.etd.part2.html">y</a>',
                           BIS_BASE + "manifest.etd.part2.html": '<a href="https://archive.org/details/gov.in.is.1.2001">IS 1 (pdf)</a>'})
    assert sc.collect_lawresorg_bis(None)[0]["industries"] == "electrical;etd.part2"


# ---------------- itu ----------------
def _itu_row(rid, title):
    return f'<a href="/rec/x?parent=T-REC-{rid}"><strong>{rid}</strong></a></p>\n </td>\n <td class="c">{title}</td>'


def test_collect_itu(monkeypatch, capsys):
    pages = {"https://www.itu.int/rec/T-REC-A/en": _itu_row("A.1", "Work of ITU-T &amp; groups")
             + _itu_row("A.2", "[Withdrawn] Old thing") + _itu_row("A.3", "[Superseded] Newer"),
             "https://www.itu.int/rec/T-REC-D/en": RuntimeError("boom")}
    seen = fake_get(monkeypatch, pages)
    rows = sc.collect_itu(None)
    assert [(r["id"], r["status"], r["title"]) for r in rows] == [
        ("ITU-T A.1", "in force", "Work of ITU-T & groups"), ("ITU-T A.2", "withdrawn", "Old thing"),
        ("ITU-T A.3", "superseded", "Newer")]
    assert rows[0]["industries"] == "telecom;series-A" and rows[0]["url"] == "https://www.itu.int/rec/T-REC-A.1/en"
    assert "skip series D: boom" in capsys.readouterr().err
    assert len([u for u in seen if "T-REC-" in u]) == len(sc.ITU_SERIES)
    assert len(sc.collect_itu(2)) == 2


# ---------------- nasa ----------------
def _nasa_tr(num, alt, title, href, year):
    return (f'<tr><td>{num}</td><td>{alt}</td><td>x</td><td>{title}</td>'
            f'<td><a href="{href}">v</a><time datetime="{year}-01-01"></time></td></tr>')


def test_collect_nasa_paginates_until_empty(monkeypatch):
    p0 = (_nasa_tr("NASA-STD-1", "", "Title One", "/standard/one", 2019)
          + _nasa_tr("NASA-STD-2", "ALT-2", "Title <b>Two</b>", "/standard/two", 2020)
          + "<tr><td>short</td></tr><tr><td>a</td><td>b</td><td>c</td><td>d</td></tr>")   # no link / too few cells
    fake_get(monkeypatch, {f"{sc.NASA_BASE}?page=0": p0, f"{sc.NASA_BASE}?page=1": _nasa_tr("N3", "", "T3", "/standard/3", 2021),
                           f"{sc.NASA_BASE}?page=2": ""})
    rows = sc.collect_nasa(None)
    assert [r["id"] for r in rows] == ["NASA-STD-1", "NASA-STD-2 (ALT-2)", "N3"]
    assert rows[1]["title"] == "Title Two" and rows[1]["year"] == "2020"
    assert rows[0]["url"] == "https://standards.nasa.gov/standard/one" and rows[0]["industries"] == "aerospace;space"
    assert len(sc.collect_nasa(2)) == 2


def test_nasa_year_blank_when_no_datetime(monkeypatch):
    fake_get(monkeypatch, {f"{sc.NASA_BASE}?page=0": '<tr><td>A</td><td></td><td>x</td><td>T</td><a href="/standard/a"></a></tr>'})
    assert sc.collect_nasa(None)[0]["year"] == ""


# ---------------- etsi ----------------
def test_collect_etsi(monkeypatch, capsys):
    pages = {"https://www.etsi.org/deliver/etsi_en/": 'HREF="/deliver/etsi_en/100000_100099/" href="/deliver/etsi_en/200000_200099/"',
             "https://www.etsi.org/deliver/etsi_en/100000_100099/": 'HREF="/deliver/etsi_en/100000_100099/100001/" HREF="/deliver/etsi_en/100000_100099/100002/"',
             "https://www.etsi.org/deliver/etsi_en/200000_200099/": RuntimeError("503"),
             "https://www.etsi.org/deliver/etsi_ts/": 'HREF="/deliver/etsi_ts/1_2/"',
             "https://www.etsi.org/deliver/etsi_ts/1_2/": 'HREF="/deliver/etsi_ts/1_2/7/"'}
    fake_get(monkeypatch, pages)
    rows = sc.collect_etsi(None)
    assert [r["id"] for r in rows] == ["ETSI EN 100001", "ETSI EN 100002", "ETSI TS 7"]
    assert rows[0]["url"] == "https://www.etsi.org/deliver/etsi_en/100000_100099/100001/"
    assert rows[0]["title"] == "(see directory for versions/PDF)" and rows[0]["industries"] == "telecom;it"
    assert "skip etsi_en/200000_200099: 503" in capsys.readouterr().err
    assert len(sc.collect_etsi(1)) == 1


# ---------------- china ----------------
def _china_tr(h, gb, adopt, title, status, date, extra="-"):
    cells = ["1", gb, "x", adopt, title, extra, status, date, "z"]
    return f"<tr><a onclick=\"showInfo('{h}')\">i</a>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def test_collect_china(monkeypatch):
    base = "https://openstd.samr.gov.cn/bzgk/std/std_list?p.p1=0&p.p90=circulation_date&p.p91=desc&page={}&pageSize=50"
    p1 = (_china_tr("AB12", "GB/T 1-2020", "采", "Title A", "现行", "2020-05-01")
          + _china_tr("CD34", "GB 2", "x", "Title B", "", "2019-01-01", extra="Fallback")
          + "<tr><td>few</td></tr>")
    fake_get(monkeypatch, {base.format(1): p1, base.format(2): ""})
    rows = sc.collect_china(None)
    assert len(rows) == 2
    assert rows[0] == dict(source="china-gb", id="GB/T 1-2020", title="Title A", year="2020", status="现行",
                           access="view-only", adopts_intl="yes",
                           url="https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=AB12", industries="china;national-standard")
    assert rows[1]["adopts_intl"] == "no" and rows[1]["status"] == "Fallback"      # empty status falls back to cells[5]
    assert len(sc.collect_china(1)) == 1


# ---------------- korea ----------------
def _korea_tr(no, title, date, view=True):
    v = "fnGoStdView('a','b','c')" if view else ""
    return (f'<tr class="mflex bottom"><td class="mobiletd">{no}</td><td class="tl mobiletd">{title}</td>'
            f'<td class="mobiletd">{date}</td><a onclick="{v}"></a></tr>')


def test_collect_korea(monkeypatch):
    pages = [_korea_tr("KS A 0001", "Basic", "2020-01-01") + _korea_tr("KS C 1", "Elec 폐지", "2019-02-03")
             + _korea_tr("KS Z 9", "Odd", "2018-01-01") + _korea_tr("XX 1", "NoClass", "2017-01-01")
             + _korea_tr("KS B 2", "NoView", "2016-01-01", view=False), ""]
    posts = []

    def fake_open(req, timeout):
        posts.append((req.full_url, req.data, req.get_header("User-agent")))
        return _Resp(pages[len(posts) - 1].encode())

    monkeypatch.setattr(sc.urllib.request, "urlopen", fake_open)
    rows = sc.collect_korea(None)
    assert [r["id"] for r in rows] == ["KS A 0001", "KS C 1", "KS Z 9", "XX 1"]
    assert rows[0]["industries"] == "basic" and rows[0]["year"] == "2020" and rows[0]["status"] == "in force"
    assert rows[1]["status"] == "abolished" and rows[1]["industries"] == "electrical;electronics"
    assert rows[2]["industries"] == "other" and rows[3]["industries"] == "other"
    assert rows[0]["url"].endswith("ksNo=KS%20A%200001") and rows[0]["access"] == "view-only"
    assert posts[0][1] == b"pageUnit=100&pageIndex=1" and posts[1][1] == b"pageUnit=100&pageIndex=2"
    assert posts[0][2] == sc.UA


def test_collect_korea_limit(monkeypatch):
    monkeypatch.setattr(sc.urllib.request, "urlopen",
                        lambda req, timeout: _Resp((_korea_tr("KS A 1", "a", "2020") + _korea_tr("KS A 2", "b", "2020")).encode()))
    assert len(sc.collect_korea(1)) == 1


# ---------------- saudi / japan ----------------
def test_collect_saudi(monkeypatch):
    html = ('<a href="/en/Laws-And-Regulations/public_multimedia/Pages/12_3.aspx"> Draft &amp; Title </a>'
            '<a href="/en/Laws-And-Regulations/public_multimedia/Pages/45_6.aspx">ab</a>'
            '<a href="/en/Laws-And-Regulations/public_multimedia/Pages/78_9.aspx">Another draft</a>')
    fake_get(monkeypatch, {"https://www.saso.gov.sa/en/sitemap/Pages/default.aspx": html})
    rows = sc.collect_saudi(None)
    assert [r["id"] for r in rows] == ["SASO-draft-12", "SASO-draft-78"]         # titles shorter than 3 chars skipped
    assert rows[0]["title"] == "Draft & Title"
    assert rows[0]["url"] == "https://www.saso.gov.sa/en/Laws-And-Regulations/public_multimedia/Pages/12_3.aspx"
    assert rows[0]["status"] == "draft for public consultation"
    assert len(sc.collect_saudi(1)) == 1


def test_collect_japan_branches(monkeypatch):
    def down(req, timeout):
        raise OSError("502")

    monkeypatch.setattr(sc.urllib.request, "urlopen", down)
    with pytest.raises(RuntimeError, match="JISC unavailable"):
        sc.collect_japan(None)
    monkeypatch.setattr(sc.urllib.request, "urlopen", lambda req, timeout: _Resp(b""))
    with pytest.raises(NotImplementedError):
        sc.collect_japan(None)


# ---------------- eu harmonised ----------------
class _Sheet:
    def __init__(self, rows):
        self.rows = rows

    def iter_rows(self, values_only):
        assert values_only is True
        return iter(self.rows)


def _install_openpyxl(monkeypatch, books):
    mod = types.ModuleType("openpyxl")
    loaded = []

    def load_workbook(fh, read_only):
        assert read_only is True
        data = fh.read()
        loaded.append(data)
        v = books[data]
        if isinstance(v, Exception):
            raise v
        return [_Sheet(r) for r in v]

    mod.load_workbook = load_workbook
    monkeypatch.setitem(sys.modules, "openpyxl", mod)
    return loaded


ROOT = "https://single-market-economy.ec.europa.eu"
IDX_URL = ROOT + "/single-market/european-standards/harmonised-standards_en"
HS = "/single-market/goods/european-standards/harmonised-standards/"


def _eu_setup(monkeypatch, monkeypatch_env=True):
    monkeypatch.setenv("STD_EU_PACE", "0")
    monkeypatch.delenv("STD_EU_ONLY", raising=False)
    idx = "".join(f'href="{HS}{n}_en"' for n in ("machinery", "toys", "formal-objections", "x-old", "new-legislative-x", "empty"))
    pages = {
        IDX_URL: idx,
        ROOT + HS + "machinery_en": 'href="/files/a.xlsx?x=1&amp;y=2" href="/files/a.xlsx?x=1&amp;y=2" href="https://other.org/b.XLSX"',
        ROOT + HS + "toys_en": 'href="/files/t.xlsx"',
        ROOT + HS + "empty_en": "<p>no sheets</p>",
        ROOT + "/files/a.xlsx?x=1&y=2": b"A",
        "https://other.org/b.XLSX": b"B",
        ROOT + "/files/t.xlsx": b"T",
    }
    rows_a = [[("Legislation", "Type", "ident", 0, 0, 0, 0, 0)],
              [("Directive 2006/42/EC", "Type A", "EN 1234:2010\nMachine safety", 0, 0, 0, 0, None),
               ("Directive 2006/42/EC", "Type A", "EN 1234:2010\nDuplicate", 0, 0, 0, 0, None),
               ("Directive 2006/42/EC", "Type B", "EN 9999\n", 0, 0, 0, 0, "withdrawn"),
               ("Generated on 2026", "x", "ignored", 0, 0, 0, 0, 0),
               ("Dir", "T", None, 0, 0, 0, 0, 0),
               ("Dir", "T", "short", 0, 0),
               None]]
    return pages, {b"A": rows_a, b"B": RuntimeError("bad xlsx"),
                   b"T": [[("Toy Directive", "Toys", "EN 71-1:2014+A1\nToy safety", 0, 0, 0, 0, None)]]}


def test_collect_eu_harmonised(monkeypatch, capsys):
    pages, books = _eu_setup(monkeypatch)
    fake_get(monkeypatch, pages)
    _install_openpyxl(monkeypatch, books)
    rows = sc.collect_eu_harmonised(None)
    assert [r["id"] for r in rows] == ["EN 1234:2010", "EN 9999", "EN 71-1:2014+A1"]
    r0, r1, r2 = rows
    assert r0["title"] == "Machine safety" and r0["year"] == "2010" and r0["status"] == "cited in OJEU"
    assert r0["industries"] == "eu;machinery;type a;Directive 2006/42/EC" and r0["access"] == "paid"
    assert r1["status"] == "withdrawn" and r1["title"] == "" and r1["year"] == ""
    assert r2["year"] == "2014" and r2["industries"].startswith("eu;toys;toys;")
    assert r0["url"] == ROOT + "/files/a.xlsx?x=1&y=2"                          # html-unescaped, de-duplicated link
    err = capsys.readouterr().err
    assert "no spreadsheet on empty_en" in err and "skip xlsx" in err
    assert len(sc.collect_eu_harmonised(1)) == 1


@pytest.mark.xfail(strict=True, raises=IndexError,
                   reason="stdcollect.py collect_eu_harmonised: a spreadsheet row whose identifier cell is only "
                          "whitespace gives lines == [] and `lines[0]` raises, aborting the whole collector")
def test_eu_harmonised_blank_identifier_cell_is_skipped(monkeypatch):
    pages, books = _eu_setup(monkeypatch)
    books[b"A"] = [[("Dir", "T", "  \n  ", 0, 0, 0, 0, 0), ("Dir", "T", "EN 1:2000\nOK", 0, 0, 0, 0, None)]]
    fake_get(monkeypatch, pages)
    _install_openpyxl(monkeypatch, books)
    assert [r["id"] for r in sc.collect_eu_harmonised(None) if r["url"].endswith("y=2")] == ["EN 1:2000"]


def test_eu_harmonised_only_env_and_page_error(monkeypatch, capsys):
    pages, books = _eu_setup(monkeypatch)
    pages[ROOT + HS + "toys_en"] = RuntimeError("503")
    fake_get(monkeypatch, pages)
    _install_openpyxl(monkeypatch, books)
    monkeypatch.setenv("STD_EU_ONLY", "toys,machinery")
    assert [r["id"] for r in sc.collect_eu_harmonised(None)][0] == "EN 1234:2010"
    assert "skip " + HS + "toys_en: 503" in capsys.readouterr().err
    monkeypatch.setenv("STD_EU_ONLY", "toys")
    assert sc.collect_eu_harmonised(None) == []


def test_eu_harmonised_pace_from_env(monkeypatch, _no_sleep):
    pages, books = _eu_setup(monkeypatch)
    monkeypatch.setenv("STD_EU_PACE", "2.5")
    fake_get(monkeypatch, pages)
    _install_openpyxl(monkeypatch, books)
    sc.collect_eu_harmonised(None)
    assert set(_no_sleep) == {2.5}


def test_eu_harmonised_requires_openpyxl(monkeypatch):
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    with pytest.raises(RuntimeError, match="pip install openpyxl"):
        sc.collect_eu_harmonised(None)


# ---------------- lawresorg_world ----------------
def _pro_tr(url, label, year, cat, title, kind="pdf"):
    return f'<tr><td><a href="{url}">{label} ({kind})</a></td><td>{year}</td><td>{cat}</td><td>{title}</td></tr>'


def test_collect_lawresorg_world(monkeypatch, capsys):
    top = ('<td><a href="au/manifest.au.html">Australia</a></td><td><a href="nz/manifest.nz.html">New Zealand</a></td>'
           '<td><a href="xx/manifest.xx.html">Broken</a></td>')
    au = (_pro_tr("https://archive.org/details/au.1", "AS 1", "2001", "Cat", "Title &amp; one")
          + _pro_tr("https://archive.org/details/au.1", "AS 1 dup", "2001", "Cat", "Dup")
          + _pro_tr("https://archive.org/details/au.2", "AS 2", "2002", "Cat2", "Two", kind="html")
          + '<tr><td>no link</td><td>1</td><td>2</td><td>3</td></tr>'
          + '<tr><td><a href="https://archive.org/details/au.3">AS 3</a></td><td>1</td></tr>')
    fake_get(monkeypatch, {"https://law.resource.org/pub/table01.html": top, "https://law.resource.org/pub/au/": au,
                           "https://law.resource.org/pub/nz/": _pro_tr("https://archive.org/details/nz.1", "NZS 1", "1999", "C", "T"),
                           "https://law.resource.org/pub/xx/": RuntimeError("gone")})
    rows = sc.collect_lawresorg_world(None)
    assert [r["id"] for r in rows] == ["AS 1", "AS 2", "NZS 1"]
    assert rows[0] == dict(source="pro-au", id="AS 1", title="Title & one", year="2001", status="as incorporated",
                           url="https://archive.org/details/au.1", access="free", industries="Australia;Cat")
    assert rows[2]["source"] == "pro-nz"
    err = capsys.readouterr().err
    assert "au (Australia): 2" in err and "nz (New Zealand): 1" in err and "skip xx: gone" in err
    assert len(sc.collect_lawresorg_world(1)) == 1


def test_lawresorg_world_industries_truncated_to_120(monkeypatch):
    top = '<td><a href="au/manifest.au.html">Australia</a></td>'
    fake_get(monkeypatch, {"https://law.resource.org/pub/table01.html": top,
                           "https://law.resource.org/pub/au/": _pro_tr("https://archive.org/details/a", "A", "1", "c" * 300, "T")})
    assert len(sc.collect_lawresorg_world(None)[0]["industries"]) == 120


# ---------------- ecfr_ibr ----------------
TITLES = json.dumps({"titles": [{"number": n, "up_to_date_as_of": f"2026-0{n % 9 + 1}-01"}
                                for n in (10, 29, 30, 33, 40, 46, 49)]})


def _ibr_urlopen(monkeypatch, per_url):
    reqs = []

    def fake_open(req, timeout):
        reqs.append((req.full_url, req.get_header("Accept-encoding"), timeout))
        v = per_url(req.full_url)
        if isinstance(v, Exception):
            raise v
        return _Resp(v)

    monkeypatch.setattr(sc.urllib.request, "urlopen", fake_open)
    return reqs


def test_collect_ecfr_ibr(monkeypatch, capsys):
    fake_get(monkeypatch, {"https://www.ecfr.gov/api/versioner/v1/titles.json": TITLES})
    xml = ("<DIV><P>ASTM A106-19a Standard Specification for Seamless Carbon Steel Pipe, IBR approved for this section.</P>"
           "<P>NIST SP 800-53, security controls; API 650 Welded Tanks, incorporated by reference. ASTM A106-19a again.</P>"
           "<P>Nothing relevant here.</P></DIV>").encode()
    reqs = _ibr_urlopen(monkeypatch, lambda u: gzip.compress(xml) if "part=1910&" in u else (xml if "part=1926" in u else RuntimeError("500")))
    rows = sc.collect_ecfr_ibr(None)
    ids = [(r["id"], r["access"]) for r in rows]
    assert ids[0] == ("ASTM A106-19a", "paid")
    assert ("NIST SP 800-53", "free") in ids and any(i[0].startswith("API 650") for i in ids)
    assert len([r for r in rows if r["id"] == "ASTM A106-19a" and "1910.6" in r["url"]]) == 1    # de-duplicated within a section
    r0 = rows[0]
    assert r0["title"] == "Standard Specification for Seamless Carbon Steel Pipe" and r0["status"] == "incorporated by reference"
    assert r0["url"] == "https://www.ecfr.gov/current/title-29/section-1910.6"
    assert r0["industries"] == "safety;process-safety;general-industry;astm;cfr-29-1910.6"
    assert reqs[0][1] == "gzip" and reqs[0][2] == 120
    assert "/title-29.xml?part=1910&section=1910.6" in reqs[0][0]
    err = capsys.readouterr().err
    assert "skip 49 CFR 171.7: 500" in err and "29 CFR 1910.6:" in err
    assert len(sc.collect_ecfr_ibr(1)) == 1


# ---------------- emit / commands ----------------
ROWS = [{"id": "a", "name": "Alpha | Beta", "x": 1}, {"id": "bb", "name": "B", "x": 2}]


def test_emit_formats(capsys):
    sc.emit(ROWS, ["id", "name"], "csv")
    assert capsys.readouterr().out.splitlines() == ["id,name", 'a,Alpha | Beta', "bb,B"]
    sc.emit(ROWS, ["id", "name"], "md")
    assert capsys.readouterr().out.splitlines() == ["| id | name |", "|---|---|", "| a | Alpha / Beta |", "| bb | B |"]
    sc.emit(ROWS, ["id", "name"], "table")
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "ID  NAME        " and lines[1] == "a   Alpha | Beta" and lines[2].startswith("bb  B ")
    sc.emit([], ["id"], "table")
    assert capsys.readouterr().out == "\n"
    sc.emit([{"id": "x" * 60}], ["id"], "table")
    assert capsys.readouterr().out.splitlines()[1] == "x" * 48          # width capped at 48
