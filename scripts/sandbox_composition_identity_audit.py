"""
Composition-identity audit of the canonical LOO population (read-only, descriptive).

STATUS: approved by the researcher on 2026-11-16 after a Research Review Board run
(see the session record; Board output is advisory and not canonical). Not a research
gate: no hypothesis, no significance test, no change to any baseline.

PURPOSE
  Establish, for each clip in the 70-clip canonical LOO population, what the repo can
  support about composition identity, and whether the stored raga label agrees with
  the Saraga metadata record that clip appears to come from. This answers the open
  items "which of the 70 clips carry a recoverable composition identity" and "how many
  distinct compositions per raga" (Phrase Evaluation Protocol, section on composition
  independence; ADR-018). It also tests L-040 for the Saraga-matched clips.

PRE-REGISTERED DESIGN (fixed before the full-population run)
  1. Population: replicate `load_clips()` of sandbox_loo_v131_canonical.py (that file
     runs at import time and cannot be imported): feature_version == "v1.2",
     gating_ratio >= 0.05, len(cents_gated) >= 200; then keep ragas with >= 5 clips
     (MIN_CLIPS = 5). Sanity check, reported not asserted: 70 clips and the per-raga
     counts in PROJECT_STATUS.md (10, 8, 9, 14, 11, 7, 11).
  2. Saraga record lookup: the same normalised-title rule as provenance_for() in
     sandbox_q003_bhairavi_pcd_diagnostic.py, over datasets/staging_metadata/*.json.
     A title match is INFERENCE (CLAUDE.md section 6: not provenance by itself).
  3. Corroboration (reproducible measurement): locate the clip's audio file under
     datasets/seed_carnatic (excluding `excluded/`), read its duration with soundfile,
     and compare with the Saraga `length` (ms). Report the signed difference in
     seconds for every clip. A clip is flagged "duration-corroborated" when
     |difference| <= 0.5 s. The 0.5 s tolerance is a descriptive flag, chosen before
     the full run (the single case examined beforehand differed by 0.01 s); it is
     not a decision threshold and no verdict depends on it.
  4. Label comparison: strip diacritics, lowercase, compare the stored raga with the
     Saraga `raaga` name. Three known spelling variants are treated as the same raga
     (todi=thodi, kambhoji=kamboji, sankarabharanam=shankarabharanam). Every other
     difference is reported as DISAGREE and is not resolved here.
  5. Composition identity is reported as: Saraga `work` mbid and title where a record
     is matched; otherwise NOT ESTABLISHED. Varnam-dataset clips (file names
     `22xxxx__gopalkoduri__...`) are labelled as such; their composition is NOT
     ESTABLISHED by this script (notation titles are empty or in .doc files, see
     .ai-memory/datasets.md). Nothing is inferred from file names beyond the title
     rule in item 2.
  6. Output per raga: clips, clips with an identity, distinct identified work mbids,
     clips without identity. These are LOWER BOUNDS on identity coverage, not counts
     of independent compositional units.
  7. Output: timestamped run directory under "Composition identity audit results/"
     (git-ignored). Nothing else is written. No dataset, cache or canonical file is
     modified.

NOT DONE HERE: no accuracy is computed, no LOO is re-run, no label is changed.
Run:  my_virtual_env_swarag\\Scripts\\python.exe scripts\\sandbox_composition_identity_audit.py
"""
import csv
import glob
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import soundfile as sf

BASE_DIR = r"D:\Swaragam"
FEAT_DIR = os.path.join(BASE_DIR, "pcd_results", "features_v12")
META_DIR = os.path.join(BASE_DIR, "datasets", "staging_metadata")
AUDIO_DIR = os.path.join(BASE_DIR, "datasets", "seed_carnatic")
RESULTS_ROOT = os.path.join(BASE_DIR, "Composition identity audit results")

MIN_CLIPS = 5
TOLERANCE_S = 0.5
ALIASES = {"todi": "thodi", "kambhoji": "kamboji", "sankarabharanam": "shankarabharanam"}
EXPECTED_COUNTS = {"mohanam": 10, "saveri": 8, "shankarabharanam": 9, "kalyani": 14,
                   "thodi": 11, "abhogi": 7, "bhairavi": 11}

_ISO_RE = re.compile(r"\.(demucs-vocal|vocal-s|vocal|mix)$")
_TS_RE = re.compile(r"\d{8}_\d{6}")
_VARNAM_RE = re.compile(r"^\d{6}__gopalkoduri__")


