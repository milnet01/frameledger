# ADR-0001: The analyser is Python 3 standard library, not C or C++

- **Status:** Accepted (2026-10-24)
- **Date:** 2026-10-24

## Context

The owner asked whether C or C++ would suit the analyser better than
Python. Each engine was asked what it needs from the analyser
([answers](../reviews/2026-10-24-discovery-customer-answers.md)).

- None embeds the analyser. Each needs a command-line report, a JSON
  result and an exit code.
- Each runs it in its own CI or pre-push pipeline. Vestige's and
  UT Ants' already run Python tools. DOOM Ants' runs in a container.
- Vestige and UT Ants also run on Windows.
- The engines estimate one run at a few thousand to a few hundred
  thousand rows, and a 127-map survey at about a million.
- All three answered Python 3 standard library.

## Decision

The analyser is Python 3.10 or newer, using only the standard library.
It is run as `python3 -I`, either on the `src/frameledger` directory or on a
bundled `.pyz` file.

## Consequences

- No customer builds anything to get a report, on Linux or Windows.
- Speed is bounded by Python. S19 sets the bar: about a million rows in
  under a minute. If a later survey outgrows that, the answer is a
  faster reader inside the analyser, not a second language.
- No plotting or data-frame library, ever (discovery N3). Charts, when
  they come, are drawn without one.
- The analyser cannot be linked into an engine. No engine asked for
  that.
