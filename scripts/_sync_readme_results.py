"""Keep the README's results mirror in step with PROJECT_STATUS.md.

PROJECT_STATUS.md -> "Current Accuracy" is the canonical table. The README
carries a summary of it. This script reads the canonical table and brings these
README fields into line with it:

  * the "Validated results" table: Training Clips and LOO Accuracy per raga,
    plus the TOTAL row (clips, correct, wrong, unknown, accuracy);
  * the summary sentence under that heading (clip, correct/wrong/unknown
    counts and the decided percentage);
  * the accuracy cell of the current version's row in "Version history".

It does NOT edit prose elsewhere in the README. Figures quoted in the
limitations bullets are only compared, and any disagreement is reported for a
person to resolve.

Per-raga correct/wrong/unknown counts are not in PROJECT_STATUS.md's table, so
they are never invented here. After syncing, the whole results table must pass
the row-sum checks required by .ai-memory/evaluation-protocol.md section 4
(each row sums to its clips, columns sum to the totals, each accuracy equals
correct/(correct+wrong)). If it does not, nothing is written and the message
says the counts must be refreshed from the LOO script output
(sandbox_loo_v131_canonical.py) first.

Usage:
  python scripts/_sync_readme_results.py            # report only; exit 1 if the README is out of step
  python scripts/_sync_readme_results.py --write    # update README.md and regenerate docs/index.html
Never commits and never stages. Review the diff, then commit by hand.
Standard library only.
"""
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _build_report_page as page  # noqa: E402  (shares the markdown table helpers)

ROOT = page.ROOT
README = page.README
STATUS = ROOT / "PROJECT_STATUS.md"


def half_up(x, places=0):
    f = 10 ** places
    return math.floor(x * f + 0.5) / f


def read_canonical(status_text):
    """-> ({raga: (clips, pct_str)}, overall dict, current version string)."""
    rows = page.table_after(status_text, "### Current Accuracy")
    ragas, overall = {}, None
    for r in rows:
        name = r[0].strip("* ")
        pct = re.search(r"(\d+(?:\.\d+)?)\s*%", r[2])
        if not pct:
            sys.exit("PROJECT_STATUS.md: no percentage in row %r" % (r,))
        if name == "Overall":
            overall = {"clips": r[1].strip("* "), "pct": pct.group(1)}
        else:
            ragas[name] = (r[1].strip("* "), pct.group(1))
    line = next((l for l in status_text.splitlines() if "New canonical" in l), None)
    m = re.search(r"(\d+)c/(\d+)w/(\d+)u", line or "")
    if not overall or not m:
        sys.exit("PROJECT_STATUS.md: could not find the Overall row or the 'New canonical ... (Nc/Nw/Nu)' line.")
    overall.update(c=m.group(1), w=m.group(2), u=m.group(3))
    ver = re.search(r"^Swarag v(\d+(?:\.\d+)+)", status_text, re.M)
    return ragas, overall, (ver.group(1) if ver else None)


def results_table_span(lines):
    start = next(i for i, l in enumerate(lines) if l.strip() == "## Validated results")
    first = next(i for i in range(start, len(lines)) if lines[i].startswith("|"))
    last = first
    while last + 1 < len(lines) and lines[last + 1].startswith("|"):
        last += 1
    return first, last


def sync(readme_text, ragas, overall, version):
    lines = readme_text.split("\n")
    changes = []
    first, last = results_table_span(lines)
    seen = set()
    for i in range(first + 2, last + 1):
        cells = page.split_row(lines[i])
        name = cells[0].strip("* ")
        is_total = name.upper() == "TOTAL"
        if is_total:
            new = ["**TOTAL**", "**%s**" % overall["clips"], "**%s**" % overall["c"], "**%s**" % overall["w"],
                   "**%s**" % overall["u"], "**%s%%**" % overall["pct"]]
        elif name in ragas:
            seen.add(name)
            clips, pct = ragas[name]
            new = [cells[0], clips, cells[2], cells[3], cells[4], "%s%%" % pct]
        else:
            sys.exit("README results table has a raga PROJECT_STATUS.md does not: %s" % name)
        line = "| " + " | ".join(new) + " |"
        if line != lines[i]:
            changes.append("results row %s: %s -> %s" % (name, lines[i], line))
            lines[i] = line
    missing = set(ragas) - seen
    if missing:
        sys.exit("PROJECT_STATUS.md has ragas the README results table lacks: %s" % sorted(missing))

    text = "\n".join(lines)
    summary = re.compile(r"\(`([^`]+)`, \d+ clips, \d+ correct / \d+ wrong / \d+ unknown, [\d.]+% decided\)")
    new_summary = lambda m: "(`%s`, %s clips, %s correct / %s wrong / %s unknown, %s%% decided)" % (
        m.group(1), overall["clips"], overall["c"], overall["w"], overall["u"], overall["pct"])
    if not summary.search(text):
        sys.exit("README summary sentence under 'Validated results' was not found; update the pattern in this script.")
    updated = summary.sub(new_summary, text, count=1)
    if updated != text:
        changes.append("summary sentence updated")
    text = updated

    if version:
        row = re.compile(r"^(\| v%s \| )[\d.]+%%( \|.*)$" % re.escape(version), re.M)
        if row.search(text):
            updated = row.sub(lambda m: "%s%s%%%s" % (m.group(1), overall["pct"], m.group(2)), text, count=1)
            if updated != text:
                changes.append("version history v%s accuracy updated" % version)
            text = updated
        else:
            changes.append("NOTE: no 'v%s' row in Version history to sync" % version)
    return text, changes


