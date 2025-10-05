#!/usr/bin/env python3
"""Fail the build when docs/CHANGE_LOG.md is not updated on pull requests."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from typing import List

CHANGELOG_PATH = pathlib.Path("docs/CHANGE_LOG.md")


def _run_git_diff(range_spec: str) -> List[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", range_spec],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    if os.getenv("ALLOW_MISSING_CHANGELOG", "").lower() in {"1", "true", "yes"}:
        print("Skipping changelog enforcement because ALLOW_MISSING_CHANGELOG is set.")
        return 0

    if not CHANGELOG_PATH.exists():
        print("docs/CHANGE_LOG.md is missing from the repository", file=sys.stderr)
        return 1

    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    base_ref = os.getenv("GITHUB_BASE_REF")
    if event_name and event_name != "pull_request":
        print(f"Skipping changelog enforcement for event {event_name}.")
        return 0

    if not base_ref:
        sha = os.getenv("GITHUB_SHA")
        if not sha:
            print("No base reference or SHA available; skipping changelog check.")
            return 0
        range_spec = "HEAD^...HEAD"
    else:
        range_spec = f"origin/{base_ref}...HEAD"

    try:
        changed_files = _run_git_diff(range_spec)
    except subprocess.CalledProcessError as exc:
        print(f"Unable to evaluate changed files for {range_spec}: {exc.stderr}", file=sys.stderr)
        return 1

    if not changed_files:
        print("No files changed in the diff range; skipping changelog check.")
        return 0

    changelog_str = str(CHANGELOG_PATH)
    if changelog_str not in changed_files:
        print(
            "docs/CHANGE_LOG.md must be updated for this pull request.",
            file=sys.stderr,
        )
        print("Changed files:", file=sys.stderr)
        for path in changed_files:
            print(f"  - {path}", file=sys.stderr)
        return 1

    print("Changelog entry detected; enforcement passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())