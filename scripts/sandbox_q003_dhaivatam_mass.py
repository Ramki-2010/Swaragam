#!/usr/bin/env python3
"""
Q-003 DHAIVATAM D1-vs-D2 MASS CHECK (Bhairavi vs Saveri, Thodi)

DIAGNOSTIC ONLY. Read-only against the feature cache. No production script,
dataset, cache, weight or threshold is modified. No clip is added or removed.
Not a Phase 1-D execution; authorises no further phase (CLAUDE.md 17a).

HYPOTHESIS (unverified; premise comes from an external report, not the repo):
  Bhairavi PCD mass in the dhaivatam region(s) differs from Saveri's and
  Thodi's in a way that separates the ragas.

PRE-REGISTRATION -- fixed here BEFORE any PCD value was inspected:
  Population : features_v12, same filters as confusion_matrix_audit.load_clips
               (v1.2, gating_ratio >= 0.05, >= 200 cents_gated frames).
               Expected n: Bhairavi 11, Saveri 8, Thodi 11 (asserted).
  PCD        : 72-bin, octave-folded, Sa-relative, 16.667 c/bin.
  Windows    : D1 = 770-830 c, D2 = 870-930 c. A bin is in a window iff its
               centre (i + 0.5) * 1200 / 72 lies in [lo, hi]. This resolves to
               D1 = bins 46-49, D2 = bins 52-55 (asserted). The windows are the
               author's proposal approved by the user, NOT repo-sourced and NOT
               taken from sandbox_absent_swara_v2.py (its swara table is
               unreliable).
  Per clip   : D1 = sum PCD[D1 bins]; D2 = sum PCD[D2 bins];
               R = D2 / (D1 + D2).
  Precondition (Sa soundness): per clip, PCD mass in the Sa window (bins
               70, 71, 0, 1 = +-33 c) ranks within the top 3 of the 18
               non-overlapping 4-bin windows starting at bins 2 + 4k (k = 0..17,
               modulo 72), one of which is the Sa window. Pass iff >= 80% of clips pass in Bhairavi AND in each
               comparator. sa_hz spread is reported. The 80% / top-3 rule is a
               proposal fixed before data. If it fails: STOP, no test is run.
  Test       : Mann-Whitney U, two-sided, exact permutation p (own
               implementation; scipy.stats is not importable in the 3.14 env), Bhairavi vs Saveri and vs Thodi, on
               R (primary) and on D1, D2 separately (descriptive).
               Effect size rank-biserial r = 2U/(n1*n2) - 1, U for Bhairavi;
               r > 0 means Bhairavi values tend to be HIGHER.
  Criterion  : diagnostic only. "Consistent separation" iff |r| >= 0.5 in the
               SAME direction against BOTH Saveri and Thodi on R. Otherwise
               INCONCLUSIVE. |r| >= 0.5 is a pre-registered diagnostic
               threshold, not proof of separation.

INTERPRETATION LIMITS: a positive result establishes a distributional
difference only, not a cause of Bhairavi's recognition failures. A null result
does not prove absence at n = 8-11. ADR-005 is unaffected. No promotion.

    python sandbox_q003_dhaivatam_mass.py
"""

import os
import sys
import csv
import json
import hashlib
import platform
import subprocess
from datetime import datetime

import numpy as np
import scipy
import itertools

from recognize_raga_v12 import N_BINS, EPS

BASE_DIR     = r"D:\Swaragam"
FEAT_DIR     = os.path.join(BASE_DIR, "pcd_results", "features_v12")
RESULTS_ROOT = os.path.join(BASE_DIR, "Q003 Bhairavi Diagnosis results")

TARGET      = "Bhairavi"
COMPARATORS = ["Saveri", "Thodi"]
EXPECTED_N  = {"Bhairavi": 11, "Saveri": 8, "Thodi": 11}

D1_WINDOW = (770.0, 830.0)
D2_WINDOW = (870.0, 930.0)
EXPECTED_D1_BINS = [46, 47, 48, 49]
EXPECTED_D2_BINS = [52, 53, 54, 55]

SA_BINS          = [70, 71, 0, 1]
SA_RANK_TOP      = 3
SA_PASS_FRACTION = 0.80
R_THRESHOLD      = 0.5


