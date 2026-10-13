"""Review Board audit packages: minimized export, identifier redaction, secret scan, provenance.

Tooling script for SKILL.md section 10 and ADR-021. Writes ONLY under the project-local,
gitignored archive `review_board_archive/` (or an explicit --out). Never modifies the tracked
repository, Claude session logs, or an existing package.

PROTECTION, STATED ACCURATELY: identifier redaction for known classes and a best-effort
secret scan. It does not guarantee that a package is private or free of secrets.
  Identifier classes redacted:
    - email addresses (pattern-detected; noreply@anthropic.com kept), incl. escaped forms
    - name tokens (>= 4 chars) from the OWNER's addresses only (git user.email, or addresses
      sharing a 5-character stem with it or with the Windows username)
    - the Windows username, as a whole token anywhere
    - org/account IDs, narrow patterns only: `org=<uuid>` and organization/org/account/user
      + id/uuid keys
    - Claude session IDs known to this project, full or truncated
  The public GitHub handle in the repository's remote URL is kept (CLAUDE.md section 1a).
  The secret scan runs FIRST, on intact text, then identifier redaction.
  Secret scan: common credential formats (see SECRET_PATTERNS). Hits are replaced with
  [REDACTED_SECRET:<type>] and listed in secret_scan_report.{json,md} without their values.
  A scan with no findings does NOT establish that no secrets are present.

DEFAULT PACKAGE (minimized): brief, report, roster.json, reviewer final reports, minimized
reviewer transcripts and the parent's Board segment (user/assistant text, tool calls and
tool results only), verification files, manifest.json, secret-scan report, SHA256SUMS.txt
and provenance_entry.md. Removed: thinking blocks, system/injected context
(<system-reminder> blocks, attachment and meta records), session metadata (uuids, cwd,
version, git branch, request ids). The full raw session log is included ONLY with
--full-session-log (explicit opt-in), and is still identifier-redacted and secret-scanned.

Subcommands
  export          package a live Board run from this project's Claude session logs
  package         build a package from an explicit JSON spec (used for historical exports)
  archive-source  copy an existing export folder verbatim into the archive with an
                  inventory and hashes, verify the copy, and optionally remove the original

Run from the repository root with my_virtual_env_swarag\\Scripts\\python.exe.
"""
import argparse, datetime, glob, hashlib, json, os, re, shutil, subprocess, sys

