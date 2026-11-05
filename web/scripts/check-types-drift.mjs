// Fails when src/api/schema.d.ts is not what openapi-typescript would generate from
// ../docs/openapi.json, i.e. the API contract changed and the types were not regenerated.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const bin = join("node_modules", "openapi-typescript", "bin", "cli.js");
const dir = mkdtempSync(join(tmpdir(), "docgate-types-"));
const fresh = join(dir, "schema.d.ts");
try {
  execFileSync(process.execPath, [bin, "../docs/openapi.json", "-o", fresh], { stdio: "ignore" });
  const same = readFileSync(fresh, "utf-8") === readFileSync("src/api/schema.d.ts", "utf-8");
  if (!same) {
    console.error("src/api/schema.d.ts is out of date. Run: npm run gen:types");
    process.exitCode = 1;
  } else {
    console.log("API types are up to date with docs/openapi.json");
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
}
