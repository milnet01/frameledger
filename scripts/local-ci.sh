#!/usr/bin/env bash
# THE CI GATE. One list of steps, run in two places.
#
# `.github/workflows/ci.yml` CALLS this file and restates none of it. That is
# the whole point (`local-gate.md` § 3): two lists of steps drift the first
# time someone edits one of them, and the drift surfaces as a red build on a
# push — which is exactly what running locally was meant to prevent. A
# hand-written mirror is correct on the day it is written and wrong after.
#
# So: to change what CI does, change THIS FILE. Never add a step to the
# workflow.
#
# Usage:
#   ./scripts/local-ci.sh           the full gate
#   ./scripts/local-ci.sh --docs    the checks that do not need a build
#   ./scripts/local-ci.sh --docs-glob   print what counts as documentation
#
# WHY --docs EXISTS, AND WHY IT IS NOT A SKIP. Rebuilding and re-testing to fix
# a prose typo is how a person learns to reach for --no-verify. So --docs omits
# only the legs that need a compiler or a full environment, and NOTHING ELSE:
# every check that can run without one runs in both modes. A mode cheaper than
# the pipeline is fine; a mode that checks LESS of what the pipeline checks is
# a green that lies. The pre-push hook selects it on a documentation-only push.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

# The one definition of what counts as documentation. The pre-push hook reads
# it with `--docs-glob` and does its own matching, so the decision has one home
# as well as one value.
DOCS_GLOB='docs/*|*.md|LICENSE'

# Tool versions are pinned HERE and installed from here by the workflow. A
# version pinned only in the workflow is a second copy: this script would take
# whatever happened to be on PATH, so the same commit could pass locally and
# fail on GitHub. Measured case: ruff's default rule set changed between
# releases, so an unpinned run enforces a different set on each machine.
# RUFF_VERSION='0.16.8'

if [[ ${1:-} == --docs-glob ]]; then printf '%s\n' "$DOCS_GLOB"; exit 0; fi

DOCS_ONLY=0
[[ ${1:-} == --docs ]] && DOCS_ONLY=1

# ── Have you filled anything in yet? ────────────────────────────────────────
# SET THIS TO 1 once the steps below run at least one real check. Until then
# this script reports honestly that it verified nothing.
#
# Why it exists: as shipped, every step below is a commented example, so the
# script ran nothing and printed "all checks passed". A gate that cannot fail
# is worse than no gate — it spends the attention that would have caught the
# defect, and the machine-wide pre-push hook reports its exit 0 as a pass.
# Measured 2026-09-26 on a fresh scaffold.
CONFIGURED=0

step() { printf '\n=== %s ===\n' "$1" >&2; }

# A check whose tool is absent SAYS SO and is never silently dropped: a check
# that did not run must not look like one that passed.
need() {
    command -v "$1" >/dev/null 2>&1 && return 0
    printf 'local-ci: %s is not installed — that check did NOT run\n' "$1" >&2
    return 1
}

# run NAME CMD... — one line for a green step, the log's tail for a red one.
# The full output goes to .git/local-ci/NAME.log, so nothing is lost; a full
# run's output cost each agent session that pushed (CFG-0776). On CI it
# streams, so the workflow's own log keeps everything. A red step still
# stops the gate. A step that skips itself says so with need(), which
# prints directly.
LOG_DIR="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || echo .)/local-ci"
run() {
    local name=$1 log rc=0
    shift
    if [[ ${CI:-} == true ]]; then "$@"; return; fi
    mkdir -p "$LOG_DIR"
    log="$LOG_DIR/$name.log"
    "$@" >"$log" 2>&1 || rc=$?
    if (( rc == 0 )); then
        printf 'ok    %s\n' "$name" >&2
        return 0
    fi
    printf 'FAIL  %s (exit %d) — last 40 lines; full log: %s\n' "$name" "$rc" "$log" >&2
    tail -n 40 "$log" >&2
    return "$rc"
}

# ── Checks that run in BOTH modes ───────────────────────────────────────────
# Anything not needing a compiler or a full environment belongs here.

step 'documentation'
# e.g. need markdownlint && run markdownlint markdownlint .
# e.g. check-doc-facts, link checking, spelling
# SET THIS TO 1 once the documentation step runs a real check. CONFIGURED
# covers the script as a whole, so a project with lint and tests filled in
# still had --docs report a pass that checked nothing (Deedbox, 2026-09-28).
DOCS_CONFIGURED=0

if (( DOCS_ONLY )); then
    if (( CONFIGURED && DOCS_CONFIGURED )); then
        printf '\nlocal-ci: --docs passed; build and test legs skipped by design.\n' >&2
    elif (( CONFIGURED )); then
        printf '\nlocal-ci: --docs ran NO documentation check (none configured) — nothing was verified.\n' >&2
        printf 'local-ci: fill in the documentation step, then set DOCS_CONFIGURED=1.\n' >&2
    else
        printf '\nlocal-ci: NO CHECKS ARE CONFIGURED YET — this run verified nothing.\n' >&2
        printf 'local-ci: fill in the steps above, then set CONFIGURED=1.\n' >&2
    fi
    exit 0
fi

# ── Checks that need a build or a full environment ──────────────────────────

step 'lint'
# e.g. need ruff && run lint ruff check .

step 'types'
# e.g. need mypy && run types mypy

step 'build'
# e.g. run build cmake --build build

step 'test'
# e.g. need pytest && run test pytest -q     |     run test ctest --test-dir build --output-on-failure

if (( CONFIGURED )); then
    printf '\nlocal-ci: all checks passed.\n' >&2
else
    printf '\nlocal-ci: NO CHECKS ARE CONFIGURED YET — this run verified nothing.\n' >&2
    printf 'local-ci: fill in the steps above, then set CONFIGURED=1.\n' >&2
fi
