#!/usr/bin/env python3
"""
fetch_stars.py — Update star counts on every GitHub link in README.md.

Usage:
    python scripts/fetch_stars.py            # update in place
    python scripts/fetch_stars.py --dry-run  # print diff, don't write
    python scripts/fetch_stars.py --zh        # update README.zh.md instead

Reads README.md (or README.zh.md with --zh), finds every markdown link of the
form [name](https://github.com/owner/repo[.git]), queries GitHub for the current
stargazers_count via `gh api`, and rewrites the file so each link is followed by
" ⭐<count>" (or " ⭐<count> ⭐" for the Chinese version, which uses Chinese
"星标" terminology — see --style below).

Style:
    --style ascii   ⭐1234   (default, matches awesome-list convention)
    --style zh      ⭐1234   (same glyph, used by README.zh.md too)

Pitfall we hit: never use str.rstrip(".git") — that strips ANY trailing
character in the set {., g, i, t}, which mangled `wit`→`w`, `wreckit`→`wreck`,
`ralph-tui`→`ralph-tu`. We use a regex suffix-strip instead.

Requires: `gh` CLI authenticated as a user with public-repo read access.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

LINK_RE = re.compile(
    r"\[[^\]]+\]\(https://github\.com/([^/\s)\]]+)/([^/\s)#?\]]+?)(?:\.git)?\)"
)
LINE_RE = re.compile(
    r"^(- \[[^\]]+\]\(https://github\.com/[^/\s)\]]+/[^/\s)#?\]]+?\))(\s*-\s*)",
    re.MULTILINE,
)


def unique_repos(text: str) -> list[str]:
    seen, out = set(), []
    for m in LINK_RE.finditer(text):
        owner, repo = m.group(1), m.group(2)
        key = f"{owner}/{repo}"
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def fetch_star(full: str, timeout: int = 30) -> int | None:
    owner, repo = full.split("/", 1)
    r = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}", "--jq", ".stargazers_count"],
        capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode == 0 and r.stdout.strip().isdigit():
        return int(r.stdout.strip())
    return None


def update_readme(path: Path, dry: bool = False) -> tuple[int, int, list[str]]:
    text = path.read_text(encoding="utf-8")
    repos = unique_repos(text)
    # Exclude self if present
    # (we don't know owner/repo of the file's own repo generically, so skip)
    stars: dict[str, int] = {}
    failed: list[str] = []
    t0 = time.time()
    for i, full in enumerate(repos, 1):
        n = fetch_star(full)
        if n is not None:
            stars[full] = n
        else:
            failed.append(full)
        if i % 20 == 0:
            print(f"  {i}/{len(repos)} fetched ({len(failed)} failed)", file=sys.stderr)
    dt = time.time() - t0
    print(f"  fetched {len(stars)}/{len(repos)} in {dt:.1f}s", file=sys.stderr)

    def repl(m: re.Match) -> str:
        full_link = m.group(1)
        sub = re.search(
            r"github\.com/([^/\s)\]]+)/([^/\s)#?\]]+?)(?:\.git)?\)", full_link
        )
        key = f"{sub.group(1)}/{sub.group(2)}"
        if key in stars:
            return f"{m.group(1)} ⭐{stars[key]}{m.group(2)}"
        return m.group(0)

    new_text, n = LINE_RE.subn(repl, text)
    if not dry:
        path.write_text(new_text, encoding="utf-8", newline="\n")
    return n, len(failed), failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print stats, don't write")
    ap.add_argument("--zh", action="store_true", help="update README.zh.md instead")
    args = ap.parse_args()

    target = Path("README.zh.md" if args.zh else "README.md")
    if not target.exists():
        print(f"error: {target} not found", file=sys.stderr)
        return 1
    n, failed_count, failed = update_readme(target, dry=args.dry_run)
    print(f"{'would update' if args.dry_run else 'updated'} {n} links in {target}")
    if failed:
        print(f"failed to fetch stars for {failed_count}:", file=sys.stderr)
        for f in failed:
            print(f"  {f}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
