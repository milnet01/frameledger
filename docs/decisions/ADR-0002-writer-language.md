# ADR-0002: The writer is one header in the common subset of C99 and C++17

- **Status:** Proposed — accepted when the design is agreed
- **Date:** 2026-10-24

## Context

All three engines asked for an optional writer that formats the file
and times nothing
([answers](../reviews/2026-10-24-discovery-customer-answers.md)).

- DOOM Ants' engine is C, with a C++ Vulkan back-end.
- Vestige is C++17 and builds with `-Wall -Wextra -Wpedantic` under
  GCC and Clang, and under MSVC.
- UT Ants is C++23 and builds with warnings as errors under GCC 14,
  Clang 19 and MSVC.
- UT Ants first asked for a C++ header; it accepted one C header on
  those two build conditions.

## Decision

The writer is `include/frameledger.h`: one header, no dependencies, no
build step, written in the subset that compiles warning-free both as
C99 and as C++17.

## Consequences

- One copy serves all three engines.
- It cannot use C-only syntax C++ rejects (designated initialisers,
  variable-length arrays, `restrict`), nor C++-only features such as
  templates, classes or `std::` types. C++ callers get a C interface.
- Its tests must compile it as C and as C++, under GCC, Clang and MSVC,
  at each engine's warning level. MSVC needs a Windows build, which
  this machine's own checks cannot run (unverified how it will be
  covered).
- It stays optional (discovery N2). A writer built from the spec alone
  is equally valid.
