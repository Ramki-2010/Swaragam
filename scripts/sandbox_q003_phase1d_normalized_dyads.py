"""
Q-003 PHASE 1-D  --  MODEL-NORM DYAD SCORING AT MATCHED INFLUENCE (Bhairavi)
========================================================================

Pre-registration: docs/research/Q-003/RESEARCH_PLAN.md, section "Phase 1-D"
(design audit and Correction C-8 in docs/research/Q-003/PHASE_LOG.md).
Authorised by the researcher in session on 2026-11-19 ("Commence phase 1-D").

QUESTION
    Does normalised dyad similarity materially change RECOGNITION -- not
    channel rank -- when its influence on the score is held constant?

CONDITIONS (all LOO, 7 ragas, 70 clips; PCD channel identical in all four)
    C0  PCD ONLY      DYAD_WEIGHT = 0 (PCD_WEIGHT unchanged)     effect ceiling
    C1  BASELINE      0.5*(x_up.m_up + x_dn.m_dn), weight 0.2    must reproduce 25c/14w/31u
    C2  MODEL-NORM, MATCHED   gamma * 0.5*(x_up.m_up/|m_up| + x_dn.m_dn/|m_dn|), weight 0.2
                      PRIMARY TEST.  Model-norm only (audit F1): NOT full cosine.
    C3  MODEL-NORM, NAIVE     same as C2 with gamma = 1          CONTROL ONLY, never a
                      promotion candidate (reproduces the dyad-heavy config of L-017).

    gamma = mean_f[S_raw(f)] / mean_f[S_nrm(f)], S = std over the 7 candidate
    ragas of the dyad similarity in fold f.  It is computed from all 70 folds
    BEFORE any accuracy is computed.  Pre-registered sensitivity variants,
    reported and not separate conditions: per-fold gamma(f) = S_raw(f)/S_nrm(f),
    and the same global matching using (max - min) instead of std.

    Audit F4 (match on top1-top2 gap) is "recommended", not pre-registered as a
    variant; it is deliberately NOT run here, because adding it after the
    fact would be a post-hoc choice.

STOP CONDITIONS (plan section "Stop conditions"), all enforced below
    1. C1 does not reproduce the canonical baseline.
    2. Raw-count replication fails on any clip.
    3. C2 dyad leader counts do not reproduce Phase 1-C's published
       (Bhairavi 8/11 Thodi 5/11 Kalyani 9/14 Saveri 5/8 Shankarabharanam 4/9
        Mohanam 3/10 Abhogi 1/7).
    4. S_nrm(f) degenerate (non-finite or exactly zero) in any fold.  The plan
       gives no numeric threshold for "approximately zero"; this script uses
       only the numerical-degeneracy test and reports min(S_nrm) so a human can
       judge anything short of it.
    5. Any tracked file, or the feature cache listing, changes during the run.
    6. Report and stop: no promotion, no production edit.

NOT DONE HERE: no significance test (none is available at n = 11), no
production or dataset change, no sampling (LOO is exhaustive; no seed).
ADR-005 forecloses production promotion regardless of outcome.

KNOWN LIMITATIONS (carried forward)
    - 6 of 11 Bhairavi clips (Bhairavi_clean_1..6) have no recoverable
      composition, performer or source identity.
    - One Mohanam-labelled clip (Brochevarevarura) matches a Saraga record whose
      raga is kamas (composition-identity audit 2026-11-16); unresolved and
      left as labelled, because relabelling is a methodology change.
    - n = 11: a change of 1-3 clips is not statistically meaningful.
"""

import os
import io
import csv
import json
import time
import hashlib
import subprocess
import contextlib
from collections import defaultdict, Counter

import numpy as np

# --- canonical constants, imported (never re-declared) -- ADR-015, audit F2 --
from recognize_raga_v12 import (
    N_BINS, EPS, PCD_WEIGHT, DYAD_WEIGHT, MARGIN_STRICT, MIN_MARGIN_FINAL,
    MIN_STABLE_FRAMES,
)

with contextlib.redirect_stdout(io.StringIO()):
    from confusion_matrix_audit import (
        load_clips, compute_features, idf_var_weights, MIN_CLIPS, ALPHA,
    )

from sandbox_q003_bhairavi_pcd_diagnostic import (
    BASE_DIR, RESULTS_ROOT, TARGET, _versions, _git_commit,
)

