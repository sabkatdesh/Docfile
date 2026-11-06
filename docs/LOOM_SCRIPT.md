# Loom script (target 4:30, hard limit 5:00)

Audience: a non-technical hiring manager. Say "the AI" for the language model, "the rules" for the code. Never read code aloud.

## Before you record

Run these once, in this order, from the repo root. Fix anything that is not green before you press record.

```bash
git status                       # clean
python tasks.py check            # all green, about 2 minutes
python tasks.py eval             # 10/10, unsafe errors: 0
```

Start from an empty database, then start the app:

```bash
# Windows PowerShell:  Remove-Item -Recurse -Force runs
rm -rf runs
python tasks.py serve --step-delay 0.4
```

Open <http://127.0.0.1:8000> in a clean browser window (zoom 110%, light theme, bookmarks bar hidden, notifications off). Keep a second terminal open at the repo root. Have `data/sample/supplier-pack-03.pdf` and `docs/NOTE.md` ready in tabs. `--step-delay` slows the progress so viewers can see the steps; drop it if it feels slow.

## Timeline

| Time | Say | Screen / click |
|---|---|---|
| 0:00 to 0:30 **Problem** | "A garment company gets quotes from suppliers. Someone has to check each one against what was ordered and against company rules: price, quantity, payment terms, tax numbers, delivery. It is slow, and a wrong yes costs real money. I built a checker that answers Approve, Reject or Needs a person, shows the exact words it relied on, and never guesses." | Show **Dashboard** with the empty table. Point at the three verdict words in the page. |
| 0:30 to 1:30 **One clean pack** | "Ten sample quotes. I press Run all checks. Each one goes through the same fixed steps: read the PDF, two independent readers extract the facts, every quote is checked against the document, then plain rules decide." Open pack 01: "Approve, because all 12 checks pass. On the left is the quote text, with the evidence highlighted. On the right, what we asked for against what they quoted, and the 12 rules." | Click **Run all checks**. Watch progress. Click **supplier-pack-01** in the table. Click a field in the extracted list so the highlight scrolls. Point at the rule checklist and the verdict card. |
| 1:30 to 3:00 **Pack 09 and the pause** | "Pack 09 looks fine at a glance. The AI read the total as 322,000, but 50,000 pieces at 6.40 is 320,000. And payment says 30 to 90 days; the rule allows 30 to 60. The system does not guess which is right. It stops and asks me." Go to Review queue: "I give a decision and a reason, and it is saved next to the machine's answer, not over it." Then Evaluation: "The score only uses the machine's answer, so my decision cannot hide a mistake." | Click **Dashboard**, open **supplier-pack-09**, click the "Subtotal 322,000.00" highlight, point at the failed rules. Click **Review queue**, pick pack 09, choose **Reject**, type "Total does not match the unit price; ask supplier for a corrected quote.", click **Save decision**. Click **Evaluation**. |
| 3:00 to 3:45 **Score and safety** | "10 out of 10 match my answer key: 2 approve, 5 reject, 3 need a person. The number I care about is unsafe errors, a wrong Approve, and that is zero. Ten samples is a sanity check, so I also built 39 mutation tests: take a passing pack, change one thing, and the verdict must change. And 811 automatic tests, including one for every rule at its exact edge." | **Evaluation**: point at the accuracy KPI, the unsafe errors card, the confusion matrix, the mutation results. |
| 3:45 to 4:30 **AI, limits, next** | "I used Claude Code to build this, and it wrote most of the code. I wrote the spec and the answer key first, approved a plan for each stage, made the design calls, and ran the checks myself. The main design call: the AI reads, the code judges. What does not work well: the second reader only fits this quote layout, there is no scanned-PDF support, ten samples is small, and the demo replays recorded answers. Next: more documents, a second model as the cross-check, and real logins." | Show `docs/NOTE.md` for 5 seconds, then the dashboard. End on the dashboard with your face or the title visible. |

## If something fails on camera

- **App will not load or crashes:** stop, say "let me show the same thing in the terminal", and run `python tasks.py demo`, then `python tasks.py review list --db runs/demo.sqlite` and `python tasks.py eval`. The demo output already shows each verdict with its quote. Narrate the same story from the printed reasons.
- **Run seems stuck:** reload the page; the run log replays. Otherwise restart `serve` after deleting `runs/`.
- **409 "pending reviews" dialog appears:** that is the safety feature. Say so, click **Discard and run**.
- **Port busy:** `python tasks.py serve --port 8001`.
- **Worst case:** record the terminal only (demo, eval, check). A calm, honest take beats a polished one.

## Likely questions on the shortlist call

1. **How do you know it never approves something wrong?** Approve needs all 12 rules to pass, and unknown never counts as a pass. A test runs 5,000 seeded combinations to check that. Any extraction doubt becomes Needs a person. The honest limit: I proved this on these templates, not on every possible document.
2. **Why not let the LLM decide?** It can be fluent and wrong, and I cannot test its judgment at the exact edge of a rule (3.00% against 3.01%). Code can be tested and audited. The model is used only where code is weak, which is reading messy text.
3. **What breaks on a new document layout?** The regex reader is template-specific, so fields stop agreeing and go to a person. It fails safe but loses automation. Fix: swap the second reader for a different model (the provider is a config value).
4. **Why a real database pause and not just a flag?** The review must survive a restart and record who decided and why. LangGraph's interrupt plus SQLite does that, and the machine verdict is never overwritten.
5. **What did the AI do and what did you do?** Claude Code wrote most of the code. I set the design, the answer key and the rules of the road, approved plans, made the calls on precedence and safety defaults, and ran the checks. (Be ready to open a rule and explain it in your own words.)

### "Change one thing live"

Two small, safe changes. Do either one with the test green before and after.

1. **Tighten a threshold.** In `src/docgate/domain/config.py`, change `price_tolerance_pct` from `Decimal("3")` to `Decimal("2")`. Run `python tasks.py eval`: pack 04 (+2.31%) now flips from Needs a person to Reject, which shows up as a conservative-looking mismatch against the golden set, and the boundary tests for the 3% rule fail, which proves the tests guard the value. Say so, then revert with `git checkout src/docgate/domain/config.py`. (Do not edit the golden file.)
2. **Change a reason's wording.** In `src/docgate/reporting/explain.py`, change the phrase "A person must check" to something else, run `python tasks.py demo`, and show the new text. Run the explain tests to see which one pins the wording, update that test's expected string, and note that the verdict and rules are untouched. Revert with `git checkout`.

Rehearse both once before the call. Neither touches any rule logic or golden expectations.
