# stdcollect

Collect engineering-standards metadata from public sources and list which standards bodies are free vs paid, by sector and by country.

    python3 stdcollect.py sectors --sector oil-gas
    python3 stdcollect.py countries --region asia
    python3 stdcollect.py bodies --access free
    python3 stdcollect.py collect itu nasa etsi rfc ecfr lawresorg_bis
    python3 stdcollect.py search "pressure"
    python3 stdcollect.py download catalog/lawresorg_bis.csv --match IS.456 --max 1

Collectors: ITU-T, ETSI, NASA NTSS, IETF RFCs, US eCFR, Indian Standards (BIS), Public.Resource.Org world (AU/JP/NZ/ZA/KE/PH/TH/UG/ET/EC/GCC/ARSO/COMESA), EU harmonised standards, China GB (view-only), Korea KS (view-only), SASO drafts. Japan JISC (outage), UNECE, CEN search and ASSIST block automated clients. Paid standards are listed, never scraped.

Registry data (`registry.json`, `countries.json`, `sectors.json`) is best-knowledge; confirm access/pricing on each body's site.
