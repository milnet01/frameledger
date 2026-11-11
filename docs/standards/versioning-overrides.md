# Versioning overrides — frameledger

This file answers what `~/.claude/standards/versioning.md` § 3 and § 4
leave to each project: the breaking surfaces, the `1.0` exit line, and
one departure from § 4's numbering inside `0.x`. Everything else
follows the global standard unchanged.

## What makes it 1.0

**MAJOR stays 0 until every item in `ROADMAP.md`'s 1.0.0 section has
shipped.** That section holds each engine finding and fixing a
bottleneck with frameledger (FLED-0014) and a version a stranger's
engine can use (FLED-0015), which waits on 0.6.0 to 0.9.0.

## One MINOR per milestone

**Departure from § 4.** Inside `0.x`, § 4 bumps the MINOR only for a
breaking change, and a new feature bumps the PATCH. Here, each
`ROADMAP.md` milestone section is released as the next MINOR, whatever
it holds: 0.5.0 is "variants and baselines". A PATCH, such as 0.5.1,
carries fixes only, and never a breaking change.

**Why.** Each milestone's number is its roadmap section's name, so an
engine reading "pinned at 0.4.0" knows which features it has, and the
roadmap can plan features for a release before they are built. Under
§ 4, 0.3.0 and 0.4.0, which added features and broke nothing, would
have been 0.2.1 and 0.2.2, and the roadmap could not have named its
releases ahead.

**What still holds from § 4.** A breaking change never ships in a
PATCH. It waits for the next milestone's MINOR, and that release's
`CHANGELOG.md` entry names it.

## Breaking surfaces

A release that changes any of these so that existing use stops working
is breaking. They are what `docs/design.md` § The parts says engines'
scripts and writers are built to.

- **The run file**: its header, static line, rows and close line,
  `docs/specs/FLED-0001-run-file-format.md` § 4.1 to § 4.5. A file
  that one release reads must still be read by the next.
- **The budget file**, § 4.12.
- **The writer's interface**: the functions, types and limits
  `include/frameledger.h` declares, § 4.6.
- **The commands**: each command's flags, defaults and exit codes, and
  its JSON result's keys and meanings, § 4.7 to § 4.16.
- **How it is run**: `python3 -I src/frameledger`, the
  `frameledger.pyz` bundle, the `frameledger` and `frameledger.cmd`
  launchers (§ 4.7), and the Python 3.10 floor.

## Not surfaces

- **Plain text and Markdown output.** They are for people; scripts
  read the JSON. Their wording may change in any release.
- **The analyser's modules.** Nothing outside this repository imports
  them.
