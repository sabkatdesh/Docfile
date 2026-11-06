# Supplier Document Checker: one-page note

Sabkat Shoheb Desh. BIAI Round 2, Task 1.

## What I built
A system that reads 10 supplier quotation PDFs, compares each with the purchase request and the company rules, and answers **Approve**, **Reject** or **Needs a person to check**, with the exact quoted evidence. It runs as fixed LangGraph steps, not a free agent. The rule is: the AI reads, code judges. A language model only pulls out fields, each with a word-for-word quote. Plain Python does every comparison and makes every decision. A second, rule-based reader checks the model, and a value is used only if its quote is in the PDF and both readers agree. Anything missing, unclear or in conflict stops the pack for a person. There is a web app and a command line.

## How I tested it
- 811 Python tests, plus `ruff` and strict `mypy`, all green. Every rule is tested at its exact boundary (3.00% against 3.01%, 30 against 31 days).
- A golden test on the 10 packs that fails the build on any mismatch.
- A mutation suite of 39 cases: change one value in a passing pack (price +3.1%, advance 21%, TIN removed, delivery 46 days) and the answer must change. Failure tests cover empty and garbage PDFs, timeouts and malformed model output.
- 145 front-end tests, including one end-to-end walk through the review flow.
- A fresh-clone check: new folder, full install, demo with no API key and the network blocked.

## Results
10 of 10 packs correct: 2 Approve, 5 Reject, 3 Needs a person. **0 unsafe errors** (no wrong Approve). Packs 04, 07 and 09 pause for a person; the decision and reason are saved beside the machine's answer. Pack 09 is the hard one: the total does not add up (50,000 x 6.40 is 320,000, quoted 322,000) and payment is "30 to 90 days". Both are caught and shown with quotes.

## What does not work well
- The second reader fits this one quotation layout. On another layout most fields would go to a person: safe, but not useful.
- Text PDFs only. Scans fail with a clear error; there is no OCR.
- Ten samples is a sanity check, not proof of generalising. The mutation tests help, but they edit these same documents.
- The demo replays recorded answers from one model and one prompt version. The recordings were made live with Groq, whose free tier is slow and rate limited.
- One run at a time, one database, no login. A reviewer can only Approve or Reject.
- `sqlite-vec` comes in with LangGraph's checkpointer. It is pinned, but I did not verify its binary against upstream.
- Claude Code wrote most of the code under my spec, plan approvals and review.

## What I would do next
1. Re-run live regularly and add more documents, including scans.
2. Replace the template-specific reader with a second, different model.
3. Add "request more information", logins and several users.
4. Test the app in a real browser suite.
