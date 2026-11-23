# shellcheck shell=bash
# The writer's toolchains, read by test_compile.sh and test_kit.sh: one row
# each of C compiler, C++ compiler, nm, and whether its programs run here.
# On Linux, mingw-w64 builds are compiled and linked, not run; on Windows
# (Git Bash), the `gcc` on PATH, expected to be mingw-w64, and it runs
# (FLED-0087); GitHub's runner image puts one there. macOS has
# one row: its `gcc` is Apple's Clang under another name, so a GCC row
# would test Clang twice, and GCC and mingw-w64 are checked on Linux by the
# same CI run (FLED-0038).

# shellcheck disable=SC2034  # used by the scripts that source this file
case $(uname -s) in
Darwin)
    toolchains=("clang clang++ nm run")
    ;;
MINGW*)
    toolchains=("gcc g++ nm run")
    ;;
*)
    toolchains=(
        "gcc g++ nm run"
        "clang clang++ nm run"
        "x86_64-w64-mingw32-gcc x86_64-w64-mingw32-g++ x86_64-w64-mingw32-nm build-only"
    )
    ;;
esac
