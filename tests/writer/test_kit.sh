#!/usr/bin/env bash
# The kit's C leg: docs/specs/FLED-0001-run-file-format.md § 4.19, INV-116.
#
# scripts/make_kit.py turns each case's JSON into calls on
# include/frameledger.h, builds them and runs them, under each toolchain
# that runs its programs here. Each file it writes must be the case's
# NAME.csv byte for byte; when it is not, `check --expect` names the
# difference. So a writer change that alters a kit file fails here until
# the kit is made again and the change shows in its diff. On Linux
# mingw-w64 is build-only, so it runs no case.
#
# Usage: tests/writer/test_kit.sh
# PYTHON names the interpreter (default python3). A compiler that is not
# installed fails the run: a check that did not run must not read as a pass.
set -Eeuo pipefail
cd "$(dirname "$0")/../.."

PYTHON=${PYTHON:-python3}
# shellcheck source=tests/writer/toolchains.sh
source tests/writer/toolchains.sh

out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
failed=0

fail() { printf 'FAIL %s\n' "$*"; failed=1; }

for row in "${toolchains[@]}"; do
    read -r cc _ _ mode <<<"$row"
    [[ $mode == run ]] || { printf '%s: build-only here, so it runs no case\n' "$cc"; continue; }
    command -v "$cc" >/dev/null || { fail "$cc is not installed, so its kit cases did NOT run"; continue; }
    made="$out/$cc"
    "$PYTHON" -I scripts/make_kit.py --cc "$cc" "$made" || { fail "$cc: make_kit.py"; continue; }
    for expected in src/frameledger/kit/*.csv; do
        name=$(basename "$expected")
        cmp -s "$expected" "$made/$name" && continue
        "$PYTHON" -I src/frameledger check --expect "$expected" "$made/$name" || true
        fail "$cc: $name is not the kit's bytes"
    done
done

if (( failed )); then
    printf 'test_kit: FAILED\n'
    exit 1
fi
printf 'test_kit: every case matches under every toolchain that runs here\n'
