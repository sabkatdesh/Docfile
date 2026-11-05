import { type ChildProcess, spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const PORT = 8765;
export const E2E_API = `http://127.0.0.1:${PORT}`;

let server: ChildProcess | undefined;
let scratch: string | undefined;

async function waitForHealth(deadline: number): Promise<void> {
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${E2E_API}/api/health`);
      if (res.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error("the API did not become healthy in time");
}

/** Starts the real FastAPI app in replay mode on a throwaway database, so the smoke test cannot
 * disturb the developer's own run history and needs no API key. */
export async function setup(): Promise<void> {
  const root = resolve(process.cwd(), "..");
  const python =
    process.platform === "win32"
      ? join(root, ".venv", "Scripts", "python.exe")
      : join(root, ".venv", "bin", "python");
  scratch = mkdtempSync(join(tmpdir(), "docgate-e2e-"));
  server = spawn(
    python,
    [
      "-m",
      "docgate.cli",
      "serve",
      "--port",
      String(PORT),
      "--db",
      join(scratch, "e2e.sqlite"),
      "--out",
      join(scratch, "out"),
    ],
    { cwd: root, stdio: "ignore" },
  );
  server.on("error", (error) => {
    throw error;
  });
  await waitForHealth(Date.now() + 30_000);
  process.env.DOCGATE_E2E_API = E2E_API;
}

export async function teardown(): Promise<void> {
  server?.kill();
  // Windows can hold the sqlite file for a moment after the process dies; cleanup is best-effort.
  await new Promise((r) => setTimeout(r, 500));
  if (scratch) {
    try {
      rmSync(scratch, { recursive: true, force: true });
    } catch {
      // the OS temp folder is cleaned eventually
    }
  }
}