def window_bins(lo, hi):
    return [i for i in range(N_BINS) if lo <= (i + 0.5) * 1200.0 / N_BINS <= hi]


D1_BINS = window_bins(*D1_WINDOW)
D2_BINS = window_bins(*D2_WINDOW)
assert D1_BINS == EXPECTED_D1_BINS, D1_BINS
assert D2_BINS == EXPECTED_D2_BINS, D2_BINS
assert N_BINS == 72


def load_clips():
    """Same filters as confusion_matrix_audit.load_clips (not imported: that
    module imports aggregate_all_v12, which creates an empty run directory at
    import time)."""
    clips = []
    for fname in sorted(os.listdir(FEAT_DIR)):
        if not fname.endswith(".npz"):
            continue
        d = np.load(os.path.join(FEAT_DIR, fname), allow_pickle=True)
        if "feature_version" not in d or str(d["feature_version"]) != "v1.2":
            continue
        if float(d["gating_ratio"]) < 0.05:
            continue
        cents = d["cents_gated"]
        if len(cents) < 200:
            continue
        clips.append({"fname": fname, "raga": str(d["raga"]),
                      "cents": cents, "sa_hz": float(d["sa_hz"])})
    return clips


def pcd_of(cents):
    hist, _ = np.histogram(cents, bins=N_BINS, range=(0, 1200))
    return hist / (np.sum(hist) + EPS)


def sa_window_rank(pcd):
    """Rank (1 = largest) of the Sa window among 18 non-overlapping 4-bin
    windows whose starts are 2 + 4k (so one window is {70,71,0,1})."""
    masses = []
    for k in range(18):
        idx = [(2 + 4 * k + j) % N_BINS for j in range(4)]
        masses.append((float(pcd[idx].sum()), tuple(sorted(idx))))
    sa_key = tuple(sorted(SA_BINS))
    sa_mass = next(m for m, key in masses if key == sa_key)
    return 1 + sum(1 for m, _ in masses if m > sa_mass)


def _midranks(v):
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(len(v))
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def rank_biserial(x, y):
    """Exact two-sided Mann-Whitney U (permutation of midranks) and
    rank-biserial r. Implemented here, not via scipy.stats, because
    scipy.stats cannot be imported in the Python 3.14 environment (Windows
    Application Control blocks scipy.sparse.csgraph._min_spanning_tree).
    Exact enumeration is feasible at n = 8-11 (<= C(22,11) = 705432)."""
    v = np.asarray(list(x) + list(y), dtype=float)
    n1, n2 = len(x), len(y)
    ranks = _midranks(v)
    u_obs = ranks[:n1].sum() - n1 * (n1 + 1) / 2.0
    mu = n1 * n2 / 2.0
    combos = np.array(list(itertools.combinations(range(n1 + n2), n1)))
    u_all = ranks[combos].sum(axis=1) - n1 * (n1 + 1) / 2.0
    p = float(np.mean(np.abs(u_all - mu) >= abs(u_obs - mu) - 1e-9))
    return float(u_obs), p, 2.0 * float(u_obs) / (n1 * n2) - 1.0


def git(*args):
    return subprocess.run(["git", "-C", BASE_DIR, *args],
                          capture_output=True, text=True).stdout.strip()


