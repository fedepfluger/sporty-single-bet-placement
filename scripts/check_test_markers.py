#!/usr/bin/env python3
"""Every test must belong to exactly one suite.

CI runs `-m smoke` on pull requests and `-m regression` nightly, so a test marked
with neither is never executed by anything: it looks like coverage on the report
and is dead weight in reality. One marked with both makes the smoke gate as slow
as the full run. Neither mistake fails a normal `pytest` invocation, which is why
it is worth a guard.

The check is two pytest collections rather than source parsing, so markers are
seen exactly as the test run sees them - including ones applied through
`pytestmark`, a conftest, or a collection hook. Collecting also proves every test
module still imports and parametrises, so a broken file fails here too.
"""

from __future__ import annotations

import subprocess
import sys

#: pytest's exit code for "no tests matched", which is the passing case for us.
NO_TESTS_COLLECTED = 5

CHECKS = {
    "not smoke and not regression": "carry no suite marker, so nothing ever runs them",
    "smoke and regression": "carry both suite markers, so the smoke gate pays for them twice",
}


def collect(expression: str) -> subprocess.CompletedProcess[str]:
    # `-o addopts=` clears the ini defaults first. Without it pytest.ini's `-v`
    # overrides `-q`, the output becomes a `<Function ...>` tree instead of node
    # ids, and the parsing below silently finds nothing - a check that always passes.
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-m",
            expression,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    problems = 0

    for expression, complaint in CHECKS.items():
        result = collect(expression)

        if result.returncode == NO_TESTS_COLLECTED:
            continue

        if result.returncode != 0:
            print(f"pytest could not collect the suite (exit {result.returncode}):\n")
            print(result.stdout[-3000:] or result.stderr[-3000:])
            return 1

        names = [line for line in result.stdout.splitlines() if line.startswith("tests/")]
        print(f'These tests {complaint}  [-m "{expression}"]:\n')
        print("\n".join(f"  {name}" for name in names))
        print()
        problems += len(names)

    if problems:
        print("Give each of them exactly one of @pytest.mark.smoke / @pytest.mark.regression.")
        return 1

    print("All tests are assigned to exactly one suite.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
