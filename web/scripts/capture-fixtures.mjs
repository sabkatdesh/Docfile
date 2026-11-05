// Captures real API responses as test fixtures. Start a server first, in replay mode:
//   python tasks.py serve --db runs/fixtures.sqlite --out runs/fixtures
// then: npm run fixtures:capture   (set API=http://127.0.0.1:PORT to use another address)
//
// It starts runs on that server, including one with discard_pending, so point it at a throwaway
// database, never at a record you want to keep.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const API = process.env.API ?? "http://127.0.0.1:8000";
const OUT = join("src", "test", "fixtures");
mkdirSync(OUT, { recursive: true });

async function call(path, init) {
  const res = await fetch(API + path, {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
  return { status: res.status, text: await res.text() };
}
const save = (name, text) =>
  writeFileSync(join(OUT, name), text.endsWith("\n") ? text : `${text}\n`);
const saveJson = (name, text) => save(name, JSON.stringify(JSON.parse(text), null, 2));
const post = (path, body) => call(path, { method: "POST", body: JSON.stringify(body) });

async function waitIdle() {
  for (let i = 0; i < 120; i++) {
    const health = JSON.parse((await call("/api/health")).text);
    if (!health.active_run_id) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("run did not finish");
}

await waitIdle();
// A first run, so there is something on record; then the two refusals it causes.
let accepted = await post("/api/runs", { packs: null, discard_pending: true });
if (accepted.status !== 202) throw new Error(`could not start a run: ${accepted.text}`);
await waitIdle();

const conflict = await post("/api/runs", { packs: null });
if (conflict.status !== 409) throw new Error("expected pending_reviews_would_be_lost");
saveJson("error-pending-reviews.json", conflict.text);

// The recorded run that the reducer test replays.
accepted = await post("/api/runs", { packs: null, discard_pending: true });
const run = JSON.parse(accepted.text);
const stream = await call(run.events_url);
save("run-events.txt", stream.text);
await waitIdle();

saveJson("packs-after-run.json", (await call("/api/packs")).text);
for (const n of ["01", "03", "04", "07", "09"]) {
  saveJson(`pack-${n}.json`, (await call(`/api/packs/supplier-pack-${n}`)).text);
}
saveJson("review.json", (await call("/api/review")).text);
saveJson("eval.json", (await call("/api/eval")).text);
saveJson("health.json", (await call("/api/health")).text);

const blank = await post("/api/review/supplier-pack-04", { decision: "Approve", reason: "   " });
saveJson("error-blank-reason.json", blank.text);
const final = await post("/api/review/supplier-pack-01", { decision: "Approve", reason: "x" });
saveJson("error-machine-final.json", final.text);

console.log(`fixtures written to ${OUT}`);
