import fs from "node:fs";
import { parseCsv, fail } from "./lib.mjs";
if (!fs.existsSync("catalog/japan_jis.csv")) fail("catalog/japan_jis.csv missing (JISC outage)");
const n = parseCsv("catalog/japan_jis.csv").rows.length;
if (n < 1000) fail("rows " + n);
console.log(`G6 verified (${n} rows)`);
