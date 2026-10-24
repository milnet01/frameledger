# ADR-0002: The writer is one header in the common subset of C99 and C++17

- **Status:** Accepted (2026-10-24)
- **Date:** 2026-10-24

## Context

All three engines asked for an optional writer that formats the file
and times nothing
([answers](../reviews/2026-10-24-discovery-customer-answers.md)).

- DOOM Ants' engine is C, built as `-std=gnu11 -Wall`. Its Vulkan
  back-end is C++, built as `-std=c++23 -Wall`. Its Windows build uses
  mingw-w64 GCC and G++ 13.
- Vestige is C++17 and builds with `-Wall -Wextra -Wpedantic` under
  GCC and Clang, and under MSVC.
- UT Ants is C++23, built with GCC 14, Clang 19 and MSVC. It first
  asked for a C++ header. It accepted one C header that compiles
  warning-free at `/W4 /WX` (MSVC) and `-Wall -Wextra -Werror` (GCC,
  Clang), checked in a translation unit of its own, and needs no build
  step.

## Decision

The writer is `include/frameledger.h`: one header, no dependencies, no
build step, written in the subset that compiles warning-free both as
C99 and as C++17.

## Consequences

- One copy serves all three engines.
- It cannot use C-only syntax C++ rejects (designated initialisers,
  variable-length arrays, `restrict`), nor C++-only features such as
  templates, classes or `std::` types. C++ callers get a C interface.
- Its tests must compile it as C and as C++, under GCC and Clang, at
  each engine's warning level, mingw-w64 included. This machine cannot
  run MSVC. Vestige's Windows CI and UT Ants' push gate each compile the
  header with MSVC at `/W4 /WX` on every release they pin, and report a
  failure back.
- It stays optional (discovery N2). A writer built from the spec alone
  is equally valid.
