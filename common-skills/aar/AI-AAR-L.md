Yep — that’s the right instinct: **AI-AAR-L shouldn’t be “more sections,” it should be “more depth where it matters,” plus 0–3 extra sections that force rigor.** Think *incident/postmortem energy* without importing all the ceremony.

Below is a concise **AI-AAR-L Handbook** built as **AI-AAR-M + depth guidance**, with **three optional add-ons** you can include when relevant.

---

# AI After Action Report: Large Edition (AI-AAR-L)

AI-AAR-L is for **high-stakes, high-cost, high-complexity, or repeat-failure** work. Its purpose is to produce:

1. a reliable handoff, 2) a defensible record, and 3) **closed-loop improvements**.
   Timebox: **30–90 minutes**. Target length: **1–3 pages**. If it’s longer, you’re writing a spec, not an AAR.

## 1) Goal & Success Criteria

Same as M, but make it audit-grade.

* Include **priority order** of success criteria (P0/P1/P2).
* Define **quality gates** (what must be verified vs “best effort”).
* State “what would have made us stop early.”

## 2) Scope & Constraints

Same items as M, but separate *hard* from *soft* constraints.

* Hard: non-negotiables, policy, deadlines, access limits
* Soft: preferences, “nice-to-haves,” suggested tools
* Add **known unknowns** explicitly (things you knew you didn’t know).

## 3) What Happened (Actual Outcome)

Same as M, but include a compact timeline + deltas.

* Status + artifact links
* **Timeline** (5–10 bullets): key events/turning points
* Deltas: “expected vs actual” in 3–6 bullets

## 4) Key Discoveries (Field Notes)

Same as M, but raise the bar: classify and attach evidence.
For each discovery (as a bullet list):

* **Claim:** what we learned
* **Confidence:** Confirmed / Likely / Suspected
* **Evidence:** link/log/test/run/trace (or note “no evidence”)
* **Impact:** why it matters for future jobs

## 5) Decisions & Rationale

Same as M, but add the “decision ledger” format.
For each major decision:

* Decision + alternatives
* Tradeoffs (cost, time, risk)
* **Reversibility:** reversible / expensive / irreversible
* **Trigger to revisit:** what new info would change it?

## 6) What Worked (Keep)

Same as M, but make it reusable.

* Convert “worked” into **repeatable patterns**:

  * “When X, do Y because Z.”
* Pull out **assets** (prompt snippets, test harnesses, checklists) into a stable place and link them.

## 7) What Didn’t Work (Change)

Same as M, but go one step deeper than symptoms.
For each failure mode:

* Symptom (what happened)
* **Root cause hypothesis** (best current explanation)
* Contributing factors (tooling, prompt, process, human)
* **Prevent/Detect**: how to prevent it, how to detect it early next time

## 8) Prompt / Tool / Process Deltas

Same as M, but show diffs and rationale.

* Prompt: “before -> after” (small diff blocks are OK)
* Tools: parameter changes, ordering changes, new guardrails
* Process: new checkpoints, tests, review gates
* Call out “expected improvement” (speed? accuracy? safety?)

## 9) Risks & Safety Checks

Same as M, but build a small risk register.
For each risk:

* Risk statement
* Severity (low/med/high)
* Likelihood (low/med/high)
* Mitigation + verification step
* Escalation trigger

## 10) Action Items (Owned, Finite, Testable)

Same as M, but add enforcement:

* Each item has: owner, priority, “done when,” and a **due window**
* Add one line: **“How we’ll confirm closure”** (review cadence or gate)

### Human

1. **…** (Priority: … / Done when: … / Due: …)
   N. **…**

### Agent

1. **…** (Priority: … / Done when: … / Due: …)
   N. **…**

---

## Optional Add-On A) Metrics & Evaluation (use when outcomes are measurable)

Add **only if** you can define numbers.

* Baseline vs after (time saved, accuracy, cost, defect rate)
* Test set / evaluation method
* Success thresholds for the next run

## Optional Add-On B) Counterfactuals & Alternatives (use when decisions were hard)

A short “what we’d try next if we restarted.”

* Top 2 alternative approaches
* Why they might outperform
* What evidence would justify switching

## Optional Add-On C) Rollout / Change Management (use when changes affect others)

If your deltas affect a team/system:

* Migration plan, comms, training notes
* Backout plan
* Ownership map

---

### Rule of thumb for L vs M

If any of these are true, bump to **L**:

* The job cost you “real money” (compute, time, risk, reputation)
* The job touched sensitive data or safety boundaries
* You hit the **same failure twice**
* You’re changing prompts/tools/processes that others will reuse

If you want, I can also provide a **one-page AI-AAR-L template** that’s fill-in-the-blanks (same sections, preformatted bullets) so it’s easy to run consistently.
