# Swarag — Architecture Decision Records

Mandated by the Vision Bible (Section 12). Each ADR documents a decision
already made and evidenced elsewhere in the memory files. Generated
2026-07-11 against v1.3.2. Format: Context -> Decision -> Consequence -> Status.

---

### ADR-001: Deterministic DSP over Machine Learning
- **Context**: Small dataset (<100 clips), need for interpretable errors.
- **Decision**: Use hand-designed DSP features (PCD, dyads) with deterministic
  scoring rather than a trained classifier.
- **Consequence**: No black-box failures; every error is traceable to a
  specific feature or weight. Slower to add new discriminative power than ML.
- **Status**: ACTIVE. Revisit per ML Roadmap (Bible Section 10) once
  deterministic features mature and diverse data exists.
- **Source**: ARCHITECTURE.md Design Constraints; Bible Section 10.

### ADR-002: 72-bin Pitch Class Distribution
- **Context**: 36-bin PCD could not separate shuddha Ma from prati Ma
  (92 cents apart, only 2-3 bins at 36-bin resolution).
- **Decision**: Use 72 bins (17 cents/bin) as the PCD resolution.
- **Consequence**: +11.9% LOO accuracy (66.7% -> 78.6% in the 6-raga
  sandbox). 96+ bins tested and rejected — too sparse, inflated UNKNOWN rate.
- **Status**: ACTIVE, locked.
- **Source**: L-034, Run 2026-03-12 (LOO 36 vs 72 bins).

### ADR-003: IDF x Variance PCD Weighting
- **Context**: Common swaras (Sa, Pa) shared across all ragas were diluting
  dot-product similarity.
- **Decision**: Weight each PCD bin by inverse document frequency times
  1/std, downweighting common swaras and upweighting distinctive ones.
- **Consequence**: +6% production accuracy over baseline dot-product;
  single biggest improvement after the ALPHA fix.
- **Status**: ACTIVE, locked.
- **Source**: L-030.

### ADR-004: Laplace Smoothing ALPHA = 0.01
- **Context**: ALPHA=0.5 on 1296-cell dyad matrices added more smoothing
  mass (648) than signal (~370 transitions/file); dyad similarities were
  ~0.001 for all ragas (noise).
- **Decision**: Set ALPHA=0.01, scaled to matrix size.
- **Consequence**: Discrimination ratio improved 1.24x -> 1.73x.
- **Status**: ACTIVE, locked.
- **Source**: L-023, L-026.

### ADR-005: Global Fusion Weight PCD=0.8 / Dyad=0.2
- **Context**: At 7 ragas / 70 clips, 72x72 dyad matrices are still sparse.
  Weight sweep tested 0.6/0.4, 0.7/0.3, 0.8/0.2.
- **Decision**: 0.8/0.2 as the global default, applied uniformly to all
  ragas as of v1.3.2 (see ADR-013 — no per-raga exceptions remain).
- **Consequence**: Fewest wrongs of the configs tested at fixed margin
  threshold.
- **Status**: ACTIVE. Revisit when per-raga clip counts reach 15-20+ and
  dyad discrimination ratio exceeds 2.0x.
- **Source**: L-045.

### ADR-006: Per-Raga Override — Bhairavi = 0.5/0.5 [SUPERSEDED]
- **Context**: Bhairavi's dyads were believed genuinely distinctive
  (unlike most ragas, where per-raga overrides just trade accuracy
  between ragas).
- **Decision**: Override fusion weight to 0.5/0.5 for Bhairavi only.
- **Consequence**: Appeared net-positive against a 67.4% LOO table logged
  at the time. That table was later found fabricated — its per-raga rows
  never summed to its own TOTAL row. On the canonical rerun
  (`sandbox_loo_v131_canonical.py`), the override produced 0% decided for
  Bhairavi (9 wrongs).
- **Status**: **SUPERSEDED by ADR-013.** Kept as a record that a decision
  was made on unverified evidence — this is the concrete case for ADR-011
  (LOO is the only tier trusted for accuracy claims).