FEAT_DIR = os.path.join(BASE_DIR, "pcd_results", "features_v12")

# Canonical baseline (evaluation-protocol.md section 7b) -- stop condition 1.
CANON = dict(total=70, correct=25, wrong=14, unknown=31,
             bhairavi=dict(clips=11, c=1, w=6, u=4),
             bhairavi_confusers={"Saveri": 4, "Thodi": 2})

# Phase 1-C published dyad-leader counts (true raga ranked #1 by the
# L2-normalised dyad channel) -- stop condition 3.  PHASE_1C values quoted in
# RESEARCH_PLAN.md "Free correctness check".
PHASE1C_COSINE_FIRST = {"Bhairavi": (8, 11), "Thodi": (5, 11), "Kalyani": (9, 14),
                        "Saveri": (5, 8), "Shankarabharanam": (4, 9),
                        "Mohanam": (3, 10), "Abhogi": (1, 7)}

CONDITIONS = ["C0", "C1", "C2", "C3"]
SENSITIVITY = ["C2_perfold", "C2_range"]      # reported, not separate conditions


class Stop(SystemExit):
    pass


def stop(n, msg):
    raise Stop("STOP CONDITION %d: %s" % (n, msg))


# =========================================================================
# Guards: git state and feature-cache fingerprint (stop condition 5)
# =========================================================================
def git_porcelain():
    out = subprocess.run(["git", "-C", BASE_DIR, "status", "--porcelain"],
                         capture_output=True, text=True)
    return [l for l in out.stdout.splitlines() if l.strip()]


def feature_fingerprint():
    h = hashlib.sha256()
    n = 0
    for f in sorted(os.listdir(FEAT_DIR)):
        st = os.stat(os.path.join(FEAT_DIR, f))
        h.update(("%s|%d|%d\n" % (f, st.st_size, st.st_mtime_ns)).encode())
        n += 1
    return h.hexdigest(), n


# =========================================================================
# Raw dyads (replication check, stop condition 2).  Uses the IMPORTED
# MIN_STABLE_FRAMES (audit F2).  Mirrors aggregate_all_v12.py / the Phase 1-C
# raw_dyads exactly; returns counts before `+= ALPHA`.
# =========================================================================
def raw_dyads(cents):
    edges = np.linspace(0, 1200, N_BINS + 1)
    bins = np.digitize(cents, edges) - 1
    bins = bins[(bins >= 0) & (bins < N_BINS)]
    stable, cur, cnt = [], bins[0], 1
    for b in bins[1:]:
        if b == cur:
            cnt += 1
        else:
            if cnt >= MIN_STABLE_FRAMES:
                stable.append(cur)
            cur, cnt = b, 1
    if cnt >= MIN_STABLE_FRAMES:
        stable.append(cur)
    up = np.zeros((N_BINS, N_BINS))
    dn = np.zeros((N_BINS, N_BINS))
    for i in range(len(stable) - 1):
        a, b = stable[i], stable[i + 1]
        if b > a:
            up[a, b] += 1
        elif b < a:
            dn[a, b] += 1
    return up, dn


def smooth(raw):
    m = raw + ALPHA
    return (m / (np.sum(m) + EPS)).flatten()


def build_processed():
    with contextlib.redirect_stdout(io.StringIO()):
        all_clips = load_clips()
    counts = Counter(c["raga"] for c in all_clips)
    eligible = {r for r, n in counts.items() if n >= MIN_CLIPS}
    processed, bad = [], []
    for c in (x for x in all_clips if x["raga"] in eligible):
        pcd, up, down = compute_features(c["cents"])
        ru, rd = raw_dyads(c["cents"])
        if not (np.allclose(smooth(ru), up) and np.allclose(smooth(rd), down)):
            bad.append(c["fname"])
        processed.append({"fname": c["fname"], "raga": c["raga"],
                          "pcd": pcd, "up": up, "down": down})
    return processed, bad


