---
name: review-board
description: Convene the Swaragam Research Review Board - six problem-specific expert perspectives in separate read-only contexts, a challengeable shared evidence brief, parent verification, correlation accounting, and a synthesis that preserves disagreement. Advisory only; user-invoked only.
argument-hint: <research question, hypothesis, finding or decision to review>
disable-model-invocation: true
---

# Research Review Board

**Under review:** $ARGUMENTS

If nothing was supplied above, ask the researcher for the question. Do not infer one.

**Standing.** Advisory only. The decision is recorded in `adr.md` ADR-019. `CLAUDE.md`
governs everything below: this procedure adds no rule and grants no permission.
It is separate from `/analyze-swarag` (ADR-012), which it neither wraps nor
replaces. It may recommend `/analyze-swarag` when that tool fits better.

**Standing rule:** reuse recently verified evidence; only re-check if stale,
contradictory, materially changed, or insufficient.

---

## 1. Frame the problem, before choosing anyone

Establish the current state as CLAUDE.md §2 requires, in proportion to the question. Then write down:

- what exactly is being investigated
- what is established (cite file, commit or artifact, and label it)
- what is uncertain
- which assumptions support the current interpretation
- what could reasonably be wrong
- what evidence would distinguish the competing explanations

If one perspective can answer the question, say so and ask whether to proceed
anyway. A Board is costly (ADR-012).

## 2. Compose the board: six perspectives derived from this problem

There is no fixed roster. Derive six perspectives from §1. Prefer:

- **distinct questions** and, where possible, **distinct primary evidence sources**
- coverage of the assumptions listed in §1
- **at least one perspective whose job is to challenge the leading interpretation**
- a methodology or governance perspective **when** the question touches sequencing,
  thresholds, provenance, authorisation or a frozen decision

Do not manufacture diversity. If six genuinely distinct angles do not exist,
run six useful ones and **declare the overlap**.

For each perspective record its name, why it was chosen, the questions it must answer,
and what it should inspect. Also record the perspectives you considered and rejected.

## 3. Shared evidence brief

Write one brief to the **session scratchpad** (never the repository), as
`review_board_brief_<YYYYMMDD_HHMM>.md`. It contains:

- the research question
- established and recently verified evidence, with sources
- current uncertainty and important assumptions
- relevant constraints and the governance boundary
- investigation-specific context

Label every item: FACT · verified repository evidence · INFERENCE · HYPOTHESIS ·
EXTERNAL CONTEXT · NOT ESTABLISHED.

The brief states these reviewer rules:

- read-only; anything state-changing is written as `REQUIRES AUTHORISATION: <action> - <why>` and not performed
- use the labels above
- no significance language unless a justified analysis exists
- do not re-derive established evidence and present it as your own finding
- never call a hypothesis a cause
- a word limit

**Mandatory reviewer section:** "WHAT IN THIS BRIEF IS WRONG, OVERSTATED,
INCOMPLETE, OR POTENTIALLY MISLEADING?" The brief is a claim to be challenged,
not ground truth.

## 4. Launch

- Use the Agent tool with `subagent_type: board-reviewer`. It is role-neutral and has only
  the Read, Grep and Glob tools. If that type is not loaded in this session, use a
  built-in type and **record that read-only was enforced by instruction only**.
- Each prompt contains the brief's path plus that perspective's remit: expertise,
  questions, permitted reading and required output shape. Required output: verdict,
  labelled findings with sources (file:line, artifact or calculation), the
  brief-challenge section, REQUIRES AUTHORISATION items, and limitations.
- **Parallel by default**: all six in one message, as background tasks. Run in sequence only
  when a perspective genuinely needs another's output, and record that it lost
  contextual independence as a result.
- Reviewers do not see each other's reports.

## 5. Parent verification

- Identify the claims that would change the conclusion. Verify them against the
  repository or authoritative artifacts, with effort in proportion to their importance.
- Record each one as accepted, checked, corrected, downgraded or rejected.
- Label anything unverified as **reviewer-reported**. Never promote it silently.
- Checking a claim against the same source the reviewers used confirms the reading,
  not the evidence. Say so.

## 6. Correlation ledger

For each important finding, record:

- which perspectives reported it
- the underlying evidence they used
- its class: **contextual diversity** (separate contexts), **analytical agreement**
  (same evidence, same reading), or **independent evidence** (different data, method or
  instrument)

The same source counts as **one observation**, however many reviewers noticed it.
Reviewers that run on the same base model are themselves a further correlation.

## 7. Disagreement

Do not force consensus. For each disagreement:

- preserve it and give the reason
- classify it as factual, methodological, interpretive or evidential
- name the evidence that would resolve it

An unresolved disagreement is a valid result.

## 8. Report

Baseline sections. Adapt them, and drop any that are irrelevant:

1. Research question
2. Why the Board was invoked
3. Established evidence
4. Six perspectives selected and why (including overlap and rejected options)
5. Findings from each perspective
6. What was challenged in the evidence brief
7. Agreements
8. Disagreements
9. Claims verified by Claude
10. Competing explanations
11. Evidence-quality assessment, using the §6 ledger
12. Unresolved items
13. Recommended next steps
14. **RESEARCHER DECISION REQUIRED**: every state-changing recommendation

## 9. Boundaries

The Board advises. It cannot do any of the following:

- advance a phase
- authorise an experiment
- change code, datasets, caches, canonical results, governance or ADRs
- commit or push

CLAUDE.md §§5, 8, 14–17a apply unchanged. Board output enters the repository only
with the researcher's approval, through normal documentation (for example, an append-only
PHASE_LOG observation).

Offer to export the brief and report. Reviewer transcripts persist in the session log
(`~/.claude/projects/<project>/<session>/subagents/`).
