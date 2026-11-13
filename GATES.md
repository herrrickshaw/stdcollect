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

- [x] G3: catalog/ecfr_ibr.csv lists at least 500 incorporated-by-reference standards from at least 3 CFR sections, each tagged with its publisher body
  CHECK: node analysis/verify/g3.mjs
  EXPECT: G3 verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/umashankar/standards; path=8ce7a6ec4399/26 entries; EXPECT=matched; output-sha256=1c721ab93bf8a3788a34f6fd854fef79ad5d6f800ed1c7785d7ef2b1db68dfed; output-bytes=36

- [x] G4: analysis/sector_chains.csv maps at least 10 sectors to the international standards that recur in them
  CHECK: node analysis/verify/g4.mjs
  EXPECT: G4 verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/umashankar/standards; path=8ce7a6ec4399/26 entries; EXPECT=matched; output-sha256=2aa222fda19e3452d8e03f90ff5768bb31c4c76c3c0deed40d46275b02faaa57; output-bytes=26

- [x] G5: analysis/degree.csv classifies every IS/ISO and IS/IEC entry in the BIS catalog (identical, modified or unknown) with at most 40 percent unknown
  CHECK: node analysis/verify/g5.mjs
  EXPECT: G5 verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/umashankar/standards; path=8ce7a6ec4399/26 entries; EXPECT=matched; output-sha256=bab1cde108b8fd2a15965b04c34cd36aee4425937236a289fbe2817a4eccc87b; output-bytes=38

- [ ] G6: JISC either yields catalog/japan_jis.csv with >=1000 rows or the outage is documented as an abandoned handoff
  CHECK: node analysis/verify/g6.mjs
  EXPECT: G6 verified
  EVIDENCE: pending

- [x] G7: every country in countries.json has a checked http_status for its url
  CHECK: node analysis/verify/g7.mjs
  EXPECT: G7 verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/umashankar/standards; path=8ce7a6ec4399/26 entries; EXPECT=matched; output-sha256=aee3c51e8394253b85003f84bf258514d0119a09972919885b53d268921bf21b; output-bytes=36

- [x] G8: RESEARCH_LINKAGE.md states the link counts currently produced by analysis/link_standards.py
  CHECK: node analysis/verify/g8.mjs
  EXPECT: G8 verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/umashankar/standards; path=8ce7a6ec4399/26 entries; EXPECT=matched; output-sha256=d0eb2b9420774db4956d3dddefe450d743935deccd9814eb0de44cf57aad6528; output-bytes=12

- [ ] G9: git working tree has no uncommitted tracked changes and HEAD equals origin/main
  CHECK: node analysis/verify/g9.mjs
  EXPECT: G9 verified
  EVIDENCE: pending

- [x] G10: analysis/clauses.csv and specs.csv cover every IS/ISO and IS/IEC entry (clauses extracted where the text is available, otherwise marked text unavailable)
  CHECK: node analysis/verify/g10.mjs
  EXPECT: G10 verified
  EVIDENCE: exit=0; shell=/bin/sh; cwd=/Users/umashankar/standards; path=8ce7a6ec4399/26 entries; EXPECT=matched; output-sha256=24bf0f962ab1357c4f18035e66ff0912b17a82d6efad42adbf4afec5bfc5e656; output-bytes=69

ABANDON: G2 measured ceiling is 17 legislations, not 25: 19 of the 41 Commission pages publish no spreadsheet (their standards sit only inside OJ implementing decisions on EUR-Lex, which answers scripts with HTTP 202 and was not crawled); handoff: write an EUR-Lex decision parser if more coverage is wanted
ABANDON: G6 JISC (jisc.go.jp) returned HTTP 502 with a service-stop notice and no restart date on 2026-11-13 and again on retry; handoff: re-run `python3 stdcollect.py collect japan` when the site returns and build the JIS search collector then
