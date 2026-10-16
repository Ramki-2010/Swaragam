"""Build docs/index.html (the illustrated report) from README.md.

The README is the source for every fact on the page: tables, gate statuses,
limitations, pipeline and links are parsed from it, never retyped. Before
building, the README's accuracy table is checked against the canonical table
in PROJECT_STATUS.md (clips and LOO accuracy per raga); any disagreement stops
the build. Only the design, the hero and the "Research governance" block live
in the template (docs/_report_template.html).

Usage:  python scripts/_build_report_page.py          # write docs/index.html
        python scripts/_build_report_page.py --check  # exit 1 if docs/index.html is stale

Standard library only.
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
TEMPLATE = ROOT / "docs" / "_report_template.html"
OUT = ROOT / "docs" / "index.html"
REPO_BLOB = "https://github.com/Ramki-2010/Swaragam/blob/main/"

# README heading -> (section id, nav label). Order is the README's own order.
SECTION_IDS = {
    "What Swaragam is": "what",
    "Research status": "status",
    "Pipeline": "pipeline",
    "Validated results": "results",
    "Methodology and limitations": "limits",
    "Repository navigation": "nav",
    "Installation and usage": "usage",
    "Research documentation": "docs",
    "Development and contributing": "dev",
    "License": "license",
}
GOV_BEFORE = "Repository navigation"  # the governance block is inserted before this section


def inline(text):
    """Minimal inline markdown: links (whose label may hold code), code, bold, italics."""
    out = []
    pos = 0
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        out.append(inline_plain(text[pos:m.start()]))
        out.append(link(inline_plain(m.group(1)), m.group(2)))
        pos = m.end()
    out.append(inline_plain(text[pos:]))
    return "".join(out)


def inline_plain(text):
    out = []
    for part in re.split(r"(`[^`]+`)", text):
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append("<code>%s</code>" % html.escape(part[1:-1]))
            continue
        part = html.escape(part, quote=False)
        part = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", part)
        part = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", part)
        out.append(part)
    return "".join(out)


def link(label, href):
    if not re.match(r"^(https?:|#|mailto:)", href):
        href = REPO_BLOB + href.lstrip("./")
    return '<a href="%s" target="_blank" rel="noopener">%s</a>' % (href, label)


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def pill_class(status):
    s = status.lower()
    if s.startswith(("answered", "completed")):
        return "done"
    if s.startswith("active"):
        return "active"
    if s.startswith("blocked"):
        return "blocked"
    return "pending"


def render_table(rows):
    header, body = rows[0], rows[2:]
    is_gate = header[0].strip().lower() == "gate"
    loo_col = next((i for i, h in enumerate(header) if "LOO" in h), None)
    numeric = {i for i, h in enumerate(header)
               if all(re.fullmatch(r"[\d.,%\-–]+|\*\*[\d.,%]+\*\*", r[i].strip()) for r in body if i < len(r))}
    out = ['<div class="tablewrap"><table>', "<tr>"]
    for i, h in enumerate(header):
        out.append('<th%s>%s</th>' % (' class="num"' if i in numeric and i != loo_col else "", inline(h)))
    out.append("</tr>")
    for r in body:
        total = r[0].strip().strip("*").upper() == "TOTAL" or r[0].strip().startswith("**TOTAL")
        out.append('<tr class="total">' if total else "<tr>")
        for i, c in enumerate(r):
            cls = ' class="num"' if i in numeric and i != loo_col else ""
            if is_gate and i == len(r) - 1:
                m = re.match(r"^(.*?)(\s+[—–-]+\s+(.*))?$", c)
                lead = m.group(1).strip()
                rest = m.group(3)
                cell = '<span class="pill %s">%s</span>' % (pill_class(lead), html.escape(lead.upper()))
                if rest:
                    cell += " " + inline(rest)
                out.append("<td>%s</td>" % cell)
            elif i == loo_col and not total:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", c)
                if m:
                    pct = float(m.group(1))
                    out.append('<td><div class="bar"><i style="width:%dpx"></i><span>%s</span></div></td>'
                               % (round(pct), html.escape(c)))
                else:
                    out.append("<td>%s</td>" % inline(c))
            else:
                out.append("<td%s>%s</td>" % (cls, inline(c)))
        out.append("</tr>")
    out.append("</table></div>")
    return "\n".join(out)


def render_blocks(lines, sec_id):
    """Render the body lines of one README section."""
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre>%s</pre>" % html.escape("\n".join(code)))
        elif line.startswith("### "):
            out.append("<h3>%s</h3>" % inline(line[4:].strip()))
            i += 1
        elif line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            text = " ".join(quote)
            cls = "note live" if "live gate" in text else "note"
            out.append('<div class="%s">%s</div>' % (cls, inline(text)))
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            out.append(render_table(rows))
        elif re.match(r"^- ", line):
            items = []
            while i < len(lines) and re.match(r"^- ", lines[i]):
                item = lines[i][2:]
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip():
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            cls = ' class="pts"' if sec_id == "what" else ""
            out.append("<ul%s>%s</ul>" % (cls, "".join("<li>%s</li>" % inline(t) for t in items)))
        else:
            para = []
            while (i < len(lines) and lines[i].strip() and not lines[i].startswith(("```", "|", ">", "- ", "### "))):
                para.append(lines[i].strip())
                i += 1
            out.append("<p>%s</p>" % inline(" ".join(para)))
    return "\n".join(out)


def parse_readme(text):
    lines = text.splitlines()
    intro, sections, cur = [], [], None
    for line in lines[1:]:
        if line.startswith("## "):
            cur = (line[3:].strip(), [])
            sections.append(cur)
        elif cur is None:
            intro.append(line)
        else:
            cur[1].append(line)
    return intro, sections


def table_after(text, marker):
    """Rows of the first markdown table after the line containing `marker`."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if marker in l)
    rows = []
    for l in lines[start:]:
        if l.startswith("|"):
            rows.append(split_row(l))
        elif rows:
            break
    return rows[2:]


