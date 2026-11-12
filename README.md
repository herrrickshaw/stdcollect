# stdcollect

Collect engineering-standards metadata from public sources and list which standards bodies are free vs paid, by sector and by country.

    python3 stdcollect.py sectors --sector oil-gas
    python3 stdcollect.py countries --region asia
    python3 stdcollect.py bodies --access free
    python3 stdcollect.py collect itu nasa etsi rfc ecfr lawresorg_bis
    python3 stdcollect.py search "pressure"
    python3 stdcollect.py download catalog/lawresorg_bis.csv --match IS.456 --max 1

Collectors: ITU-T, ETSI (/deliver tree), NASA NTSS, IETF RFCs, US eCFR titles, Indian Standards (Public.Resource.Org), China GB (view-only), Korea KS (view-only), SASO consultation drafts. Japan (JISC) is blocked by a site outage; ASSIST blocks automated clients. Paid standards are listed, never scraped.

Registry data (`registry.json`, `countries.json`, `sectors.json`) is best-knowledge; confirm access/pricing on each body's site.