# =========================================================================
# Pass 1: per-fold similarities.  Arithmetic mirrors
# confusion_matrix_audit.py:129-148 / recognize_raga_v12.py:210-216; only the
# model-norm variant is added.  No accuracy is computed here.
# =========================================================================
def fold_quantities(processed):
    folds = []
    for i, held in enumerate(processed):
        train = processed[:i] + processed[i + 1:]
        by_raga = defaultdict(list)
        for c in train:
            by_raga[c["raga"]].append(c)
        models = {r: {"pcd": np.mean([c["pcd"] for c in rc], axis=0),
                      "up": np.mean([c["up"] for c in rc], axis=0),
                      "down": np.mean([c["down"] for c in rc], axis=0)}
                  for r, rc in by_raga.items()}
        weights = idf_var_weights(models)
        pcd_w = held["pcd"] * weights
        pcd_w = pcd_w / (np.sum(pcd_w) + EPS)

        ragas = sorted(models)
        pcd_sim, d_raw, d_nrm = {}, {}, {}
        for r in ragas:
            m = models[r]
            mw = m["pcd"] * weights
            mw = mw / (np.sum(mw) + EPS)
            pcd_sim[r] = float(np.dot(pcd_w, mw))
            d_raw[r] = float(0.5 * (np.dot(held["up"], m["up"]) +
                                    np.dot(held["down"], m["down"])))
            nu = float(np.sqrt(np.dot(m["up"], m["up"])))
            nd = float(np.sqrt(np.dot(m["down"], m["down"])))
            d_nrm[r] = float(0.5 * (np.dot(held["up"], m["up"] / nu) +
                                    np.dot(held["down"], m["down"] / nd)))
        folds.append(dict(fname=held["fname"], true=held["raga"], ragas=ragas,
                          pcd=pcd_sim, raw=d_raw, nrm=d_nrm))
    return folds


def spread(d, kind):
    v = np.array(list(d.values()))
    return float(np.std(v)) if kind == "std" else float(v.max() - v.min())


def compute_gammas(folds):
    s_raw = np.array([spread(f["raw"], "std") for f in folds])
    s_nrm = np.array([spread(f["nrm"], "std") for f in folds])
    r_raw = np.array([spread(f["raw"], "rng") for f in folds])
    r_nrm = np.array([spread(f["nrm"], "rng") for f in folds])
    for arr in (s_nrm, r_nrm):
        if (not np.all(np.isfinite(arr))) or np.any(arr == 0.0):
            stop(4, "S_nrm degenerate in at least one fold (min=%r)" % arr.min())
    return dict(
        gamma=float(s_raw.mean() / s_nrm.mean()),
        gamma_range=float(r_raw.mean() / r_nrm.mean()),
        gamma_fold=[float(a / b) for a, b in zip(s_raw, s_nrm)],
        mean_S_raw=float(s_raw.mean()), mean_S_nrm=float(s_nrm.mean()),
        min_S_raw=float(s_raw.min()), min_S_nrm=float(s_nrm.min()),
        mean_range_raw=float(r_raw.mean()), mean_range_nrm=float(r_nrm.mean()),
        S_raw=[float(x) for x in s_raw], S_nrm=[float(x) for x in s_nrm],
    )


# =========================================================================
# Pass 2: score every condition.  The decision rule is production's.
# =========================================================================
def decide(scores, true):
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    margin = ranked[0][1] - ranked[1][1]
    if margin >= MARGIN_STRICT:
        tier, pred = "HIGH", ranked[0][0]
    elif margin >= MIN_MARGIN_FINAL:
        tier, pred = "MOD", ranked[0][0]
    else:
        tier, pred = "UNK", "UNKNOWN"
    outcome = ("correct" if pred == true
               else "unknown" if tier == "UNK" else "wrong")
    return float(margin), tier, pred, outcome


def rank_of(d, r):
    return sorted(d, key=lambda k: d[k], reverse=True).index(r) + 1


