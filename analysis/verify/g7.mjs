import fs from "node:fs";
import { fail } from "./lib.mjs";
const c = JSON.parse(fs.readFileSync("countries.json", "utf8"));
const bad = c.filter(x => x.http_status === undefined || x.http_status === null || !x.checked);
if (bad.length) fail(bad.length + " countries unchecked: " + bad.slice(0, 5).map(x => x.code).join(","));
console.log(`G7 verified (${c.length} countries checked)`);
