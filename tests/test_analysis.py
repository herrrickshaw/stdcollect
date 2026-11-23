import csv
import urllib.error

import pytest

FIELDS = ["source", "id", "title", "year", "status", "url", "access", "industries", "adopts_intl"]


def write_catalog(root, name, rows):
    with (root / "catalog" / name).open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS, restval="")
        w.writeheader()
        w.writerows(rows)


def read_csv(path):
    return list(csv.reader(path.open()))


class Resp:
    def __init__(self, text):
        self.text = text
        self.asked = None

    def read(self, n=None):
        self.asked = n
        return self.text.encode() if n is None else self.text.encode()[:n]


def fake_urlopen(monkeypatch, per_url):
    calls = []

    def f(req, timeout):
        calls.append((req.full_url, req.get_header("User-agent"), timeout))
        v = per_url(req.full_url)
        if isinstance(v, BaseException):
            raise v
        return Resp(v)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", f)
    import time
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    return calls, sleeps


def http_error(code):
    return urllib.error.HTTPError("u", code, "m", {}, None)


BIS = [
    dict(source="bis-public-resource", id="IS/ISO 9001", title="gov.in.is.iso.9001", year="2015",
         url="https://archive.org/details/gov.in.is.iso.9001.2015"),
    dict(source="bis-public-resource", id="IS/IEC 61010", title="x", year="2010",
         url="https://archive.org/details/gov.in.is.iec.61010.2010"),
    dict(source="bis-public-resource", id="IS 456", title="not an adoption", year="2000",
         url="https://archive.org/details/gov.in.is.456.2000"),
    dict(source="bis-public-resource", id="IS/ISO 1", title="gone", year="2001",
         url="https://archive.org/details/gov.in.is.iso.1.2001"),
]

TEXT = """
 1 Scope
 This standard covers the dimensions. The thickness shall be not less than 10 mm in all cases and tested.
 2.1 Materials and tools ...........
 3 Terms 123
 2.1.1 Sampling
 Material shall be at least 25 kPa when measured within 5 min of mixing.
 1 Scope
"""


# ---------------- clauses_in.py ----------------
def test_clauses_in_extracts_headings_and_specs(analysis, monkeypatch, capsys):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS)
    calls, sleeps = fake_urlopen(monkeypatch, lambda u: http_error(404) if ".iso.1." in u else TEXT)
    analysis("clauses_in.py")
    cl = read_csv(analysis.root / "analysis" / "clauses.csv")
    assert cl[0] == ["national_id", "clause", "heading", "url"]
    got = {(r[0], r[1], r[2]) for r in cl[1:]}
    assert ("IS/ISO 9001", "1", "Scope") in got and ("IS/ISO 9001", "2.1.1", "Sampling") in got
    assert not any("Materials and tools" in h or h.startswith("Terms") for _, _, h in got)     # TOC dots / trailing number rejected
    assert sum(1 for r in cl[1:] if r[0] == "IS/ISO 9001" and r[1] == "1") == 1                  # duplicate heading collapsed
    assert ["IS/ISO 1", "", "(text unavailable)", BIS[3]["url"]] in cl
    assert not any(r[0] == "IS 456" for r in cl[1:])                                              # only ISO/IEC adoptions
    sp = read_csv(analysis.root / "analysis" / "specs.csv")
    assert sp[0] == ["national_id", "clause", "spec_snippet", "value_unit", "url"]
    units = [r[3] for r in sp[1:] if r[0] == "IS/ISO 9001"]
    # the greedy prefix backtracks from the end, so each sentence yields its LAST keyword's quantity
    assert units == ["10 mm", "5 min"]
    assert capsys.readouterr().out.strip() == "done 3"
    assert calls[0][0] == "https://archive.org/download/gov.in.is.iso.9001.2015/is.iso.9001.2015.txt"
    assert calls[0][1] == "stdcollect/0.1" and calls[0][2] == 90
    assert sleeps.count(1) == 3                       # 1 request per second


