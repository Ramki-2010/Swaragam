---
name: review-board
description: Convene the Swaragam Research Review Board - six problem-specific expert perspectives in separate read-only contexts, a challengeable shared evidence brief, parent verification, correlation accounting, and a synthesis that preserves disagreement. Advisory only; user-invoked only.
argument-hint: <research question, hypothesis, finding or decision to review>
disable-model-invocation: true
---

# Research Review Board

**Under review:** $ARGUMENTS

If nothing was supplied above, ask the researcher for the question. Do not infer one.

**Standing.** Advisory only. The decision is recorded in `adr.md` ADR-019; ADR-020 records how it is enforced. `CLAUDE.md`
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

Label every item with the one canonical vocabulary, which `board-reviewer.md` repeats unchanged:
FACT · verified repository evidence · INFERENCE · HYPOTHESIS · EXTERNAL CONTEXT ·
NOT ESTABLISHED · REQUIRES AUTHORISATION.

The brief states these reviewer rules:

- read-only; anything state-changing is written as `REQUIRES AUTHORISATION: <action> - <why>` and not performed
- do not read session logs or other reviewers' output (see §4, Isolation)
- use the labels above
- no significance language unless a justified analysis exists
- do not re-derive established evidence and present it as your own finding
- never call a hypothesis a cause
- a word limit

**Mandatory reviewer section:** "WHAT IN THIS BRIEF IS WRONG, OVERSTATED,
INCOMPLETE, OR POTENTIALLY MISLEADING?" The brief is a claim to be challenged,
not ground truth.

## 4. Launch

- Use the Agent tool with `subagent_type: board-reviewer`. It is role-neutral and its only
  working tools are Read, Grep and Glob; the harness also adds its hand-back tool. If that type is not loaded in this session, use a
  built-in type and **record that read-only was enforced by instruction only**.
- Each prompt contains the brief's path plus that perspective's remit: expertise,
  questions, permitted reading and required output shape. Required output: verdict,
  labelled findings with sources (file:line, artifact or calculation), the
  brief-challenge section, REQUIRES AUTHORISATION items, and limitations.
- **Parallel by default**: all six in one message, as background tasks. Run in sequence only
  when a perspective genuinely needs another's output, and record that it lost
  contextual independence as a result.
- **Isolation.** Reviewers must not read session logs or other reviewers' output.
  `.claude/settings.json` denies `Read` on `~/.claude/projects/*/*.jsonl` and
  `~/.claude/projects/**/subagents/**`. In a test on 2026-10-12, direct Read and Grep on those
  paths were denied, and recursive searches from a parent folder returned nothing.
  This is a **path-specific** restriction, not a sandbox: reviewers can still read every
  other path. The parent audits reviewer transcripts through Bash, which these `Read` rules do not cover.
  If the deny rules are not active, record isolation as procedural only.

## 5. Parent verification

- Identify the claims that would change the conclusion. Verify them against the
  repository or authoritative artifacts, with effort in proportion to their importance.
- Record each one as **checked** (verified by the parent), **accepted** (carried
  forward unverified, so reviewer-reported), **corrected**, **downgraded** or **rejected**.
- Tag every claim in the report with exactly one provenance:
  **PARENT-VERIFIED** · **REVIEWER-REPORTED** · **INFERRED FROM IMPLEMENTATION** · **NOT TESTED**.
  A reviewer's description of its own tools or behaviour is REVIEWER-REPORTED until the
  parent checks it against the configuration or session log. Never promote a claim silently.
- Checking a claim against the same source the reviewers used confirms the reading,
  not the evidence. Say so.

## 6. Correlation ledger

For each important finding, record which perspectives reported it and the
underlying evidence they used. Then apply these rules:

- **Independent** means independent *upstream evidence*: a different dataset,
  measurement, instrument or artifact lineage. Separate agent contexts do not make
  findings independent.
- Findings from the same underlying evidence count as **one observation**, however many reviewers noticed it.
- Agreement between reviewers on the same base model adds **no** evidential weight. Only
  parent verification against a primary artifact, or a different upstream source, can
  strengthen a finding.
- Overlap between perspectives declared in §2 is recorded in the ledger. A finding
  reported by overlapping perspectives counts as one context.

## 7. Disagreement

Do not force consensus. For each disagreement:

- preserve it and give the reason
- classify it as factual, methodological, interpretive or evidential
- name the evidence that would resolve it

An unresolved disagreement is a valid result.

## 8. Report

Baseline sections. Adapt or drop the others as the problem requires. **Never omit
sections 6, 8, 12 or 14.** Write "none" if a section is empty. Section 14 is mandatory
whenever any recommendation changes state or needs authorisation.

1. Research question
2. Why the Board was invoked
3. Established evidence
4. Six perspectives selected and why (including overlap and rejected options)
5. Findings from each perspective
6. What was challenged in the evidence brief: **every** challenge, with its outcome
7. Agreements
8. Disagreements
9. Claims verified by Claude
10. Competing explanations
11. Evidence-quality assessment, using the §6 ledger
12. Unresolved items and limitations
13. Recommended next steps
14. **RESEARCHER DECISION REQUIRED**: every state-changing recommendation

## 9. Boundaries

The Board advises. It has no authority to do any of the following:

- advance a phase
- authorise an experiment
- change code, datasets, caches, canonical results, governance or ADRs
- commit or push

How this is enforced:

- **Reviewers** are tool-restricted. They have no write, execute or spawn tools.
- **The parent** keeps its full toolset. Its limits come from CLAUDE.md, this
  procedure and the researcher's approval, **not from a technical block**.

CLAUDE.md §§5, 8, 14–17a apply unchanged. Board output enters the repository only
with the researcher's approval, through normal documentation (for example, an append-only
PHASE_LOG observation).

Offer to export the brief and report. Reviewer transcripts persist in the session log
(`~/.claude/projects/<project>/<session>/subagents/`).
