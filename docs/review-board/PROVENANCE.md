# Review Board provenance ledger

**Purpose.** This is the durable, repository-native record of Research Review Board runs:
what was run, on which repository state, by which reviewers, and which outputs were produced,
identified by hash. It is a provenance record, **not** a transcript archive. Transcripts and
packages live in the local, gitignored `review_board_archive/` (ADR-021).

**Authority.** This ledger records that a run happened and what it produced. It does not make
any Board finding canonical. Board output remains advisory and non-canonical (ADR-019) until a
finding is separately approved for recording in a source-of-truth document.

## Rules

1. **An entry must exist before** any Board finding is used as supporting evidence in a
   canonical repository document: an ADR, `PHASE_LOG`, `PROJECT_STATUS`, a research plan,
   lessons, or other source-of-truth documentation (`CLAUDE.md` §4a). The citing document
   names the entry by its heading.
2. **Entries are added only with the researcher's approval** (SKILL.md §9 and §10). The
   ledger is append-only. Correct an entry by appending a correction, never by rewriting it
   (`CLAUDE.md` §4b).
3. **No transcript content** goes into an entry: no reviewer text, quotations, findings or
   reasoning. Hashes, identifiers and status only.
4. **Each entry is generated, not hand-typed:** it starts from the package's
   `provenance_entry.md`, written by `scripts/_export_review_board.py`. The hashes in it
   must match the package.
5. A package lives only on the researcher's machine. If it is lost, the entry still records
   what existed and its hashes, and the entry must not then be cited as re-checkable.

## Entry format

```
### <YYYY-MM-DD> - <label>
- Kind: live | historical (+ status note)
- Question: <one line>
- Repository HEAD at run: <full SHA>
- Roster source: roster file | fallback | reconstructed
- Reviewers: one line each - <agent id> - <perspective> - type <agent type>, enforcement <tool|instruction-only> - OK|MISSING
- Isolation verification: <parent's audit result>
- Package: review_board_archive/<path> (local, untracked)
- SHA256SUMS.txt: <sha256> (<n> files)
- Key artifacts (sha256): roster, manifest, secret-scan report, brief, report, each reviewer final report
- Secret scan: <n> findings (best-effort)
- Limitations: <as recorded>
```

## Entries

### 2026-11-16 - vagdhenu_lyrics_track

- **Kind:** live
- **Question:** Should the Vagdhenu lyrics-recognition track (RQ-LING-001) be included in Swaragam?
- **Repository HEAD at run:** `7204084ea6911b95841dfc0b267222c8eb342742`
- **Roster source:** roster file
- **Reviewers:**
  - `a2bb6f7604d8b8c80` - Source and claims auditor - type `board-reviewer`, enforcement `tool` - OK
  - `aaa69fbe088ce6ba5` - Governance, scope and mission fit - type `board-reviewer`, enforcement `tool` - OK
  - `ac78772db8a62b016` - Evaluation methodology, leakage and circularity - type `board-reviewer`, enforcement `tool` - OK
  - `a5295495261329d10` - Data feasibility, provenance and licensing - type `board-reviewer`, enforcement `tool` - OK
  - `a937bc4f732853477` - Advocate: strongest case for, smallest valid version - type `board-reviewer`, enforcement `tool` - OK
  - `a244bebe5d0785606` - Challenger: opportunity cost, technical feasibility, alternatives - type `board-reviewer`, enforcement `tool` - OK
- **Isolation verification:** NOT AUDITED by the parent: reviewer transcript files were empty and access to session logs was denied; isolation rests on tool restriction only
- **Package:** `review_board_archive/2026-11-16/vagdhenu_lyrics_track_2108` (local, untracked)
- **SHA256SUMS.txt:** `e2a21fb767443cc6b5de771310c816229bd96b7b9dcda8f3d6345be7e699bb3d` (26 files)
- **Key artifacts (sha256):**
  - `roster.json`: `71de3674140edd6cc8339224bab8824fcf54a6d7ef72ced996ef8e983cc2cc0d`
  - `manifest.json`: `149c63006a0f21d35a106d9290a2092706770b6c4c19fb0105720eb161aa271d`
  - `secret_scan_report.json`: `b657ce1d3f181633d70d164146bc1ee6f3e5e9a4319336e66e87475a649830f0`
  - `brief_review_board_brief_20261116_2019.md`: `8658e0bdebfb581ac7a4e445f7c26becbdd8c2fac5549dd1203ea8b5d01ab3df`
  - `report_review_board_report_20261116_2019.md`: `5c8bbfb6a3703eb9b12a0f0d8e6c8efd55dc5a06238fb15e1710bd078a977028`
  - `reviewer_reports/1_Source_and_claims_auditor.md`: `ac528e698036f3a98fea30c22b8e27b345cd856aa5a3108728d8d80ce36ebb13`
  - `reviewer_reports/2_Governance_scope_and_mission_fit.md`: `edc1c3a919aea700f1dfa8a740c2faf42cf69375f76d775a9e3e9be1dbdafb79`
  - `reviewer_reports/3_Evaluation_methodology_leakage_and_circularity.md`: `9b299636819cab93309840272cc67c1676dec9b43bf7ef35539f6edbdf2164ba`
  - `reviewer_reports/4_Data_feasibility_provenance_and_licensing.md`: `6f5c0cebbf3fc8bf62e1ee8830a73d3b48b84b25842c5a3f250621eacfa25f06`
  - `reviewer_reports/5_Advocate_strongest_case_for_smallest_valid_version.md`: `bc13a9f27d76813d2a2372f80d5b716f77c68e18790bf1e733f0e3639cdbe14b`
  - `reviewer_reports/6_Challenger_opportunity_cost_technical_feasibility_alternativ.md`: `7345210d7c6f1bd4b5e9ae973ad49f0cc12fd9827f66ff592ecc3f17e68e31a7`
- **Secret scan:** 0 findings (best-effort)
- **Limitations:** none recorded
- **Addendum (2026-11-16, appended after the package was built):**
  - **Isolation check:** the researcher searched the six minimized reviewer transcripts (`.md` and `.jsonl`) for `.claude/projects` and `review_board_archive`. Each file has exactly one matching line: line 49 of the brief as read by the reviewer, the constraint text "Do not read `~/.claude/projects/` or `review_board_archive/`". No tool call naming either path was found. Limits: two string patterns only; Grep and Glob coverage is best-effort (ADR-020, ADR-021). The "Isolation verification" line above is unchanged.
  - **Limitations:** reviewers had Read, Grep and Glob only, with no web access. External checks were made by the parent through fetched pages summarised by a model. Mesaros 2010, Gao 2022, Chitra 2019, Natesan and Beigi 2025 and IndicF5's stated figures were not verified. The report in the package is a compact version; the full Board report exists only in the session chat.

Historical runs are **not** backfilled: the 2026-10-12 Q-003 Research Council, the 2026-10-12
Review Board smoke-test and runtime-validation runs, and the 2026-10-13 Q-003 Review Board.
Packages derived from the migrated exports exist in `review_board_archive/`. Entering them
here is a separate decision for the researcher. ADR-019, ADR-020 and L-055 cite "session
records outside the repository"; until those runs are entered here, that citation gap remains.