def row_sum_problems(text):
    """The evaluation-protocol section 4 checks on the README results table."""
    rows = page.table_after(text, "## Validated results")
    problems, tot, sums = [], None, [0, 0, 0, 0]
    for r in rows:
        name = r[0].strip("* ")
        nums = [r[i].strip("* ") for i in range(1, 5)]
        pct = float(re.search(r"[\d.]+", r[5]).group(0))
        clips, c, w, u = (int(n) for n in nums)
        if name.upper() == "TOTAL":
            tot = (clips, c, w, u, pct)
            continue
        if c + w + u != clips:
            problems.append("%s: correct+wrong+unknown = %d, but clips = %d" % (name, c + w + u, clips))
        if c + w and half_up(100.0 * c / (c + w)) != half_up(pct):
            problems.append("%s: %d/(%d+%d) is %.1f%%, README says %s%%" % (name, c, c, w, 100.0 * c / (c + w), pct))
        sums = [a + b for a, b in zip(sums, (clips, c, w, u))]
    if tot is None:
        return ["no TOTAL row found"]
    for label, got, want in zip(("clips", "correct", "wrong", "unknown"), sums, tot[:4]):
        if got != want:
            problems.append("TOTAL %s: rows sum to %d, TOTAL row says %d" % (label, got, want))
    if tot[2] + tot[1] and half_up(100.0 * tot[1] / (tot[1] + tot[2]), 1) != tot[4]:
        problems.append("TOTAL accuracy: %d/(%d+%d) is %.1f%%, README says %s%%" % (
            tot[1], tot[1], tot[2], 100.0 * tot[1] / (tot[1] + tot[2]), tot[4]))
    return problems


def prose_drift(text, ragas):
    """Percentages quoted in the limitations bullets must match the table. Reported, never edited."""
    notes = []
    section = text.split("## Methodology and limitations", 1)[-1].split("\n## ", 1)[0]
    for name, (_, pct) in ragas.items():
        for m in re.finditer(r"\*\*%s (\d+(?:\.\d+)?)%%" % re.escape(name), section):
            if half_up(float(m.group(1))) != half_up(float(pct)):
                notes.append("limitations text says %s %s%%, canonical table says %s%%" % (name, m.group(1), pct))
    return notes


def main(argv):
    status_text = STATUS.read_text(encoding="utf-8")
    readme_text = README.read_text(encoding="utf-8")
    ragas, overall, version = read_canonical(status_text)
    new_text, changes = sync(readme_text, ragas, overall, version)

    problems = row_sum_problems(new_text)
    if problems:
        print("Row-sum check FAILED on the README results table after syncing. Nothing was written.")
        for p in problems:
            print("  -", p)
        print("The per-raga correct/wrong/unknown counts are not in PROJECT_STATUS.md. Refresh them from the\n"
              "output of scripts/sandbox_loo_v131_canonical.py (and PROJECT_STATUS.md), then rerun.")
        return 2

    drift = prose_drift(new_text, ragas)
    real = [c for c in changes if not c.startswith("NOTE:")]
    for c in changes:
        print(("  would change: " if "--write" not in argv else "  changed: ") + c)
    for d in drift:
        print("  WARNING (edit by hand):", d)

    if "--write" in argv:
        if new_text != readme_text:
            README.write_text(new_text, encoding="utf-8", newline="\n")
        page.write()
        print("README.md %s; docs/index.html regenerated. Nothing staged or committed." %
              ("updated" if new_text != readme_text else "already in step"))
        return 1 if drift else 0
    if real:
        print("README is out of step with PROJECT_STATUS.md. Run: python scripts/_sync_readme_results.py --write")
        return 1
    print("README results mirror agrees with PROJECT_STATUS.md; row sums pass.")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