def test_clauses_in_no_headings_marker_and_resume(analysis, monkeypatch, capsys):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:1])
    fake_urlopen(monkeypatch, lambda u: "plain prose without numbering")
    analysis("clauses_in.py")
    cl = read_csv(analysis.root / "analysis" / "clauses.csv")
    assert cl[1] == ["IS/ISO 9001", "", "(no numbered clauses recognised)", BIS[0]["url"]]
    # a second run skips URLs already present and does not rewrite the header
    calls, _ = fake_urlopen(monkeypatch, lambda u: "x")
    analysis("clauses_in.py")
    assert calls == [] and len(read_csv(analysis.root / "analysis" / "clauses.csv")) == 2
    assert capsys.readouterr().out.count("done 1") == 2


def test_clauses_in_spec_cap_is_40_per_standard(analysis, monkeypatch):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:1])
    text = "\n".join(f"Item {i} shall be at least {i} mm long." for i in range(60))
    fake_urlopen(monkeypatch, lambda u: text)
    analysis("clauses_in.py")
    assert len(read_csv(analysis.root / "analysis" / "specs.csv")) - 1 == 40


def test_clauses_in_fetch_retries(analysis, monkeypatch):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:1])
    seq = iter([http_error(500), OSError("net"), TEXT])

    def per(u):
        v = next(seq)
        return v
    calls, sleeps = fake_urlopen(monkeypatch, per)
    analysis("clauses_in.py")
    assert len(calls) == 3 and sleeps[:2] == [10, 5]
    assert len(read_csv(analysis.root / "analysis" / "clauses.csv")) > 2


def test_clauses_in_gives_up_after_three_attempts(analysis, monkeypatch):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:1])
    calls, sleeps = fake_urlopen(monkeypatch, lambda u: http_error(500))
    analysis("clauses_in.py")
    assert len(calls) == 3 and [s for s in sleeps if s != 1] == [10, 20, 40]
    assert read_csv(analysis.root / "analysis" / "clauses.csv")[1][2] == "(text unavailable)"


# ---------------- degree_in.py ----------------
@pytest.mark.parametrize("text,degree,evidence_part", [
    ("This standard is identical with ISO 9001 : 2015 Quality systems.", "identical", "identical with ISO 9001"),
    ("This is technically equivalent to the ISO text.", "modified", "technically equivalent"),
    ("The text has been modified for Indian conditions.", "modified", "modified"),
    ("Nothing about the relationship appears here.", "unknown", "no equivalence statement in first 12k chars"),
])
def test_degree_classification(analysis, monkeypatch, capsys, text, degree, evidence_part):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:1])
    fake_urlopen(monkeypatch, lambda u: "Foreword. " + text)
    analysis("degree_in.py")
    rows = read_csv(analysis.root / "analysis" / "degree.csv")
    assert rows[0] == ["national_id", "year", "degree", "evidence", "url"]
    assert rows[1][:3] == ["IS/ISO 9001", "2015", degree] and evidence_part in rows[1][3]
    assert capsys.readouterr().out.strip() == "degree rows: 1 of 1"


def test_degree_evidence_truncated_and_text_unavailable(analysis, monkeypatch):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:1] + BIS[3:])
    long_ev = "identical with " + "x" * 400

    def per(u):
        return http_error(403) if ".iso.1." in u else long_ev

    fake_urlopen(monkeypatch, per)
    analysis("degree_in.py")
    rows = read_csv(analysis.root / "analysis" / "degree.csv")
    assert len(rows[1][3]) <= 160 and rows[1][2] == "identical"
    assert rows[2][2:4] == ["unknown", "text unavailable"]


def test_degree_only_scans_first_12000_chars_and_reads_40000_bytes(analysis, monkeypatch):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:1])
    late = "a" * 12100 + " identical with ISO 1."
    fake_urlopen(monkeypatch, lambda u: late)
    analysis("degree_in.py")
    assert read_csv(analysis.root / "analysis" / "degree.csv")[1][2] == "unknown"


def test_degree_fetch_retries_generic_errors_with_5s_pause(analysis, monkeypatch):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:1])
    seq = iter([OSError("net"), "identical with x"])
    calls, sleeps = fake_urlopen(monkeypatch, lambda u: next(seq))
    analysis("degree_in.py")
    assert len(calls) == 2 and 5 in sleeps
    assert read_csv(analysis.root / "analysis" / "degree.csv")[1][2] == "identical"


