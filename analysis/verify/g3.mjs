import { parseCsv, fail } from "./lib.mjs";
const { rows } = parseCsv("catalog/ecfr_ibr.csv");
const secs = new Set(rows.map(r => r.industries.split(";").pop()));
const untagged = rows.filter(r => !r.industries.split(";").includes(r.id.split(" ")[0].toLowerCase()));
if (rows.length < 500) fail("rows " + rows.length);
if (secs.size < 3) fail("sections " + secs.size);
if (untagged.length) fail(untagged.length + " rows without publisher tag");
console.log(`G3 verified (${rows.length} refs, ${secs.size} sections)`);