- **Source**: L-042, datasets.md baseline reconciliation, commit b1a1ac9.

### ADR-007: MIN_CLIPS_PER_RAGA = 5 Guardrail
- **Context**: Adding ragas with 1-3 clips (Abhogi, Saveri, Madhyamavati at
  the time) dropped LOO accuracy from 72.0% to 41.7% — thin models became
  false attractors.
- **Decision**: Exclude any raga with fewer than 5 clips from aggregation.
  Keep features on disk (not deleted) so they activate automatically once
  the threshold is met.
- **Consequence**: Prevents thin-data sink behavior. Currently excludes
  Kamboji (3), Madhyamavati (2), Hamsadhvani (1).
- **Status**: ACTIVE, locked.
- **Source**: L-036, BUG-011.

### ADR-008: Absent-Swara Penalty — Rejected
- **Context**: Abhogi (janya, subset of Kalyani's swaras) needed a way to
  score "expected but absent" swaras. Two approaches tried: data-driven
  (median threshold on model PCD) and musicological (known swara bin ranges).
- **Decision**: Reject both. Gamaka ornamentation spreads energy into
  neighboring swara bins, so a "missing" swara still shows 6-19% energy —
  binary absent/present detection cannot separate signal from gamaka leakage.
- **Consequence**: Do not re-attempt binary absent-swara detection. Active
  replacement direction: quantitative energy-ratio comparison
  (`sandbox_abhogi_ratio.py`, BUG-015).
- **Status**: REJECTED, added to proven-dead-ends list.
- **Source**: L-046, BUG-015.

### ADR-009: Mandatory Vocal Isolation
- **Context**: Blind test showed 64% accuracy / 100% OOD rejection on
  vocal-isolated audio vs 38% accuracy / 25% OOD rejection on mix audio,
  same models and thresholds.
- **Decision**: Vocal isolation (Saraga stems or Demucs) is a mandatory
  pipeline step, not optional preprocessing.
- **Consequence**: BUG-009 (mix audio OOD false positives) remains open
  specifically because this mandate is not yet enforced in code — confirmed
  2026-07-10: `scripts/recognize_raga_v12.py` contains no vocal/Demucs/
  isolation check. Policy exists, enforcement does not.
- **Status**: ACTIVE as policy; enforcement OPEN (tracked under BUG-009).
- **Source**: L-028, L-029, BUG-009.

### ADR-010: Sandbox-First Development
- **Context**: A silent production breakage (BUG-001) demonstrated that
  direct edits to production scripts are unsafe without a comparison step.
- **Decision**: Every fix is implemented in a `test_*.py` / `sandbox_*.py`
  script, compared before/after, and only promoted to production if results
  are strictly better.
- **Consequence**: Near-zero code regressions since adoption. Notably did
  NOT prevent the Bhairavi override (ADR-006) from shipping on fabricated
  documentation — sandbox-first protects code paths, not the accuracy
  numbers logged about them. See ADR-011.
- **Status**: ACTIVE, mandatory. See workflow.md Section 5.
- **Source**: L-011, L-015, workflow.md.

### ADR-011: LOO Cross-Validation as the Trust Standard
- **Context**: Self-evaluation (model built and tested on the same clips)
  overestimated accuracy by 10-15% versus true held-out performance. Later,
  a hand-typed LOO table (67.4%) was found fabricated — internally
  inconsistent row sums — despite looking like a real run.
- **Decision**: Leave-one-out cross-validation, run via a checked-in script
  (not hand-typed), is the only accuracy number treated as canonical.
- **Consequence**: Canonical baseline is pessimistic but honest. Directly
  caused the Bhairavi override retirement (ADR-013) once the real rerun
  contradicted the fabricated one.
- **Status**: ACTIVE, locked.
- **Source**: L-031, L-033, ADR-013.

### ADR-012: Multi-Agent Analysis Is On-Demand, Not Routine
- **Context**: Running the 5-expert analysis on every change wastes tokens
  on decisions that don't need it.
- **Decision**: Reserve `/analyze-swarag` for genuinely hard, cross-domain,
  or mixed-result decisions.
- **Consequence**: Faster iteration on routine work.
- **Status**: ACTIVE, locked.
- **Source**: L-014, workflow.md Section 12.

### ADR-013: Retire Bhairavi Per-Raga Override
- **Context**: Canonical LOO rerun (`sandbox_loo_v131_canonical.py`)
  showed the Bhairavi 0.5/0.5 override at 0% decided (9 wrongs), directly
  contradicting the 40% figure ADR-006 was built on.
- **Decision**: Retire the override. Bhairavi uses the uniform 0.8/0.2
  global weight like every other raga (ADR-005).
- **Consequence**: Overall canonical LOO moved 60.5% (with override,
  confirmed bad) -> 64.1% (without it), +3.6pp. Bhairavi itself sits at
  14% decided standalone — weak, but no longer masked by an unsupported
  weight hack. (Historical hypothesis, NOT established by this ADR's
  evidence: "its real fix is more diverse training clips." The LOO rerun
  cited here measured accuracy, not cause. Whether the limit is data or
  representation is the open question of Q-003.)
  Follow-up (2026-07-11): `scripts/confusion_matrix_audit.py` — the very
  script whose Scenario 1/2 comparison motivated this retirement — was
  found still hardcoding the override as its own "canonical" default one
  commit later. Fixed same day. See Section 11 of the Dossier.
- **Status**: ACTIVE, locked. Commit `21da815`.
- **Source**: datasets.md CANONICAL v1.3.2 table, commit `21da815`.

### ADR-014: Energy-Ratio Scoring — Rejected for Abhogi/Kalyani Separation
- **Context**: BUG-015 (Abhogi janya absorption) needed a successor to the
  rejected absent-swara penalty (ADR-008). Quantitative Pa/N3 energy-ratio
  comparison (`sandbox_abhogi_ratio.py`) was proposed as a more precise,
  non-binary alternative.
- **Decision**: Reject. Phase 1 diagnostic showed Abhogi and Kalyani's Pa
  energy distributions have essentially no separation (ratio=1.01x, 4/7
  Abhogi clips overlap Kalyani's Pa range). Phase 2 LOO sweep confirmed
  this at the outcome level: Abhogi's per-raga result was byte-identical
  (C=1/W=2/U=4, 33%) at every tested ratio_weight from 0.05 to 0.40. The
  approach's own topline "+1.0% improvement" was unrelated collateral
  (Bhairavi/Thodi gains, a Mohanam regression) and did not reflect any
  actual signal for the target raga.
- **Consequence**: Confirms the Abhogi problem is not solvable by any
  scoring-time adjustment to PCD-derived features (weight overrides,
  absent-swara penalty, and now energy ratios have all failed for the
  same underlying reason: gamaka spillover makes Abhogi and Kalyani's
  swara-energy profiles genuinely overlap, not just hard to threshold).
  Points decisively toward phrase-level or sequence-level features
  (n-grams, contour templates) as the only untried category.
- **Status**: REJECTED, added to proven-dead-ends list.
- **Source**: BUG-015, L-050, datasets.md Run 2026-07-11.

### ADR-015: Audit Scripts Import Shared Constants Instead of Duplicating
- **Context**: Both `confusion_matrix_audit.py` and `sandbox_abhogi_ratio.py`
  hardcoded their own copies of scoring constants (N_BINS, ALPHA, weights,
  PER_RAGA_WEIGHTS). One of those copies drifted stale for a single commit
  (2026-07-11) and silently mislabeled a retired config as canonical
  (BUG-017).
- **Decision**: Both scripts now `from recognize_raga_v12 import (...)`
  the shared scoring constants instead of redefining them. Already
  established as safe by `batch_evaluate.py`'s existing import of
  `recognize_raga_v12.recognize_raga`.
- **Consequence**: The specific "duplicate constant drifts stale" failure
  mode is now structurally impossible for these two files — if production
  constants change, both scripts pick up the change automatically with no
  manual sync step to forget. Does not prevent other corruption patterns
  (e.g. the docs/ARCHITECTURE.md editor-placeholder corruption, BUG-017) —
  those need a different mitigation (see BUG-017's recommended pre-commit
  check, not yet implemented).
- **Status**: ACTIVE, locked.
- **Source**: BUG-017, L-002, this session.

### ADR-016: Every Published Benchmark Must Be One-Command Reproducible
- **Context**: Two fabricated LOO tables (67.4%, 72.3%) entered the record
  because benchmarks were hand-typed rather than generated. A number that no
  one can regenerate from the repository is unverifiable — and, as ADR-006
  showed, decisions get built on it before the fabrication is caught.
- **Decision**: Any accuracy figure cited as canonical must be reproducible by
  a single command from a clean clone:
  ```
  git clone https://github.com/Ramki-2010/swarag
  cd swarag && pip install -r requirements.txt
  python benchmark.py
  ```
  producing the canonical figure (currently 64.1% decided, 25c/14w/31u)
  deterministically, with zero manual steps. A benchmark that cannot be
  reproduced this way may not be cited as canonical.
- **Consequence**:
  - Requires a single canonical entry point `benchmark.py` wrapping
    `sandbox_loo_v131_canonical.py`. Not yet created.
  - Requires the evaluation data (extracted features, or audio plus a
    one-command extraction step) to be present in or fetched by the repo.
    **Currently UNMET** — no audio or feature set ships in the clone, so the
    standard is aspirational until data provenance is solved. This is the
    real blocker, not the script.
  - Doubles as a regression and corruption tripwire: wired into CI or the
    pre-commit gate, any behavioural drift — including the BUG-016/017
    file-corruption class — changes the output and fails the build. This is
    the strongest available check that the codebase still produces the
    number the docs claim.
- **Status**: ACTIVE as standard; enforcement OPEN (no `benchmark.py`, no
  bundled/fetchable evaluation data yet). Mirrors ADR-009's policy-exists /
  enforcement-open split.
- **Source**: BUG-017, ADR-011, the fabricated 67.4% and 72.3% tables.

### ADR-017: Feature Cache Reuse Requires Validation; FEATURE_VERSION Has One Owner
- **Context**: Q-001A needed pyin features for many clips; re-running pyin live
  is the sole bottleneck (~2 min/clip). The production extractor already caches
  raw `f0` to `features_v12/*.npz`. Separately, `FEATURE_VERSION` was hardcoded
  in four active scripts, so a format bump would silently break cache lookup
  everywhere. (Two further copies exist in `scripts/archive/` — deprecated
  pre-v1.2 scripts, intentionally left untouched by the refactor.)
- **Decision**:
  1. Experiments MAY reuse cached raw `f0` (never `cents_gated`, a different
     post-gate array) and skip pyin, but ONLY after `--validate` proves
     cache == live for the corpus in use (f0 bit-exact AND all metrics
     identical). Re-validate after any change to extraction / downstream pitch
     logic or a librosa upgrade.
  2. `FEATURE_VERSION` is owned by `scripts/feature_constants.py`; every
     producer and consumer imports it. Never imported from a producer module
     (import-time side effects) and never re-declared.
- **Consequence**: Q-001A/B run in seconds on cached clips; cache faithfulness
  is provable, not assumed; a feature-format bump is a one-line change all
  readers follow. Validated once over a 30-clip subset (L-051: 0 mismatches,
  maxdiff 0). The cache directory holds more clips than that subset —
  cache presence is not cache validation, and the proven-faithful scope is
  the 30 clips actually run through `--validate`, not the directory as a whole.
- **Status**: ACTIVE.
- **Source**: L-051, L-053, ADR-015 (single-source discipline).

### ADR-018: Adoption of Phrase Evaluation Protocol v1.0
- **Context**: Q-001A's representation-sufficiency result (n=7, permutation
  p=0.39) and Q-001B planning surfaced three methodological gaps, each caught
  ad hoc rather than by a standing rule: no defined statistical bar for a
  promotion decision at low sample sizes; a mean-vs-threshold verdict
  practice later replaced by paired permutation testing (L-052); and, during
  the Q-001B feasibility review, a repository-verified composition confound
  — 5 of Abhogi's 7 clips and 4 of confuser Kalyani's 14 clips traced to the
  same externally sourced compositions, sung by different performers, not
  independent samples. None were coding defects; each was an unstated
  assumption the project had been relying on. Left uncodified, each would
  need rediscovering for every future raga pair and phrase hypothesis.
- **Decision**: Adopt **Phrase Evaluation Protocol v1.0** as the canonical
  methodology governing phrase-based research. Every future phrase
  experiment, starting with Q-001B, is designed and reported under the
  protocol; every future production promotion decision for a phrase-based
  method must satisfy the protocol before entering production. Methodology
  changes are made by revising the protocol itself, not through ad hoc
  per-experiment decisions — this ADR records the adoption, it is not
  updated when the protocol is.
- **Consequence**: One versioned methodology replaces context scattered
  across workflow.md, lessons.md, and individual experiment plans — a new
  raga or hypothesis starts from a template, not a blank page, and Q-001B's
  promotion decision now has a pre-committed, auditable bar instead of a
  per-experiment judgment call. Trade-off: pre-registration and composition
  auditing add upfront cost an informal sandbox check didn't require, and a
  quick exploratory run has no path to a production decision unless
  escalated to a properly gated experiment. Enforcement is documentation-level
  only — nothing currently blocks a phrase experiment from running outside
  the protocol, the same policy-exists/enforcement-open gap already logged
  in ADR-009 and ADR-016.
- **Status**: ACTIVE.
- **Date**: 2026-08-08.
- **Source**: Phrase Evaluation Protocol v1.0
  (`.ai-memory/phrase-evaluation-protocol.md`, full methodology, not
  duplicated here); Q-001A (n=7, p=0.39); L-049/BUG-018 (LOO leakage); L-050
  (topline-hides-target-miss); L-052 (mean-vs-threshold correction);
  PROJECT_STATUS.md Research Gates table; workflow.md Promotion Rule;
  evaluation-protocol.md; ADR-009, ADR-011, ADR-016 (enforcement-gap and
  LOO-trust precedent).

### ADR-019: Research Review Board — On-Demand, Advisory, Dynamically Composed
- **Context**: Some research decisions need challenge from several
  perspectives, which `/analyze-swarag` does not provide: its five roles are
  fixed, engineering-focused, and simulated within one model (ADR-012). The
  2026-10-12 Q-003 Council ran six separate read-only subagents. That showed
  the value of separate contexts, a shared evidence brief that reviewers must
  challenge, verification of key claims by the parent, and explicit
  correlation accounting. It also showed that its six roles were specific to
  one problem, and that parallel reviewers reading the same data are not
  independent evidence (L-055).
- **Decision**: Adopt a Research Review Board as an on-demand capability.
  Each invocation assembles **six perspectives chosen by Claude for that
  problem**. No roles, prompts or evidence packages are fixed. The procedure
  lives only in `.claude/skills/review-board/SKILL.md`, which is user-invoked
  only (`/review-board`). Reviewers run as the role-neutral, read-only
  `board-reviewer` subagent (`.claude/agents/board-reviewer.md`). This does
  not replace, wrap or modify the Multi-Agent Analyst (ADR-012, RULE 13,
  workflow.md §12).
- **Consequence**: Hard questions can get multi-perspective review without
  standing roles drifting into canon. The Board is **advisory**. It has no
  authority to advance phases, authorise experiments, or change code, data,
  caches, canonical results, governance or ADRs, and it cannot commit; all of
  that remains under CLAUDE.md and explicit researcher approval. Its reports
  are non-canonical unless separately approved for recording. Costs: about six
  subagent contexts per run, so it inherits ADR-012's on-demand rule. The
  read-only guarantee is enforced by tool restriction, so it holds only where
  the `board-reviewer` type is loaded; otherwise it falls back to instructions.
- **Status**: ACTIVE.
- **Date**: 2026-10-12.
- **Source**: Q-003 Council run and forensic report (2026-10-12, session
  records outside the repository); L-055; ADR-012; L-014.

### ADR-020: Review Board Enforcement Scope and Reviewer Isolation (refines ADR-019)
- **Context**: The 2026-10-12 runtime smoke test of ADR-019 found two problems.
  First, reviewer Read, Grep and Glob are not limited to particular paths: one reviewer read sibling
  reviewers' perspective names from the session log. Second, ADR-019's
  Consequence says the Board "cannot commit". That is true only of the
  tool-restricted reviewers; the orchestrating parent keeps its full toolset.
  ADR-019 is ACTIVE and is not edited (Maintenance Rule), and its decision stands.
- **Decision**: (1) Project permission deny rules in `.claude/settings.json` keep reviewers out of
  session transcripts. They deny `Read` on `~/.claude/projects/*/*.jsonl` and
  `~/.claude/projects/**/subagents/**`. On 2026-10-12 this was verified to deny a
  `board-reviewer`'s direct Read and Grep, and to exclude those files from its
  recursive searches. (2) ADR-019's "cannot commit" is scoped as follows:
  reviewers technically cannot write, execute or spawn. The parent's advisory limits
  are procedural (CLAUDE.md, the `/review-board` procedure, researcher approval),
  not technical. (3) **Deferred, not decided:** a reverse pointer from the
  Multi-Agent Analyst documentation (ADR-012, RULE 13, workflow.md §12) to the Board,
  and a rule for choosing between the two. Those documents are protected, so
  adding either needs a separate decision.
- **Consequence**: Reviewer isolation is now technical for the known transcript
  paths, and only for those. Reviewers can still read every other path, and the docs
  describe Read rules as best-effort for Grep and Glob. The deny rules also apply to the main
  conversation's Read tool, so the parent audits transcripts through Bash. Nothing
  technical binds the parent; its advisory status rests on governance.
- **Status**: ACTIVE.
- **Date**: 2026-10-12.
- **Source**: `/review-board` smoke test, 2026-10-12, and the isolation test
  (session records outside the repository); Claude Code permissions documentation
  (deny rules apply to subagents; `//`/`~/` path anchors); ADR-019;
  `.claude/skills/review-board/SKILL.md` §4 and §9.

### ADR-021: Review Board Audit Archive, Minimized Export and Provenance Ledger (refines ADR-019 and ADR-020)
- **Context**: ADR-019 and ADR-020 cite Board runs only as "session records outside the
  repository". Those records are deletable and cannot be checked from the repository
  (CLAUDE.md §18). A repository-native provenance record was proposed on 2026-10-12 and
  deferred. On 2026-10-13 an unpushed design made a full raw-session export to Downloads
  mandatory after every Board. Review found that this retained far more than auditing needs:
  injected context, reasoning blocks and unrelated session content. It claimed redaction
  more strongly than the tool delivered, had no secret scan, could not export reviewers of
  the §4 fallback type, and placed transcript copies outside ADR-020's deny rules, where
  later reviewers could read them. That design was replaced before push. ADR-019 and
  ADR-020 are ACTIVE and are not edited; their decisions stand.
- **Decision**: (1) **Local archive.** Board audit packages live in the project-local,
  gitignored `review_board_archive/`. It is a retention area, never committed, outside the
  CLAUDE.md §4a source-of-truth hierarchy. Storing something there does not make it
  canonical evidence. (2) **Minimized export by default.** After every Board the parent builds
  a package with `scripts/_export_review_board.py` (SKILL.md §10). It contains the brief, the
  report, a roster, each reviewer's final report, minimized transcripts and the parent's
  Board segment (text, tool calls and tool results only), verification files, a manifest, a
  secret-scan report, `SHA256SUMS.txt` and a draft provenance entry. Reasoning blocks,
  injected context, session metadata and the full raw session log are excluded.
  (3) **Full raw-session export is opt-in** (`--full-session-log`). It is used only when the
  researcher explicitly asks for it for that run. (4) **Protection** is described only as
  identifier redaction for known classes and a best-effort secret scan. The classes are:
  emails, owner name tokens, the Windows username, org and account IDs on narrow patterns,
  and session IDs. The scan finds common credential formats and records findings without
  their values. No package is described as fully redacted, private or secret-free, and an
  empty scan proves nothing. (5) **Roster.** Reviewers are exported from a roster written
  at launch, whatever their agent type. Without a roster, a documented `board-reviewer`
  fallback applies. A reviewer with no transcript or final report is recorded as `MISSING`
  and reported to the researcher, never dropped. (6) **Reviewer isolation from prior
  archives.** `.claude/settings.json` also denies `Read(/review_board_archive/**)`, and
  `board-reviewer.md` prohibits archive reads. Evidence from a past package reaches a reviewer
  only when the parent copies it into the brief. (7) **Provenance is separate from transcript
  retention.** `docs/review-board/PROVENANCE.md` is the durable, append-only record: date,
  question, HEAD, roster, enforcement, isolation result, artifact hashes, and no transcript
  content. An entry, approved by the researcher, must exist **before** any Board finding is
  used as supporting evidence in a canonical document (an ADR, PHASE_LOG, PROJECT_STATUS, a
  research plan, lessons or other source-of-truth documentation). (8) **Historical exports.**
  The two existing Downloads exports (2026-10-12 Council, 2026-10-13 Q-003 Board) were moved
  into the archive. Each was preserved verbatim with an inventory and verified hashes before
  its original was removed, and labelled historical: it predates this architecture, is kept
  for audit and reference, and is not a governance authority. A minimized package was derived
  from each. They are **not** entered in the ledger; backfill is a separate decision.
  (9) **Approval boundaries.** Building a package is the only step the parent takes without
  asking, because it writes nothing that Git tracks. Ledger entries, backfill, and any use of
  a Board finding in a canonical document need researcher approval, as before (ADR-019; SKILL.md §9).
- **Consequence**: A cited Board run becomes checkable from the repository: the ledger holds
  its hashes, and the local package holds the content they cover. Retention shrinks to what
  auditing needs. Limits: a package exists only on the researcher's machine, so if it is lost
  the ledger records what existed but cannot be re-checked. Redaction covers known identifier
  classes only, and the secret scan is pattern-based. Archive isolation is path-specific,
  like ADR-020: Grep and Glob coverage is best-effort, and the parent is not technically
  bound. In this session, settings changes took effect after a delay, so a newly added deny
  rule must be re-tested after a pause before it is relied on. Historical `source_as_found/`
  copies still hold full session material, including reasoning blocks, because that is how
  they were originally exported.
- **Status**: ACTIVE.
- **Date**: 2026-10-13.
- **Source**: Review of the replaced, unpushed commit `36bee7e` (2026-10-13); the deferred
  2026-10-12 provenance target; runtime isolation test, 2026-10-13. In that test a
  `board-reviewer` (agent `a156b20f19d737a80`) was denied a direct Read of the archive, and
  Grep and Glob returned nothing from it. A similarly named folder outside the archive and
  ordinary repository files stayed readable. The parent's Bash access and ADR-020's
  session-log denial were unchanged. Verified from the raw transcript. Exporter tests:
  synthetic planted credentials and identifiers, and a live export from unredacted logs.
  ADR-019; ADR-020; L-055; `.claude/skills/review-board/SKILL.md` §4 and §10.

---

## Maintenance Rule

New ADRs are added, never edited after Status is set to ACTIVE/REJECTED —
if a decision is reversed, write a new ADR that supersedes the old one and
mark the old one's Status as SUPERSEDED with a pointer forward. ADR-006 /
ADR-013 is the reference example for how to do this.