def test_degree_resumes_and_retries(analysis, monkeypatch):
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:2])
    calls, sleeps = fake_urlopen(monkeypatch, lambda u: "adapted from ISO")
    analysis("degree_in.py")
    assert len(calls) == 2
    calls2, _ = fake_urlopen(monkeypatch, lambda u: "x")
    analysis("degree_in.py")
    assert calls2 == [] and len(read_csv(analysis.root / "analysis" / "degree.csv")) == 3
    # retry ladder: 4 attempts with exponential sleeps
    write_catalog(analysis.root, "lawresorg_bis.csv", BIS[:1])
    (analysis.root / "analysis" / "degree.csv").unlink()
    calls3, sleeps3 = fake_urlopen(monkeypatch, lambda u: http_error(503))
    analysis("degree_in.py")
    assert len(calls3) == 4 and [s for s in sleeps3 if s != 1] == [10, 20, 40, 80]


# ---------------- link_standards.py ----------------
def test_key_extraction(analysis):
    write_catalog(analysis.root, "empty.csv", [])
    key = analysis("link_standards.py")["key"]
    assert key("ISO 9001:2015") == {"ISO 9001"}
    assert key("ISO/IEC 27001") == {"ISO/IEC 27001"}                      # joint standard is not also read as ISO / IEC
    assert key("IS/ISO 9001-1") == {"ISO 9001-1"}
    assert key("BS EN ISO 14001") == {"ISO 14001"}
    assert key("IEC 61010-1") == {"IEC 61010-1"}
    assert key("EN 61010–1") == {"IEC 61010-1"}                            # en dash normalised
    assert key("EN 12345") == set()                                        # EN 6xxxx only
    assert key("KS C IEC 60034.1") == {"IEC 60034-1"}
    assert key("nothing") == set()
    assert key("ISO 1 and ISO 2") == {"ISO 1", "ISO 2"}


def test_link_standards_outputs(analysis, capsys):
    write_catalog(analysis.root, "a.csv", [
        dict(source="bis-public-resource", id="IS/ISO 9001", title="Quality", url="u1"),
        dict(source="korea-ks", id="KS Q ISO 9001", title="Quality mgmt", url="u2"),
        dict(source="china-gb", id="GB/T 19001", title="Quality systems ISO 9001 text", url="u3"),
        dict(source="eu-harmonised", id="EN 1", title="Uses ISO 14001 here", url="u4"),
        dict(source="saso-drafts", id="SASO-1", title="ISO 14001 draft", url="u5"),
        dict(source="unknown-src", id="ISO 777", title="t", url="u6")])
    write_catalog(analysis.root, "b.csv", [dict(source="bis-public-resource", id="IS 1", title="IEC 1 mention", url="u7")])
    analysis("link_standards.py")
    links = read_csv(analysis.root / "analysis" / "links.csv")
    assert links[0] == ["intl_standard", "country_or_bloc", "source", "national_id", "title", "url"]
    by = {(r[0], r[1]) for r in links[1:]}
    assert ("ISO 9001", "India") in by and ("ISO 9001", "South Korea") in by and ("ISO 9001", "China") in by
    assert ("ISO 14001", "EU (CEN/CENELEC)") in by and ("ISO 14001", "Saudi Arabia") in by
    assert ("ISO 777", "unknown-src") in by                                 # unmapped source keeps its own name
    assert ("IEC 1", "India") in by                                         # national titles are read up to 60 chars
    cl = read_csv(analysis.root / "analysis" / "clusters.csv")
    assert cl[0] == ["intl_standard", "n_countries", "countries", "national_ids"]
    assert cl[1] == ["ISO 9001", "3", "China; India; South Korea", "GB/T 19001 | IS/ISO 9001 | KS Q ISO 9001"]
    assert cl[2][:3] == ["ISO 14001", "2", "EU (CEN/CENELEC); Saudi Arabia"]        # most countries first
    assert [r[0] for r in cl[3:]] == ["IEC 1", "ISO 777"]                           # ties broken alphabetically
    assert capsys.readouterr().out.strip() == "7 links; 4 intl standards; 2 in >=2 countries/blocs; 1 >=3"


