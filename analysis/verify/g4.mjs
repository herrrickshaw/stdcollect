import { parseCsv, fail } from "./lib.mjs";
const { rows } = parseCsv("analysis/sector_chains.csv");
const good = rows.filter(r => Number(r.n_intl_standards) >= 1 && r.most_recurring_intl_standards);
const sectors = new Set(good.map(r => r.sector));
if (sectors.size < 10) fail("sectors " + sectors.size);
console.log(`G4 verified (${sectors.size} sectors)`);