def verify_against_status(readme_text):
    """README's accuracy table must agree with the canonical table in PROJECT_STATUS.md."""
    status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")
    canon = {}
    for r in table_after(status, "### Current Accuracy"):
        pct = re.search(r"(\d+(?:\.\d+)?)\s*%", r[2])
        canon[r[0].strip("* ")] = (r[1].strip("* "), pct.group(1))
    mirror = {}
    for r in table_after(readme_text, "## Validated results"):
        pct = re.search(r"(\d+(?:\.\d+)?)\s*%", r[-1])
        mirror[r[0].strip("* ").replace("TOTAL", "Overall")] = (r[1].strip("* "), pct.group(1))
    bad = []
    for name, vals in canon.items():
        if name not in mirror:
            bad.append("%s: in PROJECT_STATUS.md, missing from README" % name)
        elif mirror[name] != vals:
            bad.append("%s: PROJECT_STATUS.md (clips, %%)=%s, README=%s" % (name, vals, mirror[name]))
    bad += ["%s: in README, missing from PROJECT_STATUS.md" % n for n in mirror if n not in canon]
    if bad:
        sys.exit("README disagrees with PROJECT_STATUS.md (the canonical source); "
                 "fix the README before building the page:\n  " + "\n  ".join(bad))


def build():
    readme_text = README.read_text(encoding="utf-8")
    verify_against_status(readme_text)
    intro_lines, sections = parse_readme(readme_text)
    tag = next(l for l in intro_lines if l.startswith("**"))
    para = " ".join(l.strip() for l in intro_lines
                    if l.strip() and not l.startswith(("**", "<", ">", "[")) and "<" not in l)
    tagline = re.sub(r"^\*\*(.*)\*\*$", r"\1", tag.strip())

    names = [n for n, _ in sections]
    unknown = [n for n in names if n not in SECTION_IDS]
    if unknown:
        sys.exit("README has sections the page does not know how to place: %s. "
                 "Add them to SECTION_IDS in %s." % (unknown, Path(__file__).name))

    before, after = [], []
    bucket = before
    for name, body in sections:
        if name == GOV_BEFORE:
            bucket = after
        sec_id = SECTION_IDS[name]
        bucket.append('<section id="%s">\n<h2>%s</h2>\n%s\n</section>' % (sec_id, inline(name), render_blocks(body, sec_id)))
    if bucket is before:
        sys.exit("README no longer has a '%s' section; governance block has nowhere to go." % GOV_BEFORE)

    tpl = TEMPLATE.read_text(encoding="utf-8")
    page = (tpl.replace("{{TAGLINE}}", html.escape(tagline))
               .replace("{{INTRO}}", inline(para))
               .replace("{{SECTIONS_BEFORE_GOV}}", "\n\n".join(before))
               .replace("{{SECTIONS_AFTER_GOV}}", "\n\n".join(after)))
    left = re.findall(r"\{\{[A-Z_]+\}\}", page)
    if left:
        sys.exit("Unfilled template placeholders: %s" % left)
    return page


def write():
    page = build()
    OUT.write_text(page, encoding="utf-8", newline="\n")
    print("wrote %s (%d bytes)" % (OUT.relative_to(ROOT), len(page.encode("utf-8"))))


if __name__ == "__main__":
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != build():
            print("docs/index.html is stale: run scripts/_build_report_page.py")
            sys.exit(1)
        print("docs/index.html is up to date with README.md")
    else:
        write()
