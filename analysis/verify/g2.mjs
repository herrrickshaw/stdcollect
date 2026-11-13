import { parseCsv, fail } from "./lib.mjs";
const { rows } = parseCsv("catalog/eu_harmonised.csv");
const n = new Set(rows.map(r => r.industries.split(";")[1])).size;
if (n < 25) fail(`only ${n} legislations`);
console.log(`G2 verified (${n} legislations)`);
