# How engineering standards are linked across segments and countries

Data: `analysis/links.csv` (every catalog entry that names an ISO/IEC standard), `analysis/clusters.csv` (one row per international standard with the countries carrying it), `linking_bodies.json` (bodies and agreements that create the links). Rebuild with `python3 analysis/link_standards.py`.

## 1. Which standards are similar (measured)
Method: extract the ISO/IEC number from each national id (`IS/ISO 13485`, `KS P ISO13485`, `EN ISO 13485:2016`, `EN 60034-1` = IEC) and group.

- 18,798 catalog entries name an international standard; 17,131 distinct ISO/IEC standards are involved.
- 920 appear in at least two countries/blocs; 13 in three or more.
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

## 5. Next steps
Capture China's adoption flag (采) and degree (IDT/MOD/NEQ) for ~all GB/T entries; parse each national standard's foreword for its stated degree; extend EU harmonised coverage past 10 legislations; add ASTM/ASME/API links from the eCFR incorporated-by-reference lists; build the sector chains from `clusters.csv`.
