import csv
import json
import sys
import types

import pytest

import stdcollect as sc

REGISTRY = [
    {"id": "iso", "name": "International Organization for Standardization", "region": "global", "access": "paid",
     "typical_price": "CHF 100", "free_part": "none", "url": "http://iso", "industries": ["oil-gas", "it"]},
    {"id": "ietf", "name": "IETF", "region": "global", "access": "free", "typical_price": "0", "free_part": "all",
     "url": "http://ietf", "industries": ["it", "telecom"]},
    {"id": "api", "name": "American Petroleum Institute", "region": "us", "access": "freemium", "typical_price": "USD 80",
     "free_part": "read-only", "url": "http://api", "industries": ["Oil-Gas"]},
]
COUNTRIES = [{"code": "IN", "country": "India", "body": "BIS", "access": "freemium", "region": "South Asia", "url": "u1"},
             {"code": "JP", "country": "Japan", "body": "JISC", "access": "paid", "region": "East Asia", "url": "u2"},
             {"code": "KR", "country": "South Korea", "body": "KATS", "access": "paid", "region": "East Asia", "url": "u3"}]
SECTORS = {"oil-gas-sector": ["iso", "api", "missing-id"], "telecom-sector": ["ietf"]}


@pytest.fixture
def home(tmp_path, monkeypatch):
    (tmp_path / "registry.json").write_text(json.dumps(REGISTRY))
    (tmp_path / "countries.json").write_text(json.dumps(COUNTRIES))
    (tmp_path / "sectors.json").write_text(json.dumps(SECTORS))
    monkeypatch.setattr(sc, "HERE", tmp_path)
    monkeypatch.setattr(sc.time, "sleep", lambda s: None)
    return tmp_path


def run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["stdcollect.py", *argv])
    sc.main()


# ---------------- bodies ----------------
def test_bodies_table_default_columns_and_count(home, monkeypatch, capsys):
    run(monkeypatch, "bodies")
    cap = capsys.readouterr()
    lines = cap.out.splitlines()
    assert lines[0].split() == ["ID", "NAME", "REGION", "ACCESS", "TYPICAL_PRICE", "INDUSTRIES"]
    assert len(lines) == 4 and "oil-gas;it" in lines[1]
    assert cap.err.strip() == "3 bodies"


def test_bodies_filters(home, monkeypatch, capsys):
    run(monkeypatch, "bodies", "--industry", "OIL-GAS")
    cap = capsys.readouterr()
    assert "iso" in cap.out and "ietf" not in cap.out and cap.err.strip() == "1 bodies"     # argument is lower-cased
    run(monkeypatch, "bodies", "--industry", "it")
    cap = capsys.readouterr()
    assert cap.err.strip() == "2 bodies" and "ietf" in cap.out and "iso" in cap.out
    run(monkeypatch, "bodies", "--access", "free")
    cap = capsys.readouterr()
    assert cap.err.strip() == "1 bodies" and "ietf" in cap.out and "iso" not in cap.out


def test_bodies_industry_and_access_combined(home, monkeypatch, capsys):
    run(monkeypatch, "bodies", "--industry", "oil", "--access", "freemium")
    cap = capsys.readouterr()
    assert cap.err.strip() == "0 bodies"     # api's industry is 'Oil-Gas' (capitalised): the match is case-sensitive on the data side
    run(monkeypatch, "bodies", "--industry", "oil", "--access", "paid")
    assert capsys.readouterr().err.strip() == "1 bodies"


def test_bodies_csv_columns(home, monkeypatch, capsys):
    run(monkeypatch, "bodies", "--format", "csv", "--access", "free")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "id,name,region,access,typical_price,free_part,url"
    assert out[1] == "ietf,IETF,global,free,0,all,http://ietf"