def dist(v):
    v = np.asarray(v, dtype=float)
    return dict(n=len(v), min=float(v.min()), median=float(np.median(v)),
                max=float(v.max()), mean=float(v.mean()))


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(RESULTS_ROOT, f"dhaivatam_mass_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    clips = load_clips()
    ragas = [TARGET] + COMPARATORS
    by = {r: [c for c in clips if c["raga"] == r] for r in ragas}
    counts = {r: len(by[r]) for r in ragas}
    print("Population:", counts, "| all clips:", len(clips))
    assert counts == EXPECTED_N, f"population mismatch: {counts}"

    rows = []
    for r in ragas:
        for c in by[r]:
            pcd = pcd_of(c["cents"])
            d1 = float(pcd[D1_BINS].sum())
            d2 = float(pcd[D2_BINS].sum())
            ratio = d2 / (d1 + d2) if (d1 + d2) > 0 else float("nan")
            rank = sa_window_rank(pcd)
            rows.append(dict(raga=r, fname=c["fname"], sa_hz=c["sa_hz"],
                             sa_window_mass=float(pcd[SA_BINS].sum()),
                             sa_rank=rank, sa_ok=rank <= SA_RANK_TOP,
                             D1=d1, D2=d2, R=ratio))
    with open(os.path.join(out_dir, "per_clip.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- precondition (computed from Sa-window mass only) ----
    lines = []
    pre = {}
    for r in ragas:
        rr = [x for x in rows if x["raga"] == r]
        frac = sum(x["sa_ok"] for x in rr) / len(rr)
        sa = [x["sa_hz"] for x in rr]
        pre[r] = dict(sa_ok_fraction=frac, n=len(rr),
                      sa_hz_min=min(sa), sa_hz_median=float(np.median(sa)),
                      sa_hz_max=max(sa))
        lines.append(f"PRECONDITION {r}: Sa-window rank<=top{SA_RANK_TOP} "
                     f"{frac:.2f} ({sum(x['sa_ok'] for x in rr)}/{len(rr)}); "
                     f"sa_hz min/med/max = {min(sa):.1f}/"
                     f"{float(np.median(sa)):.1f}/{max(sa):.1f}")
    precondition_pass = all(pre[r]["sa_ok_fraction"] >= SA_PASS_FRACTION
                            for r in ragas)
    lines.append(f"PRECONDITION RESULT: {'PASS' if precondition_pass else 'FAIL'}"
                 f" (needs >= {SA_PASS_FRACTION:.2f} in every raga)")

    tests = {}
    verdict = "NOT RUN (precondition failed)"
    if precondition_pass:
        for metric in ("R", "D1", "D2"):
            for comp in COMPARATORS:
                x = [q[metric] for q in rows if q["raga"] == TARGET]
                y = [q[metric] for q in rows if q["raga"] == comp]
                assert not any(np.isnan(x + y)), "NaN ratio; report, do not mask"
                U, p, r = rank_biserial(x, y)
                tests[f"{metric}:{TARGET}_vs_{comp}"] = dict(U=U, p=p, r=r)
                lines.append(f"TEST {metric} {TARGET} vs {comp}: U={U:.1f} "
                             f"p={p:.4f} r={r:+.3f}")
        rs = [tests[f"R:{TARGET}_vs_{c}"]["r"] for c in COMPARATORS]
        same_dir = all(v > 0 for v in rs) or all(v < 0 for v in rs)
        strong = all(abs(v) >= R_THRESHOLD for v in rs)
        verdict = ("CONSISTENT SEPARATION (diagnostic)" if same_dir and strong
                   else "INCONCLUSIVE")
    lines.append(f"VERDICT (R, pre-registered criterion): {verdict}")

    dists = {r: {m: dist([q[m] for q in rows if q["raga"] == r])
                 for m in ("D1", "D2", "R")} for r in ragas}
    for r in ragas:
        for m in ("D1", "D2", "R"):
            d = dists[r][m]
            lines.append(f"DIST {r} {m}: n={d['n']} min={d['min']:.4f} "
                         f"med={d['median']:.4f} max={d['max']:.4f} "
                         f"mean={d['mean']:.4f}")
    lines += ["", "Limits: positive = distributional difference only, not a "
              "cause of Bhairavi failures; null != absence at n=8-11; "
              "ADR-005 unaffected; no phase advance."]
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(out_dir, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")

    with open(__file__, "rb") as f:
        script_sha = hashlib.sha1(f.read()).hexdigest()
    record = dict(
        timestamp=ts, git_commit=git("rev-parse", "HEAD"),
        git_branch=git("branch", "--show-current"), script_sha1=script_sha,
        python=sys.version.split()[0], numpy=np.__version__,
        scipy=scipy.__version__, platform=platform.platform(),
        feature_dir=FEAT_DIR, feature_version="v1.2", n=counts,
        d1_window=D1_WINDOW, d2_window=D2_WINDOW,
        d1_bins=D1_BINS, d2_bins=D2_BINS, sa_bins=SA_BINS,
        sa_rank_top=SA_RANK_TOP, sa_pass_fraction=SA_PASS_FRACTION,
        r_threshold=R_THRESHOLD, precondition=pre,
        precondition_pass=precondition_pass, tests=tests, verdict=verdict,
        distributions=dists)
    with open(os.path.join(out_dir, "run_record.json"), "w",
              encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    print("Saved to:", out_dir)


if __name__ == "__main__":
    main()