def run_conditions(folds, g):
    out = {k: [] for k in CONDITIONS + SENSITIVITY}
    for fi, f in enumerate(folds):
        raw, nrm, pcd = f["raw"], f["nrm"], f["pcd"]
        variants = {
            "C0": (None, 0.0),
            "C1": (raw, DYAD_WEIGHT),
            "C2": ({r: g["gamma"] * v for r, v in nrm.items()}, DYAD_WEIGHT),
            "C3": (nrm, DYAD_WEIGHT),
            "C2_perfold": ({r: g["gamma_fold"][fi] * v for r, v in nrm.items()},
                           DYAD_WEIGHT),
            "C2_range": ({r: g["gamma_range"] * v for r, v in nrm.items()},
                         DYAD_WEIGHT),
        }
        for cond, (dyad, w) in variants.items():
            scores = {r: PCD_WEIGHT * pcd[r] + (w * dyad[r] if dyad else 0.0)
                      for r in f["ragas"]}
            margin, tier, pred, outcome = decide(scores, f["true"])
            # dyad channel view: C0 has none; report the raw channel for it
            dview = dyad if dyad else raw
            out[cond].append(dict(
                fname=f["fname"], true=f["true"], cond=cond, margin=margin,
                tier=tier, pred=pred, outcome=outcome, scores=scores,
                dyad_vals=dview,
                dyad_rank=rank_of(dview, f["true"]),
                dyad_leader=max(dview, key=lambda k: dview[k]),
                pcd_rank=rank_of(pcd, f["true"])))
    return out


def tally(rows):
    st = defaultdict(lambda: {"t": 0, "c": 0, "w": 0, "u": 0})
    tot = {"c": 0, "w": 0, "u": 0}
    k = {"correct": "c", "wrong": "w", "unknown": "u"}
    for r in rows:
        st[r["true"]]["t"] += 1
        st[r["true"]][k[r["outcome"]]] += 1
        tot[k[r["outcome"]]] += 1
    return dict(st), tot


def spearman(a, b):
    def rk(x):
        order = np.argsort(x)
        r = np.empty(len(x))
        r[order] = np.arange(len(x))
        return r
    ra, rb = rk(np.asarray(a)), rk(np.asarray(b))
    ra, rb = ra - ra.mean(), rb - rb.mean()
    return float(np.dot(ra, rb) / np.sqrt(np.dot(ra, ra) * np.dot(rb, rb)))


