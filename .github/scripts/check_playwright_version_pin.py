#!/usr/bin/env python3
"""Fail if a Dockerfile's Playwright base-image tag and PLAYWRIGHT_VERSION drift.

A Playwright boefje image pins the base by `FROM …/playwright:vX.Y.Z-…` and the npm
package + browser by `ARG PLAYWRIGHT_VERSION=X.Y.Z`; they must be the same version
(see kat_webpage_capture/boefje.Dockerfile and PR #5333). Dependabot's docker
ecosystem bumps only the `FROM` tag + digest — it cannot touch the `ARG` — so a bump
silently leaves the package and browser behind at the old version (PR #5334). This
guard makes that drift a red `pre-commit` check instead of a no-op "upgrade".

Runs as a pre-commit hook over boefje.Dockerfile paths; a Dockerfile without both a
Playwright base image and a PLAYWRIGHT_VERSION arg is ignored.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FROM_RE = re.compile(r"^FROM\s+\S*/playwright:v(\d+\.\d+\.\d+)", re.MULTILINE)
ARG_RE = re.compile(r"^ARG\s+PLAYWRIGHT_VERSION=(\d+\.\d+\.\d+)", re.MULTILINE)


def check(path: str) -> str | None:
    text = Path(path).read_text(encoding="utf-8")

    from_versions = FROM_RE.findall(text)
    arg_versions = ARG_RE.findall(text)
    if not from_versions or not arg_versions:
        return None  # not a version-pinned Playwright Dockerfile

    base, arg = from_versions[0], arg_versions[0]
    if base != arg:
        return (
            f"{path}: Playwright base image v{base} does not match "
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
