import { parseCsv, fail } from "./lib.mjs";
const bis = parseCsv("catalog/lawresorg_bis.csv").rows.filter(r => /^IS\/(ISO|IEC)/.test(r.id));
const deg = parseCsv("analysis/degree.csv").rows;
if (deg.length !== bis.length) fail(`degree rows ${deg.length} != IS/ISO+IEC rows ${bis.length}`);
const unk = deg.filter(r => r.degree === "unknown").length / deg.length;
if (deg.some(r => !["identical", "modified", "unknown"].includes(r.degree))) fail("bad degree value");
if (unk > 0.4) fail(`unknown share ${(unk * 100).toFixed(1)}%`);
console.log(`G5 verified (${deg.length} rows, unknown ${(unk * 100).toFixed(1)}%)`);
