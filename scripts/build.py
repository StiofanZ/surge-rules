#!/usr/bin/env python3
"""Build Surge rule files from upstream sources + local supplements.

For each configured rule set we produce TWO files:
  - <name>.txt  : Surge DOMAIN-SET format (for `DOMAIN-SET,...` directive)
                    * bare domain       -> exact match
                    * leading-dot (.d)  -> exact + all subdomains
  - <name>.list : Surge RULE-SET format (for `RULE-SET,...` directive)
                    * `.example.com`    -> `DOMAIN-SUFFIX,example.com`
                    * `example.com`     -> `DOMAIN,example.com`

Surge mobile rejects leading-dot plain lines when the config uses
`RULE-SET,...` -- that directive requires a rule-type prefix on every line.
Publishing both formats lets the user pick whichever directive their Surge
config uses without editing it.

Supported upstream parsers:
  - "domain_set" : Surge DOMAIN-SET (the Loyalsoldier format).
  - "adguard"    : AdGuard/ABP adblock syntax. Only pure `||domain^` rules
                   with safe (DNS-compatible) modifiers are extracted;
                   cosmetic, path, regex, allow-list, and resource-type
                   rules are dropped.
  - "v2fly"      : v2fly/domain-list-community text source. Recognizes
                   bare domains (suffix match), ``domain:`` prefix (suffix),
                   ``full:`` prefix (exact). Drops ``keyword:`` / ``regexp:``
                   (Surge DOMAIN-SET cannot express them). ``include:other``
                   lines recursively fetch the sibling file under the same
                   ``data/`` directory. This is the same source sing-geosite
                   uses to compile its .srs files, which lets us avoid a
                   binary SRS decoder.

Dedup rules (applied per rule set):
  - If `.example.com` exists, `example.com` AND any `*.example.com` subdomain
    entries are redundant and are dropped.
  - Exact duplicates are collapsed.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources"

REQUEST_TIMEOUT_SECONDS = 30
HTTP_USER_AGENT = "surge-rules-builder/1.0"


@dataclasses.dataclass(frozen=True)
class Source:
    url: str
    parser: str  # "domain_set" | "adguard"


@dataclasses.dataclass(frozen=True)
class RuleSet:
    name: str
    description: str
    sources: tuple[Source, ...]
    local_dir: str | None  # subdirectory under sources/, or None
    output_domain_set: str  # e.g. "proxy.txt"
    output_rule_set: str  # e.g. "proxy.list"


RULE_SETS: tuple[RuleSet, ...] = (
    RuleSet(
        name="proxy",
        description=(
            "Domains that should go through a proxy. Upstream Loyalsoldier/surge-rules "
            "proxy.txt plus local OpenAI/ChatGPT allowlist supplement."
        ),
        sources=(
            Source(
                url="https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/proxy.txt",
                parser="domain_set",
            ),
        ),
        local_dir="proxy",
        output_domain_set="proxy.txt",
        output_rule_set="proxy.list",
    ),
    RuleSet(
        name="reject",
        description=(
            "Ad / tracking / crypto-miner domains to reject. Aggregated from every "
            "domain-oriented section across AdguardTeam/AdguardFilters: BaseFilter, "
            "MobileFilter, ChineseFilter, JapaneseFilter (adservers + adservers_firstparty); "
            "SpywareFilter (tracking_servers + tracking_servers_firstparty + mobile); "
            "plus BaseFilter cryptominers. Cosmetic, URL-path, regex, allowlist, and "
            "resource-type-conditional rules are dropped by the parser."
        ),
        sources=(
            # Ad servers (third-party ad networks).
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/BaseFilter/sections/adservers.txt",
                parser="adguard",
            ),
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/MobileFilter/sections/adservers.txt",
                parser="adguard",
            ),
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/ChineseFilter/sections/adservers.txt",
                parser="adguard",
            ),
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/JapaneseFilter/sections/adservers.txt",
                parser="adguard",
            ),
            # First-party ad servers (subdomains under otherwise-legitimate sites).
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/BaseFilter/sections/adservers_firstparty.txt",
                parser="adguard",
            ),
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/ChineseFilter/sections/adservers_firstparty.txt",
                parser="adguard",
            ),
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/JapaneseFilter/sections/adservers_firstparty.txt",
                parser="adguard",
            ),
            # Trackers / analytics / mobile tracking.
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/SpywareFilter/sections/tracking_servers.txt",
                parser="adguard",
            ),
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/SpywareFilter/sections/tracking_servers_firstparty.txt",
                parser="adguard",
            ),
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/SpywareFilter/sections/mobile.txt",
                parser="adguard",
            ),
            # Crypto-miners.
            Source(
                url="https://raw.githubusercontent.com/AdguardTeam/AdguardFilters/master/BaseFilter/sections/cryptominers.txt",
                parser="adguard",
            ),
            # v2fly/domain-list-community `category-ads-all` (the source
            # SagerNet/sing-geosite compiles `geosite-category-ads-all.srs`
            # from). Recursively follows `include:` directives so we pick up
            # category-ads plus every branded subcategory (adjust, clearbit,
            # growingio, ogury, openx, pubmatic, segment, supersonic, taboola,
            # ...) without listing each one explicitly.
            Source(
                url="https://raw.githubusercontent.com/v2fly/domain-list-community/master/data/category-ads-all",
                parser="v2fly",
            ),
        ),
        local_dir="reject",
        output_domain_set="reject.txt",
        output_rule_set="reject.list",
    ),
)


# ------------------------------ fetch ------------------------------


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset)


# ------------------------------ parsers ------------------------------


def parse_domain_set(text: str) -> list[str]:
    """Extract entries from a Surge DOMAIN-SET text blob.

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


