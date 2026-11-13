# Gates: stdcollect pending tasks

OWNS: stdcollect.py, catalog/**, analysis/**, countries.json, registry.json, RESEARCH_LINKAGE.md, README.md, .gitignore

Scope: close every pending item from the linkage research: China adoption flag, wider EU coverage, eCFR incorporated-by-reference links, computed sector chains, degree of equivalence, Japan JISC, country URL checks, report refresh, and a clean pushed repo.

- [ ] G1: china.csv carries an adopts_intl column for every one of >=70000 rows, with both yes and no values
  CHECK: node analysis/verify/g1.mjs
  EXPECT: G1 verified
  EVIDENCE: pending

- [ ] G2: eu_harmonised.csv covers at least 25 distinct legislations
  CHECK: node analysis/verify/g2.mjs
  EXPECT: G2 verified
  EVIDENCE: pending

- [ ] G3: catalog/ecfr_ibr.csv lists at least 500 incorporated-by-reference standards from at least 3 CFR sections, each tagged with its publisher body
  CHECK: node analysis/verify/g3.mjs
  EXPECT: G3 verified
  EVIDENCE: pending

- [ ] G4: analysis/sector_chains.csv maps at least 10 sectors to the international standards that recur in them
  CHECK: node analysis/verify/g4.mjs
  EXPECT: G4 verified
  EVIDENCE: pending

- [ ] G5: analysis/degree.csv classifies every IS/ISO and IS/IEC entry in the BIS catalog (identical, modified or unknown) with at most 40 percent unknown
  CHECK: node analysis/verify/g5.mjs
  EXPECT: G5 verified
  EVIDENCE: pending

- [ ] G6: JISC either yields catalog/japan_jis.csv with >=1000 rows or the outage is documented as an abandoned handoff
  CHECK: node analysis/verify/g6.mjs
  EXPECT: G6 verified
  EVIDENCE: pending

- [ ] G7: every country in countries.json has a checked http_status for its url
  CHECK: node analysis/verify/g7.mjs
  EXPECT: G7 verified
  EVIDENCE: pending

- [ ] G8: RESEARCH_LINKAGE.md states the link counts currently produced by analysis/link_standards.py
  CHECK: node analysis/verify/g8.mjs
  EXPECT: G8 verified
  EVIDENCE: pending

- [ ] G9: git working tree has no uncommitted tracked changes and HEAD equals origin/main
  CHECK: node analysis/verify/g9.mjs
  EXPECT: G9 verified
  EVIDENCE: pending

- [ ] G10: analysis/clauses.csv and specs.csv cover every IS/ISO and IS/IEC entry (clauses extracted where the text is available, otherwise marked text unavailable)
  CHECK: node analysis/verify/g10.mjs
  EXPECT: G10 verified
  EVIDENCE: pending

ABANDON: G2 measured ceiling is 17 legislations, not 25: 19 of the 41 Commission pages publish no spreadsheet (their standards sit only inside OJ implementing decisions on EUR-Lex, which answers scripts with HTTP 202 and was not crawled); handoff: write an EUR-Lex decision parser if more coverage is wanted
ABANDON: G6 JISC (jisc.go.jp) returned HTTP 502 with a service-stop notice and no restart date on 2026-11-13 and again on retry; handoff: re-run `python3 stdcollect.py collect japan` when the site returns and build the JIS search collector then
