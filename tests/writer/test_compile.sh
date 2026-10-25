#!/usr/bin/env bash
# The writer's tests: docs/specs/FLED-0001-run-file-format.md § 4.6 and § 7.
#
# INV-14: include/frameledger.h compiles with no warnings as C99 and as
# C++17 under GCC, Clang and mingw-w64; one C file and one C++ file share a
# writer in one program; and `nm -u` finds no allocation, file I/O, printf
# or locale symbol in either object. Then test_writer.c runs, built as C
# and as C++, and its run file goes through the analyser's `check`
# (INV-16). mingw-w64 builds are compiled and linked, not run: the Windows
# runs are Vestige's and UT Ants' (FLED-0007).
#
# Usage: tests/writer/test_compile.sh
# PYTHON names the interpreter for `check` (default python3). A compiler
# that is not installed fails the run: a check that did not run must not
# read as a pass.
set -Eeuo pipefail
cd "$(dirname "$0")/../.."

PYTHON=${PYTHON:-python3}
FLAGS=(-O2 -Wall -Wextra -Wpedantic -Werror)
# Symbols the header must never need: § 4.6, no allocation, no file I/O,
# no printf family, no locale. C++ operator new and new[] too.
FORBIDDEN='malloc|calloc|realloc|free|fopen|fclose|fwrite|fputs|fputc|puts|printf|fprintf|sprintf|snprintf|vsnprintf|vfprintf|__mingw_.*printf|setlocale|localeconv|_Zn[wa][my]'

out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
failed=0

fail() { printf 'FAIL %s\n' "$*"; failed=1; }

# no_forbidden NM OBJECT — fails when OBJECT needs a forbidden symbol.
no_forbidden() {
    local found
    found=$("$1" -u "$2" | awk '{print $NF}' | grep -E -x "_?($FORBIDDEN)" || true)
    [[ -z $found ]] || fail "$2 references: $found"
}

# One row per toolchain: C compiler, C++ compiler, nm, and whether its
# programs run here.
toolchains=(
    "gcc g++ nm run"
    "clang clang++ nm run"
    "x86_64-w64-mingw32-gcc x86_64-w64-mingw32-g++ x86_64-w64-mingw32-nm build-only"
)

for row in "${toolchains[@]}"; do
    read -r cc cxx nm mode <<<"$row"
    for tool in "$cc" "$cxx" "$nm"; do
        command -v "$tool" >/dev/null || { fail "$tool is not installed, so its checks did NOT run"; continue 2; }
    done
    exe=; [[ $mode == build-only ]] && exe=.exe

    # INV-14: the mixed program, and what its objects reference.
    "$cc" -std=c99 "${FLAGS[@]}" -c tests/writer/mixed_c.c -o "$out/$cc-mixed_c.o" || { fail "$cc: mixed_c.c"; continue; }
    "$cxx" -std=c++17 "${FLAGS[@]}" -c tests/writer/mixed_cpp.cpp -o "$out/$cxx-mixed_cpp.o" || { fail "$cxx: mixed_cpp.cpp"; continue; }
    no_forbidden "$nm" "$out/$cc-mixed_c.o"
    no_forbidden "$nm" "$out/$cxx-mixed_cpp.o"
    "$cxx" "$out/$cc-mixed_c.o" "$out/$cxx-mixed_cpp.o" -lm -o "$out/$cxx-mixed$exe" || { fail "$cxx: linking the mixed program"; continue; }

    # The behaviour tests, as C and as C++.
    "$cc" -std=c99 "${FLAGS[@]}" tests/writer/test_writer.c -lm -o "$out/$cc-test_writer$exe" || fail "$cc: test_writer.c"
    "$cxx" -std=c++17 "${FLAGS[@]}" -x c++ tests/writer/test_writer.c -lm -o "$out/$cxx-test_writer$exe" || fail "$cxx: test_writer.c as C++"
    [[ $mode == run ]] || { printf '%s: built and linked; not run here\n' "$cc"; continue; }

    "$out/$cxx-mixed" || fail "$cxx: the mixed program exited $?"
    for program in "$cc-test_writer" "$cxx-test_writer"; do
        if "$out/$program" "$out/$program.csv"; then
            # INV-16: the run written under a comma-decimal locale conforms.
            "$PYTHON" -I src/frameledger check "$out/$program.csv" >"$out/check.txt" ||
                { cat "$out/check.txt"; fail "$program: its run fails check"; }
        else
            fail "$program"
        fi
    done
done

if (( failed )); then
    printf 'test_compile: FAILED\n'
    exit 1
fi
printf 'test_compile: all writer checks passed\n'