# AdGuard modifiers safe to ignore at DNS level: either pure-markers or contexts
# that still mean "block this whole domain" for DNS-based rule sets.
_ADGUARD_SAFE_MODIFIERS = frozenset({"third-party", "3p", "all", "important", "popup"})
_ADGUARD_DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"
)
# IPv4 literal (Surge DOMAIN-SET does not accept IP entries).
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def parse_adguard(text: str) -> list[str]:
    """Extract domain-suffix rules from an AdGuard/ABP filter blob.

    Recognized: ``||example.com^`` [with optional $safe-modifier list].
    Rejected:
      - ``!`` comment lines
      - ``@@`` allowlist exceptions
      - cosmetic / scriptlet (``##``, ``#@#``, ``#?#``, ``#$#``, ``#%#``)
      - URL parts (``/path/``, ``|http://...``)
      - regex (``/.../``)
      - wildcards inside the domain (``*`` before ``^``)
      - rules with context-dependent modifiers (``$domain=``, ``$script`` etc.)

    Returns leading-dot suffix entries (e.g. ``.example.com``), which means
    "match example.com and all subdomains" in Surge DOMAIN-SET.
    """
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("!") or line.startswith("#"):
            continue
        if line.startswith("@@"):
            continue  # allowlist exception
        if any(tok in line for tok in ("##", "#@#", "#?#", "#$#", "#%#", "$$")):
            continue  # cosmetic / scriptlet / html filter
        if not line.startswith("||"):
            continue  # not a domain-anchored rule
        body = line[2:]  # strip leading ||
        if "$" in body:
            rule_part, mod_part = body.split("$", 1)
        else:
            rule_part, mod_part = body, ""
        if not rule_part.endswith("^"):
            continue
        domain = rule_part[:-1]
        if not domain:
            continue
        if "/" in domain or ":" in domain or "*" in domain or "?" in domain:
            continue
        domain = domain.lower()
        if not _ADGUARD_DOMAIN_RE.match(domain):
            continue
        if _IPV4_RE.match(domain):
            continue  # IPv4 literal -- Surge DOMAIN-SET is domain-only
        if mod_part:
            mods = [m.strip() for m in mod_part.split(",") if m.strip()]
            bad = False
            for m in mods:
                name = m[1:] if m.startswith("~") else m
                name = name.split("=", 1)[0]
                if name not in _ADGUARD_SAFE_MODIFIERS:
                    bad = True
                    break
            if bad:
                continue
        out.append("." + domain)
    return out


_V2FLY_ATTR_RE = re.compile(r"@([A-Za-z0-9_-]+)")
_V2FLY_BARE_DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"
)


def _parse_v2fly_line(line: str) -> tuple | None:
    """Classify one non-empty, non-comment v2fly line.

    Returns one of:
      ("include", target, frozenset[str])       -- an ``include:other`` directive
                                                   with optional filter tags
                                                   (e.g. ``include:apple @ads``).
      ("domain", ".foo"|"foo", frozenset[str])  -- a terminal rule with its own
                                                   attribute tags.
      None                                       -- unusable for Surge DOMAIN-SET.
    """
    tags = frozenset(_V2FLY_ATTR_RE.findall(line))
    line = _V2FLY_ATTR_RE.sub("", line).strip()
    if not line:
        return None
    if line.startswith("include:"):
        target = line[len("include:") :].strip().split()[0]  # strip trailing tokens
        return ("include", target, tags) if target else None
    if line.startswith("keyword:") or line.startswith("regexp:"):
        return None
    exact = False
    if line.startswith("full:"):
        exact = True
        line = line[len("full:") :]
    elif line.startswith("domain:"):
        line = line[len("domain:") :]
    line = line.strip().lower()
    if not _V2FLY_BARE_DOMAIN_RE.match(line):
        return None
    if _IPV4_RE.match(line):
        return None
    return ("domain", line if exact else "." + line, tags)


