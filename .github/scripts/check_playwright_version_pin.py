#!/usr/bin/env python3
"""Fail if a Dockerfile's Playwright base-image tag and PLAYWRIGHT_VERSION drift.

A Playwright boefje image pins the base by `FROM …/playwright:vX.Y.Z-…` and the npm
package + browser by `ARG PLAYWRIGHT_VERSION=X.Y.Z`; they must be the same version
(see kat_webpage_capture/boefje.Dockerfile and PR #5333). Dependabot's docker
ecosystem bumps only the `FROM` tag + digest — it cannot touch the `ARG` — so a bump
silently leaves the package and browser behind at the old version (PR #5334). This
guard makes that drift a red `pre-commit` check instead of a no-op "upgrade".

Scope: the pre-commit hook targets `kat_webpage_capture/boefje.Dockerfile` (the only
Playwright-pinned image today; add a path when another appears). The script itself stays
general — a file it is handed is checked when it references a Playwright base image or
declares `PLAYWRIGHT_VERSION`, and ignored otherwise. The check is fail-closed: if such a
file is present but a version can't be parsed from both the `FROM` tag and the `ARG`,
that is an error, not a skip, so a reformat that outruns these regexes can't silently
disable the guard.

Boundary: this compares the human-readable `:vX.Y.Z` tag against the arg. It does not
resolve the `@sha256:` digest to a version (that needs a registry pull); Dependabot is
relied on to keep the tag and digest consistent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# A Playwright base image, capturing the tag version. Matches `.../playwright:vX.Y.Z`.
FROM_RE = re.compile(r"^FROM\s+\S*/playwright:v(\d+\.\d+\.\d+)", re.MULTILINE)
# The value-bearing PLAYWRIGHT_VERSION arg (quotes optional; a bare redeclare has none).
ARG_RE = re.compile(r"""^ARG\s+PLAYWRIGHT_VERSION=["']?(\d+\.\d+\.\d+)["']?""", re.MULTILINE)
# Markers that put a Dockerfile in scope even if a version can't be parsed (fail-closed).
PLAYWRIGHT_FROM_MARKER = re.compile(r"^FROM\s+\S*playwright\b", re.MULTILINE)
ARG_MARKER = re.compile(r"^ARG\s+PLAYWRIGHT_VERSION\b", re.MULTILINE)


def check(path: str) -> str | None:
    text = Path(path).read_text(encoding="utf-8")

    if not PLAYWRIGHT_FROM_MARKER.search(text) and not ARG_MARKER.search(text):
        return None  # not a Playwright-pinned Dockerfile

    from_versions = FROM_RE.findall(text)
    arg_versions = ARG_RE.findall(text)
    if not from_versions or not arg_versions:
        return (
            f"{path}: pins Playwright but a vX.Y.Z version could not be parsed from both the "
            f"FROM tag and ARG PLAYWRIGHT_VERSION. Keep both in the pinned `:vX.Y.Z` / "
            f"`PLAYWRIGHT_VERSION=X.Y.Z` form so the version stays machine-verifiable."
        )

    arg = arg_versions[0]
    mismatched = sorted({version for version in from_versions if version != arg})
    if mismatched:
        return (
            f"{path}: Playwright base image v{'/v'.join(mismatched)} does not match "
            f"ARG PLAYWRIGHT_VERSION={arg}. Bump the FROM tag, its digest and "
            f"PLAYWRIGHT_VERSION together (Dependabot only bumps the FROM tag)."
        )
    return None


def main(argv: list[str]) -> int:
    exit_code = 0
    for path in argv[1:]:
        error = check(path)
        if error:
            sys.stderr.write(error + "\n")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
