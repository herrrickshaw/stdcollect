# How engineering standards are linked across segments and countries

Data: `analysis/links.csv` (every catalog entry that names an ISO/IEC standard), `analysis/clusters.csv` (one row per international standard with the countries carrying it), `linking_bodies.json` (bodies and agreements that create the links). Rebuild with `python3 analysis/link_standards.py`.

## 1. Which standards are similar (measured)
Method: extract the ISO/IEC number from each national id (`IS/ISO 13485`, `KS P ISO13485`, `EN ISO 13485:2016`, `EN 60034-1` = IEC) and group.

- 19,041 catalog entries name an international standard; 17,183 distinct ISO/IEC standards are involved.
- 1,034 appear in at least two countries/blocs; 45 in three or more.
- Strongest pairs: India–South Korea 418, EU–South Korea 403, Ethiopia–South Korea 84, China–South Korea 10, EU–India 10.
- Examples in 3 bodies at once: ISO 13485 (medical QMS), ISO 15223-1 (device symbols), ISO 22000 (food safety), ISO 3449 (earth-moving FOPS), ISO 2867, ISO 11145 (lasers). Electrical: IEC 60034 (motors), 60044, 60060 appear as IS/IEC and KS C IEC.
- These are the same text under different national numbers: the ISO/IEC number is the join key.

Caveats (the numbers undercount): Korea's catalog is complete (34k) but India's is only the Public.Resource.Org subset, EU harmonised covers 10 of ~40 legislations, Saudi is drafts only, and China's records do not carry the ISO number (its "adopted from international standard" flag was not captured), so China is under-linked. Matching is by number, not by degree of equivalence: an `IS/ISO` or `KS ... ISO` entry may be identical or modified; only the standard's own national foreword says which.

## 2. How countries are linked
| Mechanism | Body / agreement | Effect |
|---|---|---|
| Adopt the international text | ISO, IEC, national bodies | Same text, national number prefix (`IS/ISO`, `KS P ISO`, `EN ISO`, `BS EN ISO`) |
| Say how close the adoption is | ISO/IEC Guide 21-1: identical / modified / not equivalent | Lets a user know if the national copy deviates |
| Parallel development | Vienna Agreement (ISO-CEN, ~31% of CEN standards); Frankfurt Agreement (IEC-CENELEC, ~72-80% identical or based on IEC) | One text is both international and European |
| Legal driver | WTO TBT Annex 3 Code of Good Practice | Bodies must base national standards on international ones where they exist |
| National variants of one text | Eurocodes + National Annexes | Same EN, country-specific parameters |
| Regional blocs | ARSO, GSO, EAC, COMESA, COPANT, PASC, ACCSQ, EASC | Harmonise inside a bloc |
| Mutual recognition | IAF MLA, ILAC MRA, BIPM CIPM MRA | A test or certificate to the same standard is accepted abroad |

## 3. How standards are linked across segments (sectors)
- **Foundational layer** (ISO 9001 quality, ISO 14001, ISO 31000 risk, ISO 17025 labs, ISO/IEC 27001) is referenced by almost every sector standard, so it is the common link between sectors.
- **Subject classification**: ICS (ISO) groups by subject across bodies; HS codes (WCO) link traded products to the standards that apply.
- **Law-to-standard**: EU harmonised standards (EN cited in the OJEU, presumption of conformity under directives such as machinery, pressure equipment, ATEX, low voltage) and US incorporation by reference tie private standards to products and industries.
- **Sector chains**: for example process plant: API/ISO 13709 (pumps) -> ASME B31.3 piping -> ISO/EN pressure-equipment standards -> IEC 61511 / ISA-84 safety instrumented systems -> IEC 61508 base. Each sector has an international root and per-country shells.
- Only the harmonised-standard and national-prefix links are measured here; the sector chains above are from general knowledge and not yet computed.

## 4. Provenance
Verified by web search on 2026-11-13: Guide 21-1 scope, Vienna and Frankfurt Agreements and their percentages (sources differ by year), TBT Annex 3, Eurocode National Annexes. Not verified in this session (general knowledge): IAF/ILAC/BIPM, ITC Standards Map, ICS/HS roles, regional bodies, ANSI IBR, harmonised-standards presumption. `linking_bodies.json` has a `provenance` field per entry.

## 4b. Update 2026-11-13 (pending items closed)
- **China adoption flag**: the collector now records `adopts_intl` (the portal's 采 mark = adopted from an international standard) for every GB record (re-collection result committed separately).
- **Incorporated by reference (US)**: `catalog/ecfr_ibr.csv`, 890 standards named in 8 CFR sections (OSHA 1910.6/1926.6, DOT 49 CFR 171.7/192.7/195.3, EPA 40 CFR 60.17/63.14, USCG 33 CFR 127, NRC 50.55a). `analysis/ibr_sector_bodies.csv` shows which private bodies each regulation leans on (ANSI, NFPA, ASTM, SAE, CGA, API...).
- **Sector chains**: `analysis/sector_chains.csv` (126 sector rows from the Korea KS classes, EU legislations and BIS committees) and `analysis/sector_bridges.csv` (1,015 international standards that recur in 2+ sectors). Foundational standards bridge sectors: ISO 9001 recurs across KS management, IT, distribution and BIS management; ISO 13485 and ISO 15223-1 bridge EU medical-device, IVD, BIS medical and KS medical.
- **Degree of equivalence (India)**: `analysis/degree.csv`, 576 IS/ISO and IS/IEC entries read from their forewords: 415 identical, 25 modified, 136 unknown (125 because the text is withdrawn on archive.org).
- **Clauses and specifications**: `analysis/clauses.csv` (19,270 clauses with headings from 451 standards) and `analysis/specs.csv` (2,647 quantitative requirement snippets with value and unit). Covers only the free full texts we hold (Indian adoptions of ISO/IEC); 125 texts are unavailable. Paid and view-only standards (ISO, ASTM, GB, KS, EN) cannot be listed clause by clause.
- **EU harmonised**: 3,223 entries across 17 legislations. 19 of the 41 Commission pages publish no spreadsheet (standards live only in OJ decisions on EUR-Lex, not crawled), so 17 is the ceiling with this method; gate G2 (25) is recorded as abandoned.
- **Japan JISC**: still down (HTTP 502 service-stop); gate G6 abandoned with a handoff.
- **Countries**: `countries.json` now has `http_status` for each of 108 bodies' sites: 72 returned 200, 26 failed to connect from a script, 8 returned 403, 2 other. Access labels (free/paid) remain unverified.

## 5. Next steps
Parse EUR-Lex implementing decisions for the 19 EU legislations without spreadsheets; read forewords for Korea and the EU to get their degree (IDT/MOD); build the JIS collector when JISC returns; extend clause extraction to RFCs, NASA and ITU texts.