def parse_v2fly(text: str) -> list[str]:
    """Extract suffix/exact rules from a single v2fly text blob.

    Ignores ``include:`` directives -- the pipeline calls
    ``fetch_v2fly_recursive`` when attribute-aware recursion is desired.
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
        parsed = _parse_v2fly_line(line)
        if parsed is None or parsed[0] != "domain":
            continue
        out.append(parsed[1])
    return out


_V2FLY_MAX_DEPTH = 8


def fetch_v2fly_recursive(url: str) -> list[str]:
    """Fetch a v2fly file and transitively its ``include:`` siblings.

    Supports v2fly attribute filtering semantics. When a file is entered via
    ``include:target @foo``, only terminal rules that carry the ``@foo`` tag
    are emitted; un-tagged bulk rules of the target are skipped. Filters
    compose (intersect) through nested includes -- e.g. ``include:X @ads`` in
    a caller that already requires ``@cn`` emits only terminals tagged
    ``@ads AND @cn``.
    """
    text_cache: dict[str, str] = {}
    in_progress: set[tuple[str, frozenset[str]]] = set()
    out: list[str] = []

    def _walk(target_url: str, required_tags: frozenset[str], depth: int) -> None:
        key = (target_url, required_tags)
        if depth > _V2FLY_MAX_DEPTH or key in in_progress:
            return
        in_progress.add(key)
        filt_label = ",".join(sorted(required_tags)) if required_tags else "*"
        print(
            f"  [v2fly] fetch (depth {depth}, tags=[{filt_label}]): {target_url}",
            file=sys.stderr,
        )
        text = text_cache.get(target_url)
        if text is None:
            try:
                text = fetch(target_url)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"  [v2fly] WARN: include fetch failed ({exc}): {target_url}",
                    file=sys.stderr,
                )
                return
            text_cache[target_url] = text
        base = target_url.rsplit("/", 1)[0] + "/"
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "#" in line:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
            parsed = _parse_v2fly_line(line)
            if parsed is None:
                continue
            kind = parsed[0]
            if kind == "include":
                _, target, child_tags = parsed
                _walk(base + target, required_tags | child_tags, depth + 1)
            else:
                _, value, line_tags = parsed
                # Terminal rule passes iff its tag set is a superset of the
                # active required_tags filter (empty required_tags = pass-through).
                if required_tags and not required_tags.issubset(line_tags):
                    continue
                out.append(value)

    _walk(url, frozenset(), 0)
    return out


_PARSERS: dict[str, object] = {
    "domain_set": parse_domain_set,
    "adguard": parse_adguard,
    "v2fly": parse_v2fly,
}


# ------------------------------ dedupe ------------------------------


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
        start = 1 if d.startswith(".") else 0
        for i in range(start, len(parts)):
            candidate = ".".join(parts[i:])
            if candidate == bare and d.startswith("."):
                continue
            if candidate in suffixes:
                covered = True
                break
        if covered:
            continue
        kept.add(d)
    return sorted(kept, key=lambda x: (x.lstrip("."), 0 if x.startswith(".") else 1))


# ------------------------------ emitters ------------------------------


def to_ruleset(domains: list[str]) -> list[str]:
    """Convert DOMAIN-SET entries to Surge RULE-SET lines."""
    out: list[str] = []
    for d in domains:
        if d.startswith("."):
            out.append(f"DOMAIN-SUFFIX,{d[1:]}")
        else:
            out.append(f"DOMAIN,{d}")
    return out


def _timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _source_lines(rs: RuleSet) -> str:
    lines = ["# Sources:"]
    for s in rs.sources:
        lines.append(f"#   [{s.parser}] {s.url}")
    if rs.local_dir:
        local_root = SOURCES_DIR / rs.local_dir
        if local_root.is_dir():
            for p in sorted(local_root.glob("*.txt")):
                lines.append(f"#   [local] sources/{rs.local_dir}/{p.name}")
    return "\n".join(lines) + "\n"


def _common_header(
    *,
    rs: RuleSet,
    filename: str,
    fmt: str,
    upstream: int,
    local: int,
    total: int,
) -> str:
    return (
        f"# Surge {fmt}: {filename} ({rs.name})\n"
        f"# Description: {rs.description}\n"
        f"# Generated: {_timestamp()}\n"
        f"{_source_lines(rs)}"
        f"# Counts: upstream={upstream}, local={local}, total(deduped)={total}\n"
    )


def header_domain_set(rs: RuleSet, upstream: int, local: int, total: int) -> str:
    return (
        _common_header(
            rs=rs,
            filename=rs.output_domain_set,
            fmt="DOMAIN-SET",
            upstream=upstream,
            local=local,
            total=total,
        )
        + "#\n"
        f"# Use in Surge config: DOMAIN-SET,<url>,{rs.name.upper()}\n"
        "# Format:\n"
        "#   example.com   -> exact match\n"
        "#   .example.com  -> exact + all subdomains\n"
        "\n"
    )


def header_rule_set(rs: RuleSet, upstream: int, local: int, total: int) -> str:
    return (
        _common_header(
            rs=rs,
            filename=rs.output_rule_set,
            fmt="RULE-SET",
            upstream=upstream,
            local=local,
            total=total,
        )
        + "#\n"
        f"# Use in Surge config: RULE-SET,<url>,{rs.name.upper()}\n"
        "# Format:\n"
        "#   DOMAIN,example.com        -> exact match\n"
        "#   DOMAIN-SUFFIX,example.com -> exact + all subdomains\n"
        "\n"
    )


# ------------------------------ pipeline ------------------------------


def _read_local(rs: RuleSet) -> list[str]:
    """Read local supplement files. Each file is parsed as DOMAIN-SET."""
    if not rs.local_dir:
        return []
    local_root = SOURCES_DIR / rs.local_dir
    if not local_root.is_dir():
        return []
    out: list[str] = []
    for path in sorted(local_root.glob("*.txt")):
        chunk = parse_domain_set(path.read_text(encoding="utf-8"))
        print(
            f"[{rs.name}] local sources/{rs.local_dir}/{path.name}: {len(chunk)}",
            file=sys.stderr,
        )
        out.extend(chunk)
    return out


def build_rule_set(rs: RuleSet) -> int:
    """Fetch, parse, dedupe, and emit one rule set. Returns 0 on success, 1 on failure."""
    upstream_entries: list[str] = []
    for src in rs.sources:
        print(f"[{rs.name}] fetching {src.parser} source: {src.url}", file=sys.stderr)
        try:
            if src.parser == "v2fly":
                # v2fly needs recursive `include:` resolution; the resolver
                # does its own fetching, so skip the generic fetch-then-parse
                # path.
                chunk = fetch_v2fly_recursive(src.url)
            else:
                text = fetch(src.url)
                parser = _PARSERS[src.parser]
                chunk = parser(text)  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001
            print(
                f"[{rs.name}] ERROR: fetch failed for {src.url}: {exc}", file=sys.stderr
            )
            return 1
        print(
            f"[{rs.name}] parsed {len(chunk)} entries from {src.url}", file=sys.stderr
        )
        upstream_entries.extend(chunk)

    local_entries = _read_local(rs)
    combined = upstream_entries + local_entries
    deduped = dedupe(combined)
    print(
        f"[{rs.name}] upstream={len(upstream_entries)}, local={len(local_entries)}, "
        f"deduped={len(deduped)}",
        file=sys.stderr,
    )

    upstream_n, local_n, total_n = (
        len(upstream_entries),
        len(local_entries),
        len(deduped),
    )

    out_ds = ROOT / rs.output_domain_set
    out_ds.write_text(
        header_domain_set(rs, upstream_n, local_n, total_n)
        + "\n".join(deduped)
        + "\n",
        encoding="utf-8",
    )
    print(f"[{rs.name}] wrote {out_ds.relative_to(ROOT)}", file=sys.stderr)

    out_rs = ROOT / rs.output_rule_set
    out_rs.write_text(
        header_rule_set(rs, upstream_n, local_n, total_n)
        + "\n".join(to_ruleset(deduped))
        + "\n",
        encoding="utf-8",
    )
    print(f"[{rs.name}] wrote {out_rs.relative_to(ROOT)}", file=sys.stderr)
    return 0


def main() -> int:
    rc = 0
    for rs in RULE_SETS:
        rc |= build_rule_set(rs)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
