import { parseCsv, fail } from "./lib.mjs";
const { head, rows } = parseCsv("catalog/china.csv");
if (!head.includes("adopts_intl")) fail("no adopts_intl column");
const yes = rows.filter(r => r.adopts_intl === "yes").length, no = rows.filter(r => r.adopts_intl === "no").length;
if (rows.length < 70000) fail("rows " + rows.length);
if (yes + no !== rows.length) fail("rows without flag: " + (rows.length - yes - no));
if (!yes || !no) fail("flag has a single value");
console.log(`G1 verified (${rows.length} rows, ${yes} adopt international)`);
