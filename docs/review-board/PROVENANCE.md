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

None yet.

Historical runs are **not** backfilled: the 2026-10-12 Q-003 Research Council, the 2026-10-12
Review Board smoke-test and runtime-validation runs, and the 2026-10-13 Q-003 Review Board.
Packages derived from the migrated exports exist in `review_board_archive/`. Entering them
here is a separate decision for the researcher. ADR-019, ADR-020 and L-055 cite "session
records outside the repository"; until those runs are entered here, that citation gap remains.
