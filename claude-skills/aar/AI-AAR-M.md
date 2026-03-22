# AI After Action Report: Medium Edition (AI-AAR-M)

AI-AAR-M is a **fast, structured handoff** between AI agent jobs/sessions. It captures the minimum context needed to (1) **continue work safely**, (2) **transfer field knowledge**, and (3) **improve the next run**. Timebox: **5–12 minutes**. Target length: **~250–600 words**. If it’s longer, you probably need AI-AAR-L.

## 1) Goal & Success Criteria

State the mission in one sentence, then define “done” with **observable outputs**.

* Use: *Deliverable + audience + format + quality bar*
* Include: acceptance criteria, non-goals, and “stop conditions” (when to halt/escalate)

## 2) Scope & Constraints

Capture what boxed you in so Job 2 doesn’t repeat the same dead ends.

* Inputs available (docs, APIs, repos), permissions, deadlines
* Hard constraints: time, budget, policy, tooling, environment, versions
* Assumptions that were **treated as true** (even if uncertain)

## 3) What Happened (Actual Outcome)

Describe results, not narrative.

* What was produced, where it lives (links/paths), current status (% done)
* What remains unfinished + why (blocked vs deprioritized vs unknown)
* If a result is unreliable, label it **UNVERIFIED**

## 4) Key Discoveries (Field Notes)

High-value facts Job 2 should reuse immediately.

* New facts, edge cases, gotchas, hidden requirements
* “Unknown unknowns” discovered (surprises)
* Distinguish: **Confirmed** vs **Suspected** vs **Needs validation**

## 5) Decisions & Rationale

Record the forks in the road so Job 2 can defend or revisit them quickly.

* Decision + options considered + why chosen
* If reversible, say so; if irreversible/costly, flag it
* Note any “default choices” the agent made implicitly

## 6) What Worked (Keep)

Preserve momentum.

* Tactics that saved time (queries, tools, prompts, workflows)
* Reusable snippets/templates (include pointers, not long paste)
* Conditions under which it worked (so it doesn’t get misapplied)

## 7) What Didn’t Work (Change)

Be blunt and specific—this is where improvement comes from.

* Failure modes (e.g., ambiguity, hallucination risk, tool friction)
* Root cause in one line (best guess is fine; label it)
* Fix suggestion (not just complaint)

## 8) Prompt / Tool / Process Deltas

Make the next run better in concrete, copyable edits.

* Prompt changes: add/remove constraints, examples, schema, refusal rules
* Tooling changes: use tool earlier/later, different parameters, caching
* Process changes: checkpoints, verification steps, test harness, QA

## 9) Risks & Safety Checks

Prevent repeat incidents and silent failure.

* Sensitive data handling, permissions boundaries, compliance constraints
* Verification plan: how Job 2 should validate key claims/outputs
* Escalation triggers: “If X happens, stop and ask human”

## 10) Action Items (Owned, Finite, Testable)

If it isn’t owned, it won’t happen. Each item should be:
**verb-first**, measurable, and have a “done” test.

### Human

1. **…** (Done when: …)
2. **…**
   N. **…**

### Agent

1. **…** (Done when: …)
2. **…**
   N. **…**

---

### Optional Footer (recommended)

* **Job ID / Date / Agent version**
* **Primary artifacts/links**
* **Next job kickoff note**: the single most important instruction for Job 2