SCHEMA = "swaragam-review-board-audit/1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(REPO, "review_board_archive")
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# (?<!\\): in raw JSON a newline is the two characters "\n"; without this guard an email
# right after it would match as "n<email>" and redacting it would leave an invalid escape.
EMAIL = re.compile(r"(?<!\\)[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_ALLOW = {"noreply@anthropic.com"}
ORG_PATTERNS = [
    re.compile(r"[?&]org=(" + UUID + ")", re.I),
    re.compile(r'(?i)"?(?:organization|org|account|user)_?(?:uuid|id)"?\s*[:=]\s*"?(' + UUID + ")"),
]
SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
_V = r"[^\s\"'\\,;)<>]"  # secret value characters: never spans a quote or JSON escape
# Start-of-token boundary that also holds right after a JSON escape: in raw JSON a newline is
# the two characters "\n", so a plain \b fails between that "n" and the next token.
_B = r"(?:(?<=\\[nrt\"])|(?<![A-Za-z0-9_]))"
_E = r"(?![A-Za-z0-9_])"
SECRET_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
    ("anthropic_api_key", re.compile(_B + r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai_api_key", re.compile(_B + r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("github_token", re.compile(_B + r"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})")),
    ("aws_access_key_id", re.compile(_B + r"(?:AKIA|ASIA)[0-9A-Z]{16}" + _E)),
    ("aws_secret_access_key", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*" + _V + "{20,}")),
    ("google_api_key", re.compile(_B + r"AIza[0-9A-Za-z_-]{35}" + _E)),
    ("slack_token", re.compile(_B + r"xox[abprs]-[A-Za-z0-9-]{10,}")),
    ("stripe_key", re.compile(_B + r"(?:sk|rk)_live_[A-Za-z0-9]{16,}")),
    ("jwt", re.compile(_B + r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("authorization_header", re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[A-Za-z0-9._~+/=-]{12,}")),
    ("bearer_token", re.compile(r"(?i)" + _B + r"bearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("url_credentials", re.compile(r"(://)[^/\s:@\"'\\]+:[^/\s@\"'\\]{3,}(@)")),
    ("key_value_credential", re.compile(
        r"(?i)" + _B + r"((?:password|passwd|pwd|secret|client[_-]?secret|api[_-]?key|access[_-]?key|auth[_-]?token|token)"
        r"[\"']?\s*[:=]\s*[\"']?)(?![<$*{\[(]|x{3})(" + _V + "{8,})")),
]
PLACEHOLDER = re.compile(r"(?i)^(?:x+|\*+|changeme|redacted.*|example.*|your[_-].*|<.*>|none|null|true|false)$")


# ---------------------------------------------------------------- utilities

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head():
    try:
        return subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "NOT ESTABLISHED"


def json_lines(path):
    """JSON objects from a .jsonl file, or from JSONL embedded in a Markdown file."""
    with open(path, encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if s.startswith("{"):
                try:
                    yield json.loads(s)
                except json.JSONDecodeError:
                    continue


def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for c in content or []:
        if isinstance(c, dict):
            if c.get("type") == "text":
                out.append(c.get("text", ""))
            elif c.get("type") == "tool_result":
                out.append(text_of(c.get("content")))
    return "\n".join(out)


def clean(text):
    return SYSTEM_REMINDER.sub("", text or "").strip()


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s or "item").strip("_")[:60] or "item"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ---------------------------------------------------------------- minimization

def minimize(records, since=None, until=None, stats=None):
    """Keep user/assistant text, tool calls and tool results; drop everything else."""
    stats = stats if stats is not None else {}
    out = []
    for o in records:
        t, ts = o.get("type"), o.get("timestamp", "")
        if t not in ("user", "assistant") or o.get("isMeta"):
            stats["dropped_records"] = stats.get("dropped_records", 0) + 1
            continue
        if (since and ts and ts < since) or (until and ts and ts > until):
            continue
        content, kept = (o.get("message") or {}).get("content"), []
        items = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
        for c in items:
            if not isinstance(c, dict):
                continue
            ct = c.get("type")
            if ct == "text":
                txt = clean(c.get("text"))
                if txt:
                    kept.append({"type": "text", "text": txt})
            elif ct == "tool_use":
                kept.append({"type": "tool_use", "id": c.get("id"), "name": c.get("name"), "input": c.get("input")})
            elif ct == "tool_result":
                kept.append({"type": "tool_result", "tool_use_id": c.get("tool_use_id"),
                             "is_error": bool(c.get("is_error")), "content": clean(text_of(c.get("content")))})
            else:
                stats["dropped_" + str(ct)] = stats.get("dropped_" + str(ct), 0) + 1
        if kept:
            out.append({"timestamp": ts, "role": t, "content": kept})
    return out


def write_min(records, base, title):
    write(base + ".jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    lines = [f"# {title}", "", "Minimized transcript: user/assistant text, tool calls and tool results only.", ""]
    for r in records:
        for c in r["content"]:
            if c["type"] == "text":
                lines += [f"## {r['role'].title()} - {r['timestamp']}", "", c["text"], ""]
            elif c["type"] == "tool_use":
                lines += [f"**Tool call** `{c['name']}` `{c['id']}` - {r['timestamp']}", "", "```json",
                          json.dumps(c["input"], indent=2, ensure_ascii=False), "```", ""]
            else:
                err = " (ERROR)" if c["is_error"] else ""
                lines += [f"**Tool result**{err} `{c['tool_use_id']}` - {r['timestamp']}", "", "```", c["content"], "```", ""]
    write(base + ".md", "\n".join(lines))


HANDBACK_FIELDS = {"SubagentHandback": "message", "ExitPlanMode": "plan"}


def final_report(records):
    """The reviewer's last delivered output: the latest of its final assistant text or a
    hand-back tool call (some agent types deliver their report as SubagentHandback/ExitPlanMode)."""
    last = None
    for r in records:
        if r["role"] != "assistant":
            continue
        for c in r["content"]:
            if c["type"] == "text" and c["text"].strip():
                last = (r["timestamp"], c["text"])
            elif c["type"] == "tool_use" and c.get("name") in HANDBACK_FIELDS:
                msg = (c.get("input") or {}).get(HANDBACK_FIELDS[c["name"]])
                if isinstance(msg, str) and msg.strip():
                    last = (r["timestamp"], msg)
    return last


# ---------------------------------------------------------------- redaction and secret scan

def project_dir():
    base = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    want = re.sub(r"[^A-Za-z0-9]", "-", REPO).lower()
    if os.path.isdir(base):
        for d in os.listdir(base):
            if d.lower() == want:
                return os.path.join(base, d)
    return None


def github_handle():
    try:
        cfg = open(os.path.join(REPO, ".git", "config"), encoding="utf-8").read()
        m = re.search(r"github\.com[:/]([A-Za-z0-9-]+)/", cfg)
        return m.group(1) if m else None
    except OSError:
        return None


def escaped(s):
    """Pattern for s that also matches regex/JSON-escaped forms (e.g. 'a\\.b' for 'a.b')."""
    return r"\\*".join(re.escape(ch) for ch in s)


def git_emails():
    found = set()
    for key in ("user.email",):
        try:
            v = subprocess.run(["git", "-C", REPO, "config", "--get", key], capture_output=True, text=True).stdout.strip()
            if v:
                found.add(v)
        except OSError:
            pass
    return found


class Redactor:
    def __init__(self, blob, current_session=None):
        self.handle = github_handle()
        self.rules, self.residue, self.counts = [], [], {}
        if self.handle:  # protect the public handle before the username rule can touch it
            self.rules.append(("_protect", re.compile(re.escape(self.handle), re.I), "\x00GH\x00"))
        owner = git_emails()
        emails = {e for e in set(EMAIL.findall(blob)) | owner if e.lower() not in EMAIL_ALLOW}
        user = os.environ.get("USERNAME") or os.path.basename(os.path.expanduser("~"))
        tok = lambda e: [p.lower() for p in re.split(r"[._+-]", e.split("@")[0]) if len(p) >= 4 and not p.isdigit()]
        stems = {t[:5] for e in owner for t in tok(e)} | ({user.lower()[:5]} if len(user) >= 5 else set())
        # Name tokens come only from OWNER addresses (git user.email, or addresses sharing a 5-char
        # stem with it or with the username). Third-party addresses are redacted whole, but their
        # name parts are not propagated, so ordinary words (e.g. "private") are never erased.
        owner_like = {e for e in emails if e in owner or any(t[:5] in stems for t in tok(e))}
        parts = set()
        for e in owner_like:
            parts |= set(tok(e))
        for e in sorted(emails, key=len, reverse=True):
            self.rules.append(("email", re.compile(escaped(e), re.I), "[REDACTED_EMAIL]"))
        for p in sorted(parts, key=len, reverse=True):
            self.rules.append(("name_token", re.compile(r"(?i)(?<![A-Za-z0-9])" + re.escape(p) + r"[A-Za-z]?(?![A-Za-z0-9])"), "[REDACTED]"))
        proj = project_dir()
        sessions = set()
        if proj:
            sessions = {os.path.splitext(n)[0].lower() for n in os.listdir(proj) if re.fullmatch(UUID + r"(\.jsonl)?", n, re.I)}
        sessions |= {m.lower() for m in re.findall(r'"sessionId"\s*:\s*"(' + UUID + ')"', blob, re.I)}
        orgs = {m.group(1).lower() for rx in ORG_PATTERNS for m in rx.finditer(blob)} - sessions
        for o in sorted(orgs):
            self.rules.append(("org_or_account_id", re.compile(re.escape(o[:8]) + r"(?:-[0-9a-f]+)*-?", re.I), "[REDACTED_ORG_ID]"))
        for sid in sorted(sessions):
            label = "SESSION-CURRENT" if current_session and sid == current_session.lower() else \
                "SESSION-" + hashlib.sha256(sid.encode()).hexdigest()[:6].upper()  # stable across packages
            self.rules.append(("session_id", re.compile(re.escape(sid[:8]) + r"(?:-[0-9a-f]+)*-?", re.I), label))
        user_rx = re.compile(r"(?i)(?<![A-Za-z0-9])" + re.escape(user) + r"(?![A-Za-z0-9])")
        self.rules.append(("windows_username", user_rx, "USER"))
        if self.handle:
            self.rules.append(("_restore", re.compile("\x00GH\x00"), self.handle))
        self.residue = [user_rx] + [re.compile(escaped(e), re.I) for e in emails]
        self.residue += [re.compile(r"(?i)(?<![A-Za-z0-9])" + re.escape(p)) for p in parts]
        self.residue += [re.compile(re.escape(x[:8]), re.I) for x in sorted(sessions | orgs)]
        self.known = {"emails": len(emails), "name_tokens": len(parts), "session_ids": len(sessions), "org_or_account_ids": len(orgs)}

    def apply(self, text):
        for name, rx, rep in self.rules:
            text, k = rx.subn(rep, text)
            if not name.startswith("_"):
                self.counts[name] = self.counts.get(name, 0) + k
        return text

    def remaining(self, text):
        probe = re.sub(re.escape(self.handle), "", text, flags=re.I) if self.handle else text
        return sum(len(rx.findall(probe)) for rx in self.residue)


def secret_scan(text, rel, findings):
    lines_at = [0] + [m.end() for m in re.finditer("\n", text)]

    def line_no(pos):
        lo, hi = 0, len(lines_at) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if lines_at[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    for kind, rx in SECRET_PATTERNS:
        def repl(m, kind=kind):
            if kind == "key_value_credential":
                if PLACEHOLDER.match(m.group(2)):
                    return m.group(0)
                findings.append({"file": rel, "line": line_no(m.start()), "type": kind})
                return m.group(1) + f"[REDACTED_SECRET:{kind}]"
            findings.append({"file": rel, "line": line_no(m.start()), "type": kind})
            if kind == "authorization_header":
                return m.group(1) + f"[REDACTED_SECRET:{kind}]"
            if kind == "url_credentials":
                return m.group(1) + f"[REDACTED_SECRET:{kind}]" + m.group(2)
            return f"[REDACTED_SECRET:{kind}]"
        text = rx.sub(repl, text)
    return text


def text_files(root, skip=()):
    for dp, _, fs in os.walk(root):
        for fn in sorted(fs):
            p = os.path.join(dp, fn)
            if os.path.relpath(p, root) not in skip:
                yield p


def protect_tree(root, redactor, scan=True, skip=()):
    """Redact identifiers, then secret-scan, every file; validate JSONL; return problems/findings."""
    problems, findings = [], []
    for p in text_files(root, skip):
        rel = os.path.relpath(p, root)
        try:
            t = open(p, encoding="utf-8", newline="").read()
        except UnicodeDecodeError:
            problems.append(f"{rel}: not UTF-8 text; not scanned (excluded from guarantees)")
            continue
        # Secrets first, on intact text: identifier redaction can otherwise break a secret's
        # shape (e.g. turn "user:pass@host" into an email, or a name token into "[REDACTED]").
        new = secret_scan(t, rel, findings) if scan else t
        new = redactor.apply(new)
        if p.endswith(".jsonl"):
            for i, line in enumerate(new.splitlines(), 1):
                if line.strip():
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as e:
                        problems.append(f"{rel}:{i} invalid JSON after redaction ({e})")
        if new != t:
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(new)
        left = redactor.remaining(new)
        if left:
            problems.append(f"{rel}: {left} detected identifiers remain")
    return problems, findings


def write_sums(root, exclude=("SHA256SUMS.txt", "provenance_entry.md")):
    lines = [f"{sha256(p)} *{os.path.relpath(p, root).replace(os.sep, '/')}" for p in text_files(root, exclude)]
    write(os.path.join(root, "SHA256SUMS.txt"), "\n".join(sorted(lines, key=lambda s: s.split("*", 1)[1])) + "\n")
    return len(lines)


def package_location(out):
    try:
        rel = os.path.relpath(out, ARCHIVE)
    except ValueError:  # different drive
        return os.path.basename(out) + " (outside review_board_archive)"
    if rel.startswith(".."):
        return os.path.basename(out) + " (outside review_board_archive)"
    return "review_board_archive/" + rel.replace(os.sep, "/")


# ---------------------------------------------------------------- package builder

def build_package(spec):
    """spec keys: out, label, date, question, kind ('live'|'historical'), historical_note,
    roster [{id, perspective, agent_type, enforcement, transcript, final_report}], roster_source,
    brief, report, parent_segment {path, since, until}, extras [paths], full_session_log,
    source_logs [paths], isolation_status, current_session, head."""
    out = spec["out"]
    if os.path.exists(out):
        sys.exit(f"ERROR: {out} exists; never overwrite a package")
    os.makedirs(out)
    stats, roster_out, limitations = {}, [], []
    for f, name in ((spec.get("brief"), "brief"), (spec.get("report"), "report")):
        if f and os.path.isfile(f):
            shutil.copyfile(f, os.path.join(out, f"{name}_{os.path.basename(f)}"))
        else:
            limitations.append(f"{name}: NOT AVAILABLE")
    for i, r in enumerate(spec.get("roster", []), 1):
        name = f"{i}_{slug(r.get('perspective'))}"
        entry = {k: r.get(k) for k in ("id", "perspective", "agent_type", "enforcement")}
        recs = minimize(json_lines(r["transcript"]), stats=stats) if r.get("transcript") and os.path.isfile(r["transcript"]) else None
        if recs:
            write_min(recs, os.path.join(out, "transcripts", name), f"Reviewer transcript: {r.get('perspective')}")
            entry["transcript"] = f"transcripts/{name}.jsonl"
        else:
            entry["transcript"] = "MISSING"
            limitations.append(f"reviewer {r.get('id')} ({r.get('perspective')}): transcript MISSING")
        fr_text = None
        if r.get("final_report") and os.path.isfile(r["final_report"]):
            fr_text = (None, open(r["final_report"], encoding="utf-8").read())
        elif recs:
            fr_text = final_report(recs)
        if fr_text:
            write(os.path.join(out, "reviewer_reports", name + ".md"),
                  f"<!-- Final report of {r.get('perspective')} ({r.get('id')}); last assistant message {fr_text[0] or 'from supplied file'} -->\n\n{fr_text[1]}")
            entry["final_report"] = f"reviewer_reports/{name}.md"
        else:
            entry["final_report"] = "MISSING"
            limitations.append(f"reviewer {r.get('id')} ({r.get('perspective')}): final report MISSING")
        entry["status"] = "OK" if "MISSING" not in (entry["transcript"], entry["final_report"]) else "MISSING"
        roster_out.append(entry)
    write(os.path.join(out, "roster.json"), json.dumps({"roster_source": spec.get("roster_source"), "reviewers": roster_out}, indent=2, ensure_ascii=False))
    seg = spec.get("parent_segment")
    if seg and seg.get("path") and os.path.isfile(seg["path"]):
        recs = minimize(json_lines(seg["path"]), seg.get("since"), seg.get("until"), stats)
        write_min(recs, os.path.join(out, "parent", "board_segment"), "Parent (orchestrator) Board segment")
    used = set()
    for f in spec.get("extras", []):
        base = os.path.basename(f.rstrip("/\\"))
        if base in used:
            sys.exit(f"ERROR: duplicate --extra name {base}")
        used.add(base)
        dst = os.path.join(out, "verification", base)
        if os.path.isdir(f):
            shutil.copytree(f, dst)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(f, dst)
    if spec.get("full_session_log"):
        os.makedirs(os.path.join(out, "raw_full_session"))
        shutil.copyfile(spec["full_session_log"], os.path.join(out, "raw_full_session", "full_session_log.jsonl"))
        limitations.append("OPT-IN: raw_full_session/ contains the complete session log (identifier-redacted, secret-scanned)")

    blob = "\n".join(open(p, encoding="utf-8", errors="replace").read() for p in text_files(out))
    red = Redactor(blob, spec.get("current_session"))
    problems, findings = protect_tree(out, red)
    report = {"tool": "secret scan (best-effort pattern scan)", "statement":
              "Absence of findings does not establish absence of secrets.", "patterns": [k for k, _ in SECRET_PATTERNS],
              "findings_count": len(findings), "findings": findings}
    write(os.path.join(out, "secret_scan_report.json"), json.dumps(report, indent=2))
    md = ["# Secret scan report", "", "Best-effort pattern scan. **Absence of findings does not establish absence of secrets.**",
          "Values are never recorded; matches were replaced with `[REDACTED_SECRET:<type>]`.", "",
          f"Findings: {len(findings)}", ""] + [f"- `{x['file']}` line {x['line']}: {x['type']}" for x in findings]
    write(os.path.join(out, "secret_scan_report.md"), "\n".join(md) + "\n")
    manifest = {
        "schema": SCHEMA, "kind": spec.get("kind", "live"), "label": spec.get("label"), "date": spec.get("date"),
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "question": spec.get("question"), "repository_head": spec.get("head") or git_head(),
        "exporter_sha256": sha256(os.path.abspath(__file__)), "historical_note": spec.get("historical_note"),
        "protection": "identifier redaction for known classes, followed by a best-effort secret scan",
        "identifier_classes_known": red.known, "identifier_replacements": red.counts,
        "minimization_dropped": stats, "full_session_log_included": bool(spec.get("full_session_log")),
        "isolation_status": spec.get("isolation_status", "NOT RECORDED"), "roster_source": spec.get("roster_source"),
        "source_logs_sha256_before_minimization": {os.path.basename(p): sha256(p) for p in spec.get("source_logs", []) if os.path.isfile(p)},
        "limitations": limitations, "problems": problems,
    }
    write(os.path.join(out, "manifest.json"), json.dumps(manifest, indent=2, ensure_ascii=False))
    for name in ("manifest.json", "roster.json"):  # generated metadata gets the same identifier pass
        p = os.path.join(out, name)
        t = red.apply(open(p, encoding="utf-8").read())
        write(p, t)
        if red.remaining(t):
            problems.append(f"{name}: detected identifiers remain")
    n = write_sums(out)
    sums_hash = sha256(os.path.join(out, "SHA256SUMS.txt"))
    key = ["roster.json", "manifest.json", "secret_scan_report.json"] + \
          sorted(os.path.relpath(p, out).replace(os.sep, "/") for p in text_files(out) if re.search(r"(^|[\\/])(brief_|report_)|reviewer_reports", os.path.relpath(p, out)))
    entry = [f"### {spec.get('date')} - {spec.get('label')}", "",
             f"- **Kind:** {spec.get('kind', 'live')}" + (f" ({spec.get('historical_note')})" if spec.get("historical_note") else ""),
             f"- **Question:** {spec.get('question') or 'NOT RECORDED'}",
             f"- **Repository HEAD at run:** `{manifest['repository_head']}`",
             f"- **Roster source:** {spec.get('roster_source')}", "- **Reviewers:**"]
    entry += [f"  - `{r['id']}` - {r['perspective']} - type `{r['agent_type']}`, enforcement `{r['enforcement']}` - {r['status']}" for r in roster_out]
    entry += [f"- **Isolation verification:** {manifest['isolation_status']}",
              f"- **Package:** `{package_location(out)}` (local, untracked)",
              f"- **SHA256SUMS.txt:** `{sums_hash}` ({n} files)", "- **Key artifacts (sha256):**"]
    entry += [f"  - `{k}`: `{sha256(os.path.join(out, k))}`" for k in key if os.path.isfile(os.path.join(out, k))]
    entry += [f"- **Secret scan:** {len(findings)} findings (best-effort)", f"- **Limitations:** {'; '.join(limitations) or 'none recorded'}", ""]
    write(os.path.join(out, "provenance_entry.md"), red.apply("\n".join(entry)))
    print(f"package:     {out}")
    print(f"reviewers:   {len(roster_out)} ({sum(r['status'] == 'OK' for r in roster_out)} OK, {sum(r['status'] != 'OK' for r in roster_out)} MISSING)")
    print(f"identifiers: {red.counts} (known: {red.known})")
    print(f"secret scan: {len(findings)} findings (best-effort; absence of findings proves nothing)")
    print(f"SHA256SUMS:  {sums_hash} over {n} files")
    for l in limitations:
        print(f"limitation:  {l}")
    if problems:
        print("FAILED CHECKS:\n  " + "\n  ".join(problems))
        sys.exit(2)
    print("checks:      every JSONL line parses; no detected identifier remains")


# ---------------------------------------------------------------- subcommands

def cmd_export(a):
    proj = project_dir()
    if not proj:
        sys.exit("ERROR: no Claude project folder for this repository")
    log = os.path.join(proj, a.session + ".jsonl")
    sub = os.path.join(proj, a.session, "subagents")
    if not os.path.isfile(log):
        sys.exit(f"ERROR: session log not found for session {a.session}")
    roster, source = [], None
    if a.roster:
        data = json.load(open(a.roster, encoding="utf-8"))
        for r in data.get("reviewers", data if isinstance(data, list) else []):
            r = dict(r)
            r["transcript"] = os.path.join(sub, f"agent-{r['id']}.jsonl")
            roster.append(r)
        source = "roster file"
    else:  # documented fallback for runs without a roster: board-reviewer subagents since --since
        for meta in sorted(glob.glob(os.path.join(sub, "agent-*.meta.json"))):
            m = json.load(open(meta, encoding="utf-8"))
            jl = meta[:-len(".meta.json")] + ".jsonl"
            first = next(json_lines(jl), {}).get("timestamp", "") if os.path.isfile(jl) else ""
            if m.get("agentType") == "board-reviewer" and not (a.since and first and first < a.since):
                roster.append({"id": os.path.basename(meta)[6:-10], "perspective": m.get("description"), "agent_type": "board-reviewer",
                               "enforcement": "tool", "transcript": jl})
        source = "FALLBACK: no roster; board-reviewer subagents started at/after --since (fallback-type reviewers cannot be found this way)"
        if not roster:
            sys.exit("ERROR: export blocked: no roster and no board-reviewer transcripts; report this to the researcher")
    now = datetime.datetime.now()
    out = a.out or os.path.join(ARCHIVE, now.strftime("%Y-%m-%d"), f"{slug(a.label)}_{now.strftime('%H%M')}")
    build_package({
        "out": out, "label": a.label, "date": now.strftime("%Y-%m-%d"), "question": a.question, "kind": "live",
        "roster": roster, "roster_source": source, "brief": a.brief, "report": a.report,
        "parent_segment": {"path": log, "since": a.since, "until": a.until}, "extras": a.extra or [],
        "full_session_log": log if a.full_session_log else None,
        "source_logs": [log] + [r["transcript"] for r in roster], "isolation_status": a.isolation_status,
        "current_session": a.session,
    })


def cmd_package(a):
    spec = json.load(open(a.spec, encoding="utf-8"))
    build_package(spec)


def cmd_archive_source(a):
    src, dest = os.path.abspath(a.source), os.path.abspath(a.dest)
    if not os.path.isdir(src):
        sys.exit(f"ERROR: source not found: {src}")
    if os.path.exists(dest):
        sys.exit(f"ERROR: {dest} exists; never overwrite")
    inventory = []
    for p in text_files(src):
        st = os.stat(p)
        inventory.append({"file": os.path.relpath(p, src).replace(os.sep, "/"), "bytes": st.st_size, "sha256": sha256(p),
                          "modified": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    shutil.copytree(src, os.path.join(dest, "source_as_found"))
    mism = [x["file"] for x in inventory if sha256(os.path.join(dest, "source_as_found", x["file"])) != x["sha256"]]
    home = os.path.expanduser("~")
    shown = "%USERPROFILE%" + src[len(home):] if src.lower().startswith(home.lower()) else src
    findings = []
    for x in inventory:  # report-only secret scan of the preserved source (never modified)
        try:
            secret_scan(open(os.path.join(src, x["file"]), encoding="utf-8").read(), x["file"], findings)
        except UnicodeDecodeError:
            pass
    write(os.path.join(dest, "source_inventory.json"), json.dumps({
        "original_path": shown, "copied": datetime.datetime.now().isoformat(timespec="seconds"),
        "files": inventory, "copy_verified": not mism, "mismatches": mism,
        "source_secret_scan_report_only": {"statement": "Best-effort; absence of findings proves nothing. Source not modified.",
                                           "findings": findings}}, indent=2))
    print(f"source:      {shown} ({len(inventory)} files)")
    print(f"copied to:   {os.path.join(dest, 'source_as_found')}  verified: {not mism}")
    print(f"source scan: {len(findings)} findings (report-only)")
    if mism:
        sys.exit(f"ERROR: copy mismatch: {mism}")
    if a.remove_source_after_verify:
        shutil.rmtree(src)
        print("removed original after verified copy (move complete)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("export", help="package a live Board run")
    e.add_argument("--session", required=True)
    e.add_argument("--label", required=True, help="short run label, e.g. q003_bhairavi")
    e.add_argument("--question", required=True)
    e.add_argument("--roster", help="roster JSON written at launch (SKILL.md section 4)")
    e.add_argument("--brief", required=True)
    e.add_argument("--report", required=True)
    e.add_argument("--since", required=True, help="ISO timestamp of the Board's launch")
    e.add_argument("--until", help="ISO timestamp the Board ended (default: now)")
    e.add_argument("--extra", nargs="*", default=[])
    e.add_argument("--isolation-status", default="NOT RECORDED")
    e.add_argument("--full-session-log", action="store_true", help="OPT-IN: include the complete raw session log")
    e.add_argument("--out")
    e.set_defaults(func=cmd_export)
    p = sp.add_parser("package", help="build a package from a JSON spec")
    p.add_argument("--spec", required=True)
    p.set_defaults(func=cmd_package)
    s = sp.add_parser("archive-source", help="preserve an existing export verbatim with inventory and hashes")
    s.add_argument("--source", required=True)
    s.add_argument("--dest", required=True)
    s.add_argument("--remove-source-after-verify", action="store_true")
    s.set_defaults(func=cmd_archive_source)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