# ---------------- countries ----------------
def test_countries_filters(home, monkeypatch, capsys):
    run(monkeypatch, "countries", "--format", "csv")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "code,country,body,access,region,url" and len(out) == 4
    run(monkeypatch, "countries", "--region", "asia", "--format", "csv")
    assert len(capsys.readouterr().out.splitlines()) == 4
    run(monkeypatch, "countries", "--region", "east", "--access", "paid", "--format", "csv")
    assert len(capsys.readouterr().out.splitlines()) == 3
    run(monkeypatch, "countries", "--country", "korea", "--format", "csv")
    assert capsys.readouterr().out.splitlines()[1:] == ["KR,South Korea,KATS,paid,East Asia,u3"]
    run(monkeypatch, "countries", "--country", "jp", "--format", "csv")           # matches the code too
    assert capsys.readouterr().out.splitlines()[1].startswith("JP,")
    run(monkeypatch, "countries", "--country", "zzz", "--format", "csv")
    assert capsys.readouterr().out.splitlines() == ["code,country,body,access,region,url"]


# ---------------- sectors ----------------
def test_sectors(home, monkeypatch, capsys):
    run(monkeypatch, "sectors", "--format", "csv")
    out = capsys.readouterr().out
    assert "== oil-gas-sector ==" in out and "== telecom-sector ==" in out
    assert "  free: none" in out and "  free: ietf" in out
    assert "missing-id" not in out                                   # ids absent from the registry are skipped
    assert "iso,International Organization for Standardization"[:20] in out
    run(monkeypatch, "sectors", "--sector", "TELE", "--format", "csv")
    out = capsys.readouterr().out
    assert "telecom-sector" in out and "oil-gas" not in out


def test_sectors_name_truncated_to_44(home, monkeypatch, capsys):
    run(monkeypatch, "sectors", "--sector", "oil", "--format", "csv")
    out = capsys.readouterr().out
    assert "International Organization for Standardizati" in out and "International Organization for Standardization," not in out


# ---------------- industries ----------------
def test_industries_sorted_by_count_then_name(home, monkeypatch, capsys):
    run(monkeypatch, "industries")
    assert capsys.readouterr().out.splitlines() == ["  2  it", "  1  Oil-Gas", "  1  oil-gas", "  1  telecom"]


# ---------------- collect ----------------
def test_collect_writes_csv_and_isolates_failures(home, monkeypatch, capsys, tmp_path):
    calls = []

    def ok(limit):
        calls.append(limit)
        return [dict(source="s", id="1", title="T", year="2020", status="x", url="u", access="free", industries="i")]

    def bad(limit):
        raise RuntimeError("nope")

    monkeypatch.setitem(sc.COLLECTORS, "rfc", ok)
    monkeypatch.setitem(sc.COLLECTORS, "ecfr", bad)
    out = tmp_path / "cat" / "nested"
    run(monkeypatch, "collect", "ecfr", "rfc", "--limit", "7", "--out", str(out))
    err = capsys.readouterr().err
    assert "collecting ecfr ..." in err and "FAILED ecfr: nope" in err and "1 rows ->" in err
    assert calls == [7] and not (out / "ecfr.csv").exists()
    rows = list(csv.DictReader((out / "rfc.csv").open()))
    assert rows[0]["id"] == "1" and rows[0]["adopts_intl"] == "" and list(rows[0]) == sc.FIELDS


def test_collect_defaults_to_all_collectors(home, monkeypatch, capsys, tmp_path):
    names = []
    for k in list(sc.COLLECTORS):
        monkeypatch.setitem(sc.COLLECTORS, k, (lambda n: lambda limit: (names.append(n), [])[1])(k))
    run(monkeypatch, "collect", "--out", str(tmp_path / "o"))
    assert names == list(sc.COLLECTORS)
    assert len(list((tmp_path / "o").glob("*.csv"))) == len(sc.COLLECTORS)


# ---------------- search ----------------
def _catalog(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, sc.FIELDS)
        w.writeheader()
        w.writerows(rows)