# =========================================================================
def main():
    t0 = time.time()
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(RESULTS_ROOT, "run_%s_phase1d" % ts)

    print("=" * 74)
    print("Q-003 PHASE 1-D  --  MODEL-NORM DYADS AT MATCHED INFLUENCE")
    print("=" * 74)

    # --- pre-flight (CLAUDE.md section 10) --------------------------------
    commit = _git_commit()
    dirty = git_porcelain()
    if dirty:
        stop(5, "working tree not clean before run (script must be committed "
                "before execution): %s" % dirty[:5])
    fp0, n_feat = feature_fingerprint()
    print("commit: %s  clean tree: yes" % commit)
    print("feature cache: %d files, fingerprint %s" % (n_feat, fp0[:16]))
    print("constants imported: PCD_WEIGHT=%s DYAD_WEIGHT=%s MARGIN_STRICT=%s "
          "MIN_MARGIN_FINAL=%s MIN_STABLE_FRAMES=%s ALPHA=%s" %
          (PCD_WEIGHT, DYAD_WEIGHT, MARGIN_STRICT, MIN_MARGIN_FINAL,
           MIN_STABLE_FRAMES, ALPHA))

    processed, bad = build_processed()
    print("clips processed: %d" % len(processed))
    print("raw-count replication (np.allclose, all clips): %s" %
          ("PASS" if not bad else "FAIL %d" % len(bad)))
    if bad:
        stop(2, "raw-count replication failed on %s" % bad[:3])

    folds = fold_quantities(processed)
    g = compute_gammas(folds)            # BEFORE any accuracy
    print("\n--- SCALE CONTROL (computed before any accuracy) ---")
    print("  mean S_raw = %.8f   mean S_nrm = %.8f" %
          (g["mean_S_raw"], g["mean_S_nrm"]))
    print("  gamma (std, global)        = %.6f" % g["gamma"])
    print("  gamma (range, global)      = %.6f" % g["gamma_range"])
    print("  gamma per-fold: min %.4f  median %.4f  max %.4f" %
          (min(g["gamma_fold"]), float(np.median(g["gamma_fold"])),
           max(g["gamma_fold"])))
    print("  min S_raw = %.3e   min S_nrm = %.3e" %
          (g["min_S_raw"], g["min_S_nrm"]))

    res = run_conditions(folds, g)

    # --- stop 1: C1 baseline ---------------------------------------------
    st1, tot1 = tally(res["C1"])
    b = st1[TARGET]
    conf = Counter(r["pred"] for r in res["C1"]
                   if r["true"] == TARGET and r["outcome"] == "wrong")
    checks = [("total", len(res["C1"]), CANON["total"]),
              ("correct", tot1["c"], CANON["correct"]),
              ("wrong", tot1["w"], CANON["wrong"]),
              ("unknown", tot1["u"], CANON["unknown"]),
              ("Bhairavi clips", b["t"], CANON["bhairavi"]["clips"]),
              ("Bhairavi correct", b["c"], CANON["bhairavi"]["c"]),
              ("Bhairavi wrong", b["w"], CANON["bhairavi"]["w"]),
              ("Bhairavi unknown", b["u"], CANON["bhairavi"]["u"])]
    for k, v in CANON["bhairavi_confusers"].items():
        checks.append(("Bhairavi -> %s" % k, conf.get(k, 0), v))
    print("\n--- STOP 1: C1 vs CANONICAL BASELINE ---")
    ok1 = True
    for n, got, want in checks:
        ok1 &= (got == want)
        print("  %-18s got=%-4s want=%-4s %s" %
              (n, got, want, "OK" if got == want else "MISMATCH"))
    if not ok1:
        stop(1, "C1 does not reproduce the canonical baseline; nothing "
                "interpretive emitted")

    # --- stop 3: C2 leader counts vs Phase 1-C ----------------------------
    print("\n--- STOP 3: C2 dyad leaders vs PHASE 1-C PUBLISHED ---")
    lead = defaultdict(lambda: {"t": 0, "first": 0})
    for r in res["C2"]:
        lead[r["true"]]["t"] += 1
        lead[r["true"]]["first"] += int(r["dyad_rank"] == 1)
    ok3 = True
    for raga, (want, n) in PHASE1C_COSINE_FIRST.items():
        got = lead[raga]["first"]
        ok3 &= (got == want and lead[raga]["t"] == n)
        print("  %-18s got=%d/%d want=%d/%d %s" %
              (raga, got, lead[raga]["t"], want, n,
               "OK" if got == want else "MISMATCH"))
    if not ok3:
        stop(3, "C2 dyad ranks do not reproduce Phase 1-C; implementation wrong")
    # C2 == C3 rankings (positive scalar) -- sanity, reported
    same = all(a["dyad_rank"] == c["dyad_rank"]
               for a, c in zip(res["C2"], res["C3"]))
    print("  C2 and C3 dyad rankings identical (expected): %s" % same)

    # --- results ----------------------------------------------------------
    tallies = {c: tally(res[c]) for c in CONDITIONS + SENSITIVITY}
    ragas = sorted(st1)

    print("\n" + "=" * 74)
    print("OUTCOMES BY CONDITION (correct / wrong / unknown, never pooled)")
    print("=" * 74)
    print("  %-18s %5s " % ("raga", "clips") +
          " ".join("%-9s" % c for c in CONDITIONS))
    for r in ragas:
        cells = []
        for c in CONDITIONS:
            s = tallies[c][0][r]
            cells.append("%d/%d/%d" % (s["c"], s["w"], s["u"]))
        print("  %-18s %5d " % (r, st1[r]["t"]) +
              " ".join("%-9s" % x for x in cells))
    cells = ["%d/%d/%d" % (tallies[c][1]["c"], tallies[c][1]["w"],
                           tallies[c][1]["u"]) for c in CONDITIONS]
    print("  %-18s %5d " % ("TOTAL", 70) + " ".join("%-9s" % x for x in cells))
    print("\n  Sensitivity (reported, not conditions):")
    for c in SENSITIVITY:
        s = tallies[c]
        bb = s[0][TARGET]
        print("    %-11s total %d/%d/%d   Bhairavi %d/%d/%d" %
              (c, s[1]["c"], s[1]["w"], s[1]["u"], bb["c"], bb["w"], bb["u"]))

    print("\n  Bhairavi (primary): dyad rank of true raga, leader distribution")
    bh = {}
    for c in CONDITIONS:
        rows = [r for r in res[c] if r["true"] == TARGET]
        bh[c] = dict(rank=dict(Counter(r["dyad_rank"] for r in rows)),
                     leader=dict(Counter(r["dyad_leader"] for r in rows)))
        print("    %s rank %s  leader %s" %
              (c, dict(sorted(bh[c]["rank"].items())),
               dict(sorted(bh[c]["leader"].items()))))

    print("\n  Saveri attraction")
    sav = {}
    for c in CONDITIONS:
        rows = res[c]
        sav[c] = dict(
            bhairavi_clips_saveri_leads_dyad=sum(
                1 for r in rows if r["true"] == TARGET
                and r["dyad_leader"] == "Saveri"),
            bhairavi_wrongs_predicted_saveri=sum(
                1 for r in rows if r["true"] == TARGET
                and r["outcome"] == "wrong" and r["pred"] == "Saveri"),
            saveri_incoming_errors=sum(
                1 for r in rows if r["outcome"] == "wrong"
                and r["pred"] == "Saveri"))
        print("    %s  Bhairavi clips with Saveri dyad leader %d | Bhairavi "
              "wrongs -> Saveri %d | Saveri incoming errors %d" %
              (c, sav[c]["bhairavi_clips_saveri_leads_dyad"],
               sav[c]["bhairavi_wrongs_predicted_saveri"],
               sav[c]["saveri_incoming_errors"]))

    # --- transitions ------------------------------------------------------
    pairs = [("C1", "C2"), ("C1", "C0"), ("C2", "C3"), ("C1", "C3")]
    trans = []
    print("\n  Condition transitions (clips changing outcome category)")
    for a, bcond in pairs:
        n = 0
        for x, y in zip(res[a], res[bcond]):
            if x["outcome"] != y["outcome"]:
                n += 1
                trans.append(dict(from_cond=a, to_cond=bcond, clip=x["fname"],
                                  true=x["true"], from_outcome=x["outcome"],
                                  to_outcome=y["outcome"], from_pred=x["pred"],
                                  to_pred=y["pred"]))
        print("    %s -> %s : %d clips change category" % (a, bcond, n))
    for t in trans:
        if t["from_cond"] == "C1" and t["to_cond"] == "C2":
            print("      %-44s %-9s %s -> %s  (%s -> %s)" %
                  (t["clip"][:44], t["true"], t["from_outcome"],
                   t["to_outcome"], t["from_pred"], t["to_pred"]))

    # --- alternative-explanation test: delta vs concentration -------------
    print("\n  Delta vs model concentration (alternative-explanation test)")
    by_raga_all = defaultdict(list)
    for c in processed:
        by_raga_all[c["raga"]].append(c)
    conc, delta = {}, {}
    for r in ragas:
        mu = np.mean([c["up"] for c in by_raga_all[r]], axis=0)
        md = np.mean([c["down"] for c in by_raga_all[r]], axis=0)
        conc[r] = 0.5 * (float(np.sqrt(np.dot(mu, mu))) +
                         float(np.sqrt(np.dot(md, md))))
        a = sum(1 for x in res["C1"] if x["true"] == r and x["dyad_rank"] == 1)
        b2 = sum(1 for x in res["C2"] if x["true"] == r and x["dyad_rank"] == 1)
        delta[r] = b2 - a
    for r in sorted(ragas, key=lambda k: conc[k]):
        print("    %-18s concentration %.4f   leader delta %+d" %
              (r, conc[r], delta[r]))
    rho = spearman([conc[r] for r in ragas], [delta[r] for r in ragas])
    print("    Spearman(concentration, delta) = %+.3f  (descriptive, n=7; "
          "concentration here = mean L2 of up/down full-population models)" % rho)

    # --- dyad discrimination ratio (L-026, optional) ----------------------
    print("\n  Dyad discrimination ratio (self / mean-other, L-026), by channel")
    ddr = {}
    for r in ragas:
        rows = [x for x in res["C1"] if x["true"] == r]
        raw_self = np.mean([x["dyad_vals"][r] for x in rows])
        raw_oth = np.mean([np.mean([v for k, v in x["dyad_vals"].items()
                                    if k != r]) for x in rows])
        rows2 = [f for f in folds if f["true"] == r]
        n_self = np.mean([f["nrm"][r] for f in rows2])
        n_oth = np.mean([np.mean([v for k, v in f["nrm"].items() if k != r])
                         for f in rows2])
        ddr[r] = dict(raw=float(raw_self / raw_oth), model_norm=float(n_self / n_oth))
        print("    %-18s raw %.3f   model-norm %.3f" %
              (r, ddr[r]["raw"], ddr[r]["model_norm"]))

    # --- stop 5: nothing modified -----------------------------------------
    fp1, _ = feature_fingerprint()
    dirty_after = git_porcelain()
    if fp1 != fp0:
        stop(5, "feature cache fingerprint changed during the run")
    if dirty_after:
        stop(5, "tracked/untracked files changed during the run: %s" %
             dirty_after[:5])

    # --- artifacts ---------------------------------------------------------
    os.makedirs(run_dir, exist_ok=True)
    rag = ragas
    with open(os.path.join(run_dir, "per_clip_by_condition.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["clip", "true_raga", "condition", "outcome", "predicted",
                    "tier", "margin", "dyad_rank_true", "dyad_leader",
                    "pcd_rank_true"] +
                   ["score_" + r for r in rag] + ["dyad_" + r for r in rag])
        for c in CONDITIONS + SENSITIVITY:
            for x in res[c]:
                w.writerow([x["fname"], x["true"], c, x["outcome"], x["pred"],
                            x["tier"], "%.10f" % x["margin"], x["dyad_rank"],
                            x["dyad_leader"], x["pcd_rank"]] +
                           ["%.10f" % x["scores"][r] for r in rag] +
                           ["%.10f" % x["dyad_vals"][r] for r in rag])
    with open(os.path.join(run_dir, "condition_transitions.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["from_cond", "to_cond", "clip", "true_raga", "from_outcome",
                    "to_outcome", "from_pred", "to_pred"])
        for t in trans:
            w.writerow([t["from_cond"], t["to_cond"], t["clip"], t["true"],
                        t["from_outcome"], t["to_outcome"], t["from_pred"],
                        t["to_pred"]])

    meas = dict(
        gamma=g,
        outcomes={c: dict(per_raga=tallies[c][0], total=tallies[c][1])
                  for c in CONDITIONS + SENSITIVITY},
        bhairavi=bh, saveri_attraction=sav,
        dyad_leader_counts_C1={r: sum(1 for x in res["C1"]
                                      if x["true"] == r and x["dyad_rank"] == 1)
                               for r in ragas},
        dyad_leader_counts_C2={r: lead[r]["first"] for r in ragas},
        concentration=conc, leader_delta=delta,
        spearman_concentration_delta=rho, discrimination_ratio=ddr)
    with open(os.path.join(run_dir, "phase1d_measurements.json"), "w",
              encoding="utf-8") as fh:
        json.dump(meas, fh, indent=2, sort_keys=True)

    meta = dict(
        gate="Q-003", phase="1-D", timestamp=ts, run_dir=run_dir,
        authorisation="researcher, in session, 2026-11-19",
        pre_registration="docs/research/Q-003/RESEARCH_PLAN.md",
        git_commit=commit, working_tree_clean_before=True,
        working_tree_clean_after=True,
        baseline_reproduced=True, raw_replication_pass=True,
        c2_reproduces_phase1c_ranks=True, c2_c3_rank_identical=bool(same),
        gamma=g["gamma"], gamma_range=g["gamma_range"],
        mean_S_raw=g["mean_S_raw"], mean_S_nrm=g["mean_S_nrm"],
        constants=dict(pcd_weight=PCD_WEIGHT, dyad_weight=DYAD_WEIGHT,
                       alpha=ALPHA, n_bins=N_BINS, eps=EPS,
                       min_stable_frames=MIN_STABLE_FRAMES,
                       margin_strict=MARGIN_STRICT,
                       min_margin_final=MIN_MARGIN_FINAL,
                       source="recognize_raga_v12.py / confusion_matrix_audit.py, imported"),
        feature_cache=dict(files=n_feat, fingerprint=fp0,
                           unchanged=(fp0 == fp1)),
        f4_not_run="audit F4 is recommended, not pre-registered as a variant",
        software=_versions(), seed=None, sampling=False,
        elapsed_sec=round(time.time() - t0, 2),
        read_only=True, modified_production_code=False,
        modified_datasets=False, modified_feature_cache=False,
        subset_search=False, promotion_candidate=False,
        adr005_blocks_promotion=True)
    with open(os.path.join(run_dir, "run_metadata.json"), "w",
              encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)

    print("\n" + "=" * 74)
    print("artifacts: %s" % run_dir)
    print("Diagnostic only. ADR-005 blocks any production change. Report and stop.")
    print("elapsed: %.2fs" % (time.time() - t0))
    print("=" * 74)


if __name__ == "__main__":
    main()