def test_link_standards_title_truncation_rule(analysis):
    long_title = "x" * 70 + " ISO 5555"
    write_catalog(analysis.root, "a.csv", [
        dict(source="bis-public-resource", id="IS 1", title=long_title, url="u"),            # national title cut at 60 chars
        dict(source="eu-harmonised", id="EN 2", title=long_title, url="u"),                  # EU/SASO titles are read whole
        dict(source="bis-public-resource", id="IS 3", title="ISO 4444", url="u")])
    analysis("link_standards.py")
    keys = {r[0] for r in read_csv(analysis.root / "analysis" / "links.csv")[1:]}
    assert keys == {"ISO 5555", "ISO 4444"}
    src = {r[2] for r in read_csv(analysis.root / "analysis" / "links.csv")[1:] if r[0] == "ISO 5555"}
    assert src == {"eu-harmonised"}


def test_link_standards_summary_line(analysis, capsys):
    write_catalog(analysis.root, "a.csv", [
        dict(source="bis-public-resource", id="IS/ISO 1", title="t", url="u"),
        dict(source="korea-ks", id="KS A ISO 1", title="t", url="u"),
        dict(source="china-gb", id="GB ISO 1", title="t", url="u"),
        dict(source="itu-t", id="ISO 2", title="t", url="u")])
    analysis("link_standards.py")
    assert capsys.readouterr().out.strip() == "4 links; 2 intl standards; 1 in >=2 countries/blocs; 1 >=3"


# ---------------- sector_chains.py ----------------
def test_sector_chains(analysis, capsys):
    write_catalog(analysis.root, "k.csv", [
        dict(source="korea-ks", id="KS C ISO 9001", title="Elec", industries="electrical;electronics"),
        dict(source="korea-ks", id="KS C ISO 9001", title="Elec2", industries="electrical;electronics"),
        dict(source="korea-ks", id="KS D ISO 9001", title="Metals", industries="metals;steel"),
        dict(source="korea-ks", id="KS X ISO 5", title="Odd", industries="mystery-class")])
    write_catalog(analysis.root, "e.csv", [
        dict(source="eu-harmonised", id="EN ISO 9001", title="t", industries="eu;machinery;type a;Directive"),
        dict(source="bis-public-resource", id="IS/ISO 9001", title="t", industries="civil;construction;ced.part1"),
        dict(source="ecfr-ibr", id="ASTM A1", title="t", industries="safety;astm;cfr-29-1910.6"),
        dict(source="ecfr-ibr", id="ASTM A2", title="t", industries="safety;astm;cfr-29-1910.6"),
        dict(source="ecfr-ibr", id="API 5", title="t", industries="safety;api;cfr-29-1910.6"),
        dict(source="rfc", id="RFC 1", title="ISO 1", industries="x")])
    analysis("sector_chains.py")
    chains = read_csv(analysis.root / "analysis" / "sector_chains.csv")
    assert chains[0] == ["catalog", "sector", "n_intl_standards", "most_recurring_intl_standards"]
    rows = {(r[0], r[1]): r for r in chains[1:]}
    assert rows[("Korea KS", "electrical-electronics")][3] == "ISO 9001 (2)"
    assert ("Korea KS", "mystery-class") in rows and ("EU harmonised", "eu-machinery") in rows
    assert ("India BIS", "bis-ced-part1") in rows
    assert not any(r[0] == "ecfr-ibr" for r in chains[1:])
    bridges = read_csv(analysis.root / "analysis" / "sector_bridges.csv")
    assert bridges[0] == ["intl_standard", "n_sectors", "sectors"]
    assert len(bridges) == 2 and bridges[1][:2] == ["ISO 9001", "4"]
    assert bridges[1][2] == "EU harmonised:eu-machinery; India BIS:bis-ced-part1; Korea KS:electrical-electronics; Korea KS:metals-steel"
    ibr = read_csv(analysis.root / "analysis" / "ibr_sector_bodies.csv")
    assert ibr == [["cfr_section", "bodies_incorporated"], ["cfr-29-1910.6", "ASTM (2); API (1)"]]
    assert capsys.readouterr().out.strip() == "5 sector rows; 1 bridge standards; 1 CFR sections"
