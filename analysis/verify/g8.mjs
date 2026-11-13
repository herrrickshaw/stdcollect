import fs from "node:fs";
import { execSync } from "node:child_process";
import { fail } from "./lib.mjs";
const out = execSync("python3 analysis/link_standards.py", { encoding: "utf8" });
const m = out.match(/(\d+) links; (\d+) intl standards; (\d+) in >=2 countries\/blocs; (\d+) >=3/);
if (!m) fail("cannot parse link_standards output: " + out);
const doc = fs.readFileSync("RESEARCH_LINKAGE.md", "utf8");
for (const n of m.slice(1)) if (!doc.includes(Number(n).toLocaleString("en-US"))) fail(`doc missing ${Number(n).toLocaleString("en-US")}`);
console.log("G8 verified");
