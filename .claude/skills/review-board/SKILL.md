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
governs everything below. This procedure grants no permission beyond what CLAUDE.md and the
researcher have granted. Its only obligations are procedural steps for the parent within a
Board run; the §10 audit package was adopted by the researcher's explicit instruction of
2026-10-13. Nothing here authorises a repository change, a phase advance, an experiment, a
commit or a push.
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
- **Roster.** At launch, write `review_board_roster_<YYYYMMDD_HHMM>.json` to the scratchpad:
  `{"reviewers": [{"id", "perspective", "agent_type", "enforcement"}]}`, one entry per reviewer.
  `id` is the agent id the Agent tool returns; `enforcement` is `tool` for `board-reviewer`,
  otherwise `instruction-only`. The §10 export reads it. It is **required** whenever the
  fallback type is used, because the exporter cannot otherwise find those reviewers.
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
- **Archive isolation (ADR-021).** Reviewers must not read prior Board audit packages.
  `.claude/settings.json` also denies `Read(/review_board_archive/**)`; the leading `/` anchors
  the pattern at the project root. In a runtime test on 2026-10-13, a `board-reviewer`'s direct
  Read of the archive was denied, and recursive Grep and Glob from the repository root returned
  nothing from it. A similarly named folder outside the archive, and ordinary repository files,
  stayed readable. Grep and Glob coverage is best-effort, as for session logs. If a reviewer
  needs something from a past package, the parent copies that specific item into the brief
  and labels it. The parent audits the archive through Bash.

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

## 10. Audit package and provenance: mandatory after every Board

Adopted by the researcher's instruction of 2026-10-13 (ADR-021). After the report is
delivered, the parent always builds a minimized audit package. This is not an offer.
Building it is the only step the parent takes without asking, because it writes nothing
that Git tracks.

1. **Account for every reviewer.** The report names each reviewer and confirms it reported.
   None may arrive unannounced.
2. **Audit isolation.** Check each reviewer's transcript (through Bash, as in §4) for
   file-access calls that name session logs or `review_board_archive/`. Record the result.
3. **Build the package** from the repository root:

   ```
   my_virtual_env_swarag\Scripts\python.exe scripts\_export_review_board.py export --session <session-uuid> --label <short_label> --question "<question>" --roster <roster.json> --brief <brief.md> --report <report.md> --since <ISO launch time> --extra <verification files...> --isolation-status "<step 2 result>"
   ```

   It writes `review_board_archive/<YYYY-MM-DD>/<label>_<HHMM>/`. That folder is local and
   gitignored, sits outside the source-of-truth hierarchy, and is not canonical evidence. The
   tool never overwrites an existing package.
4. **What the package contains by default (minimized):** the brief, the report,
   `roster.json`, each reviewer's final report, minimized reviewer transcripts and the
   parent's Board segment (user/assistant text, tool calls and tool results only), the
   verification files, `manifest.json`, the secret-scan report, `SHA256SUMS.txt` and
   `provenance_entry.md`. Thinking blocks, injected or system context, session metadata and
   the full raw session log are **excluded**. The full raw log is added only with
   `--full-session-log`, and only when the researcher explicitly asks for it for that run.
5. **Describe protection exactly as:** identifier redaction for known classes and a
   best-effort secret scan. Never call a package fully redacted, private or secret-free.
   Report the number of secret findings. Absence of findings proves nothing.
6. **Fallback and failure.** Without `--roster`, the tool falls back to `board-reviewer`
   subagents started at or after `--since`, which cannot find fallback-type reviewers. A
   reviewer with no transcript or final report is recorded as `MISSING`, never dropped. If
   the export is blocked, or a reviewer is `MISSING`, report the cause to the researcher;
   that report completes this step.
7. **Provenance.** `provenance_entry.md` is a draft ledger entry. It must be entered in
   `docs/review-board/PROVENANCE.md`, with the researcher's approval (§9), **before** any
   finding of the Board is used as supporting evidence in a canonical document: an ADR,
   PHASE_LOG, PROJECT_STATUS, a research plan, lessons, or other source-of-truth
   documentation. Otherwise entering it is optional.
8. **Report** the package path, the roster status, the secret-finding count and the
   `SHA256SUMS.txt` hash.

Reviewer transcripts also remain in the session log
(`~/.claude/projects/<project>/<session>/subagents/`) for as long as Claude Code keeps it.