def test_search_matches_id_title_industries_case_insensitively(home, monkeypatch, capsys, tmp_path):
    base = dict(source="s", year="", status="", url="http://u", access="free", adopts_intl="")
    _catalog(tmp_path / "a.csv", [dict(base, id="ISO 9001", title="Quality", industries="mgmt"),
                                  dict(base, id="X", title="Boiler Code", industries="power"),
                                  dict(base, id="Y", title="Other", industries="Pressure;vessels")])
    _catalog(tmp_path / "b.csv", [dict(base, id="Z", title="t" * 100, industries="pressure")])
    run(monkeypatch, "search", "PRESSURE", "--out", str(tmp_path))
    cap = capsys.readouterr()
    assert cap.out.splitlines() == ["[s] Y  Other  http://u", "[s] Z  " + "t" * 80 + "  http://u"]
    assert cap.err.strip() == "2 hits"
    run(monkeypatch, "search", "9001", "--out", str(tmp_path))
    assert capsys.readouterr().out.splitlines() == ["[s] ISO 9001  Quality  http://u"]
    run(monkeypatch, "search", "nothing", "--out", str(tmp_path))
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err.strip() == "0 hits"


# ---------------- download ----------------
def test_download_only_free_matches_and_resolves_archive_pdf(home, monkeypatch, capsys, tmp_path):
    base = dict(source="s", year="", status="", industries="", adopts_intl="")
    cat = tmp_path / "cat.csv"
    _catalog(cat, [
        dict(base, id="IS 456", title="Concrete", url="https://archive.org/details/gov.in.is.456.2000", access="free"),
        dict(base, id="IS 457", title="Concrete paid", url="https://archive.org/details/gov.in.is.457", access="paid"),
        dict(base, id="RFC 1", title="Concrete memo", url="https://rfc/x/1.txt", access="free"),
        dict(base, id="IS 9", title="Steel", url="https://archive.org/details/gov.in.is.9", access="free"),
        dict(base, id="IS 458", title="CONCRETE 3", url="https://x/y z/3.pdf", access="free")])
    fetched = []

    def g(url, binary=False):
        fetched.append((url, binary))
        if "rfc" in url:
            raise OSError("down")
        return b"PDF"

    monkeypatch.setattr(sc, "get", g)
    dest = tmp_path / "dl"
    run(monkeypatch, "download", str(cat), "--match", "concrete", "--dest", str(dest), "--max", "5")
    cap = capsys.readouterr()
    assert [u for u, b in fetched] == ["https://archive.org/download/gov.in.is.456.2000/is.456.2000.pdf",
                                       "https://rfc/x/1.txt", "https://x/y z/3.pdf"]
    assert all(b for _, b in fetched)
    assert (dest / "IS_456_is.456.2000.pdf").read_bytes() == b"PDF"
    assert "fail https://rfc/x/1.txt down" in cap.err
    assert (dest / "IS_458_3.pdf").exists() and cap.out.count("saved") == 2


def test_download_respects_max(home, monkeypatch, capsys, tmp_path):
    base = dict(source="s", year="", status="", industries="", adopts_intl="", access="free", title="t")
    cat = tmp_path / "c.csv"
    _catalog(cat, [dict(base, id=f"A{i}", url=f"https://h/{i}.pdf") for i in range(5)])
    got = []
    monkeypatch.setattr(sc, "get", lambda url, binary=False: (got.append(url), b"x")[1])
    run(monkeypatch, "download", str(cat), "--match", "a", "--max", "2", "--dest", str(tmp_path / "d"))
    assert len(got) == 2


def test_download_defaults(home, monkeypatch, capsys, tmp_path):
    base = dict(source="s", year="", status="", industries="", adopts_intl="", access="free", title="t")
    cat = tmp_path / "c.csv"
    _catalog(cat, [dict(base, id=f"A{i}", url=f"https://h/{i}.pdf") for i in range(8)])
    got = []
    monkeypatch.setattr(sc, "get", lambda url, binary=False: (got.append(url), b"x")[1])
    monkeypatch.chdir(tmp_path)
    run(monkeypatch, "download", str(cat), "--match", "A")
    assert len(got) == 5 and (tmp_path / "downloads").is_dir()


def test_main_requires_subcommand(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["stdcollect.py"])
    with pytest.raises(SystemExit) as e:
        sc.main()
    assert e.value.code == 2


def test_collectors_registry_complete():
    assert set(sc.COLLECTORS) == {"ecfr_ibr", "lawresorg_world", "eu_harmonised", "china", "korea", "saudi", "japan",
                                  "itu", "nasa", "etsi", "rfc", "ecfr", "lawresorg_bis"}
    assert all(callable(f) for f in sc.COLLECTORS.values())
