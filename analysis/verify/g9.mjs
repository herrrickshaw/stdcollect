import { execSync } from "node:child_process";
import { fail } from "./lib.mjs";
const sh = c => execSync(c, { encoding: "utf8" }).trim();
const dirty = sh("git status --porcelain --untracked-files=no");
if (dirty) fail("uncommitted tracked changes:\n" + dirty);
const head = sh("git rev-parse HEAD"), origin = sh("git rev-parse origin/main");
if (head !== origin) fail(`HEAD ${head.slice(0, 7)} != origin/main ${origin.slice(0, 7)}`);
console.log("G9 verified");
