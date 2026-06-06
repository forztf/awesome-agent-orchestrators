#!/usr/bin/env python3
"""
sort_by_stars.py — Sort bullet items within each section by star count (desc).

Usage:
    python scripts/sort_by_stars.py             # sort README.md and README.zh.md in place
    python scripts/sort_by_stars.py README.md   # only one file

Reads a README, walks the document, identifies each "section" (delimited by `## `
headers) and within each section sorts the bullet lines (`- [...]`) by the ⭐N
number already in the line. Non-bullet lines (headers, intro paragraphs) keep
their position; only bullet order changes.

Idempotent: running on an already-sorted file is a no-op.

This script does NOT fetch stars. Use fetch_stars.py first if you need fresh
counts.
"""
import re
import sys
from pathlib import Path

STAR_RE = re.compile(r"⭐([\d,]+)")


def sort_file(path: Path) -> int:
    """Sort bullets within each section of `path` in place. Returns count of moved lines."""
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # Walk lines, group into sections. A "section" starts at a `## ` header and
    # runs until the next `## ` header (or EOF). Non-bullet lines pass through
    # untouched; runs of bullet lines get sorted together (split by blank lines
    # so a single section can hold multiple "paragraphs" of bullets).
    out: list[str] = []
    moved = 0
    section_lines: list[str] = []  # current run of non-section-header lines
    in_section = False

    def flush_run():
        nonlocal moved
        # Pull out contiguous bullet lines; sort them; put back.
        nonlocal section_lines
        if not section_lines:
            return
        # Find runs of bullets separated by non-bullet lines.
        result: list[str] = []
        buf: list[str] = []
        for ln in section_lines:
            if ln.lstrip().startswith("- "):
                buf.append(ln)
            else:
                if len(buf) > 1:
                    buf_sorted = sorted(
                        buf,
                        key=lambda b: -int(STAR_RE.search(b).group(1).replace(",", ""))
                        if STAR_RE.search(b) else 0,
                    )
                    if buf != buf_sorted:
                        moved += len(buf)
                    result.extend(buf_sorted)
                    buf = []
                else:
                    if buf:
                        result.extend(buf)
                        buf = []
                result.append(ln)
        if buf:
            if len(buf) > 1:
                buf_sorted = sorted(
                    buf,
                    key=lambda b: -int(STAR_RE.search(b).group(1).replace(",", ""))
                    if STAR_RE.search(b) else 0,
                )
                if buf != buf_sorted:
                    moved += len(buf)
                result.extend(buf_sorted)
            else:
                result.extend(buf)
        section_lines.clear()
        out.extend(result)

    for ln in lines:
        if ln.startswith("## "):
            # New section: flush the previous one's content
            flush_run()
            out.append(ln)
            in_section = True
        else:
            if in_section:
                section_lines.append(ln)
            else:
                out.append(ln)

    flush_run()

    new_text = "\n".join(out)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8", newline="\n")
    return moved


def main(argv: list[str]) -> int:
    targets = (
        [Path(a) for a in argv[1:]]
        if len(argv) > 1
        else [Path("README.md"), Path("README.zh.md")]
    )
    for t in targets:
        if not t.exists():
            print(f"skip: {t} not found", file=sys.stderr)
            continue
        moved = sort_file(t)
        print(f"  {t}: moved {moved} bullet lines")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
