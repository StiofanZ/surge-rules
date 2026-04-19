#!/usr/bin/env python3
"""Build proxy rule files by merging upstream Loyalsoldier/surge-rules with local sources.

Produces two output files:
  - proxy.txt  : Surge DOMAIN-SET format (for `DOMAIN-SET,...` directive)
                   * bare domain      -> exact match
                   * leading-dot (.d) -> exact + all subdomains
  - proxy.list : Surge RULE-SET format (for `RULE-SET,...` directive)
                   * `.example.com`   -> `DOMAIN-SUFFIX,example.com`
                   * `example.com`    -> `DOMAIN,example.com`

Surge mobile rejects leading-dot plain lines when the config uses
`RULE-SET,...` -- that directive requires a rule-type prefix on every line.
Publishing both formats lets the user pick whichever directive their
Surge config uses without editing it.

Dedup rules:
  - If `.example.com` exists, `example.com` AND any `*.example.com` subdomain
    entries are redundant and are dropped.
  - Exact duplicates are collapsed.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import sys
import urllib.request

UPSTREAM_URL = (
    "https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/proxy.txt"
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources"
OUTPUT_DOMAIN_SET = ROOT / "proxy.txt"
OUTPUT_RULE_SET = ROOT / "proxy.list"

REQUEST_TIMEOUT_SECONDS = 30
HTTP_USER_AGENT = "surge-rules-builder/1.0 (+https://github.com/StiofanZ/surge-rules)"


def fetch_upstream(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset)


def parse_domains(text: str) -> list[str]:
    """Extract domain entries from a Surge DOMAIN-SET text blob.

    Keeps leading dots. Strips comments (# ...) and blank lines.
    Lowercases for canonical comparison.
    """
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
        out.append(line.lower())
    return out


def dedupe(domains: list[str]) -> list[str]:
    """Remove entries made redundant by a broader domain-suffix rule.

    If `.example.com` is present, drop `foo.example.com` and `example.com`.
    Exact duplicates are also removed.
    """
    suffixes: set[str] = {d[1:] for d in domains if d.startswith(".")}

    kept: set[str] = set()
    for d in domains:
        bare = d[1:] if d.startswith(".") else d
        parts = bare.split(".")
        covered = False
        # Check strictly broader suffixes: any parent label sequence.
        start = 1 if d.startswith(".") else 0
        for i in range(start, len(parts)):
            candidate = ".".join(parts[i:])
            if candidate == bare and d.startswith("."):
                continue
            if candidate in suffixes:
                # A parent suffix (or equal suffix for a non-dot entry) covers it.
                covered = True
                break
        if covered:
            continue
        kept.add(d)
    return sorted(kept, key=lambda x: (x.lstrip("."), 0 if x.startswith(".") else 1))


def to_ruleset(domains: list[str]) -> list[str]:
    """Convert DOMAIN-SET entries to Surge RULE-SET lines.

    `.example.com` -> `DOMAIN-SUFFIX,example.com`
    `example.com`  -> `DOMAIN,example.com`
    """
    out: list[str] = []
    for d in domains:
        if d.startswith("."):
            out.append(f"DOMAIN-SUFFIX,{d[1:]}")
        else:
            out.append(f"DOMAIN,{d}")
    return out


def _common_header(
    *, filename: str, fmt: str, upstream_count: int, local_count: int, total: int
) -> str:
    stamp = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    return (
        f"# Surge {fmt}: {filename}\n"
        f"# Generated: {stamp}\n"
        f"# Upstream: {UPSTREAM_URL}\n"
        "# Supplement: sources/openai-chatgpt.txt "
        "(https://help.openai.com/zh-hans-cn/articles/9247338)\n"
        f"# Counts: upstream={upstream_count}, local={local_count}, total(deduped)={total}\n"
        "# Repo: https://github.com/StiofanZ/surge-rules\n"
    )


def header_domain_set(upstream_count: int, local_count: int, total: int) -> str:
    return (
        _common_header(
            filename="proxy.txt",
            fmt="DOMAIN-SET",
            upstream_count=upstream_count,
            local_count=local_count,
            total=total,
        )
        + "#\n"
        "# Use in Surge config: DOMAIN-SET,<url>,<policy>\n"
        "# Format:\n"
        "#   example.com   -> exact match\n"
        "#   .example.com  -> exact + all subdomains\n"
        "\n"
    )


def header_rule_set(upstream_count: int, local_count: int, total: int) -> str:
    return (
        _common_header(
            filename="proxy.list",
            fmt="RULE-SET",
            upstream_count=upstream_count,
            local_count=local_count,
            total=total,
        )
        + "#\n"
        "# Use in Surge config: RULE-SET,<url>,<policy>\n"
        "# Format:\n"
        "#   DOMAIN,example.com        -> exact match\n"
        "#   DOMAIN-SUFFIX,example.com -> exact + all subdomains\n"
        "\n"
    )


def main() -> int:
    print(f"[build] fetching upstream: {UPSTREAM_URL}", file=sys.stderr)
    try:
        upstream_text = fetch_upstream(UPSTREAM_URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[build] ERROR: upstream fetch failed: {exc}", file=sys.stderr)
        return 1

    upstream = parse_domains(upstream_text)
    print(f"[build] upstream entries: {len(upstream)}", file=sys.stderr)

    local: list[str] = []
    if SOURCES_DIR.is_dir():
        for path in sorted(SOURCES_DIR.glob("*.txt")):
            chunk = parse_domains(path.read_text(encoding="utf-8"))
            print(f"[build] local {path.name}: {len(chunk)}", file=sys.stderr)
            local.extend(chunk)

    combined = upstream + local
    deduped = dedupe(combined)
    print(f"[build] deduped total: {len(deduped)}", file=sys.stderr)

    domain_set_header = header_domain_set(len(upstream), len(local), len(deduped))
    OUTPUT_DOMAIN_SET.write_text(
        domain_set_header + "\n".join(deduped) + "\n", encoding="utf-8"
    )
    print(f"[build] wrote {OUTPUT_DOMAIN_SET.relative_to(ROOT)}", file=sys.stderr)

    rule_set_header = header_rule_set(len(upstream), len(local), len(deduped))
    ruleset_lines = to_ruleset(deduped)
    OUTPUT_RULE_SET.write_text(
        rule_set_header + "\n".join(ruleset_lines) + "\n", encoding="utf-8"
    )
    print(f"[build] wrote {OUTPUT_RULE_SET.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