def _plain(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def _canon_raga(s):
    p = _plain(s)
    return ALIASES.get(p, p)


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def _clip_base(npz_name):
    stem = os.path.splitext(npz_name)[0]
    parts = stem.rsplit("_", 2)
    if len(parts) == 3 and _TS_RE.fullmatch("_".join(parts[1:])):
        return parts[0]
    return stem


def load_population():
    clips = []
    for fname in sorted(os.listdir(FEAT_DIR)):
        if not fname.endswith(".npz"):
            continue
        d = np.load(os.path.join(FEAT_DIR, fname), allow_pickle=True)
        if "feature_version" not in d or str(d["feature_version"]) != "v1.2":
            continue
        if float(d["gating_ratio"]) < 0.05:
            continue
        if len(d["cents_gated"]) < 200:
            continue
        clips.append({"fname": fname, "raga": str(d["raga"]), "sa_hz": float(d["sa_hz"])})
    counts = Counter(c["raga"] for c in clips)
    eligible = {r for r, n in counts.items() if n >= MIN_CLIPS}
    return [c for c in clips if c["raga"] in eligible]


def saraga_index():
    idx = {}
    for path in glob.glob(os.path.join(META_DIR, "*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        works = d.get("work") or []
        rec = dict(
            work_mbid=(works[0].get("mbid") if works else None),
            work_title=(works[0].get("title") if works else None),
            recording_title=d.get("title"),
            raaga=[r.get("name") for r in d.get("raaga", [])],
            length_s=(d.get("length") / 1000.0 if d.get("length") else None),
            source_file=os.path.basename(path))
        for key in filter(None, [d.get("title"), os.path.splitext(os.path.basename(path))[0]]):
            idx[_norm(key)] = rec
    return idx


def lookup(base, idx):
    stripped = _ISO_RE.sub("", base)
    hit = idx.get(_norm(stripped))
    how = "exact-title"
    if hit is None:
        cand = [v for k, v in idx.items() if _norm(stripped) and _norm(stripped) in k]
        hit = cand[0] if len(cand) == 1 else None
        how = "unique-substring" if hit else "none"
    return hit, how


def audio_index():
    out = defaultdict(list)
    for root, dirs, files in os.walk(AUDIO_DIR):
        dirs[:] = [d for d in dirs if d.lower() != "excluded"]
        for f in files:
            stem, ext = os.path.splitext(f)
            if ext.lower() in (".mp3", ".wav", ".flac"):
                out[stem].append(os.path.join(root, f))
    return out


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=BASE_DIR, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "NOT ESTABLISHED"


def main():
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(RESULTS_ROOT, f"run_{ts}")
    os.makedirs(run_dir, exist_ok=False)

    clips = load_population()
    counts = Counter(_canon_raga(c["raga"]) for c in clips)
    idx = saraga_index()
    audio = audio_index()

    rows = []
    for c in clips:
        base = _clip_base(c["fname"])
        is_varnam = bool(_VARNAM_RE.match(base))
        hit, how = lookup(base, idx)
        paths = audio.get(base, [])
        dur = None
        if len(paths) == 1:
            try:
                dur = sf.info(paths[0]).duration
            except Exception:
                dur = None
        diff = (dur - hit["length_s"]) if (hit and dur is not None and hit["length_s"]) else None
        label = _canon_raga(c["raga"])
        saraga_ragas = [_canon_raga(r) for r in hit["raaga"]] if hit else []
        rows.append(dict(
            clip=c["fname"], label=label,
            source_class=("varnam-dataset" if is_varnam else "other"),
            saraga_match=how, saraga_record=(hit["source_file"] if hit else ""),
            work_mbid=(hit["work_mbid"] if hit else ""),
            work_title=(hit["work_title"] if hit else ""),
            saraga_raga=("|".join(saraga_ragas) if hit else ""),
            label_vs_saraga=("n/a" if not hit else ("agree" if label in saraga_ragas else "DISAGREE")),
            audio_files_found=len(paths),
            audio_duration_s=("" if dur is None else round(dur, 3)),
            saraga_length_s=("" if not hit else round(hit["length_s"], 3)),
            duration_diff_s=("" if diff is None else round(diff, 3)),
            duration_corroborated=("" if diff is None else ("yes" if abs(diff) <= TOLERANCE_S else "no")),
            identity=("work mbid via Saraga title match (INFERENCE)" if hit and hit["work_mbid"]
                      else ("NOT ESTABLISHED")),
            sa_hz=round(c["sa_hz"], 3)))

    # per-raga summary
    summary = {}
    for r in sorted(counts):
        rr = [x for x in rows if x["label"] == r]
        ident = [x for x in rr if x["identity"] != "NOT ESTABLISHED"]
        summary[r] = dict(
            clips=len(rr), clips_with_identity=len(ident),
            distinct_work_mbids_identified=len({x["work_mbid"] for x in ident}),
            clips_without_identity=len(rr) - len(ident),
            varnam_dataset_clips=sum(1 for x in rr if x["source_class"] == "varnam-dataset"),
            saraga_matched=sum(1 for x in rr if x["saraga_match"] != "none"),
            label_agree=sum(1 for x in rr if x["label_vs_saraga"] == "agree"),
            label_disagree=sum(1 for x in rr if x["label_vs_saraga"] == "DISAGREE"),
            duration_corroborated=sum(1 for x in rr if x["duration_corroborated"] == "yes"))

    sanity = {r: (counts.get(r, 0), n) for r, n in EXPECTED_COUNTS.items()}
    meta = dict(timestamp=ts, git_commit=git_commit(), python=sys.version.split()[0],
                numpy=np.__version__, soundfile=sf.__version__,
                population=len(rows), expected_population=70,
                per_raga_count_vs_expected=sanity,
                tolerance_s=TOLERANCE_S, aliases=ALIASES,
                script=os.path.basename(__file__))
    with open(os.path.join(run_dir, "per_clip.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(run_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(meta=meta, per_raga=summary), fh, indent=2, ensure_ascii=True)

    print("run dir:", run_dir)
    print("population:", len(rows), "(expected 70);", "per-raga (got, expected):", sanity)
    for r, s in summary.items():
        print(r, s)
    print("DISAGREE rows:")
    for x in rows:
        if x["label_vs_saraga"] == "DISAGREE":
            print("  ", x["clip"].encode("ascii", "replace").decode(), "| label", x["label"],
                  "| saraga", x["saraga_raga"], "| dur diff", x["duration_diff_s"])


if __name__ == "__main__":
    main()
