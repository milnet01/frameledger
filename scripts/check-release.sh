#!/usr/bin/env bash
# Is the tree ready to tag? The analyser's VERSION has a CHANGELOG section,
# and the SHA256 that section states is the archive this tree builds.
# cut-release runs it after the bump (.claude/bump.json's post_check);
# release.yml makes the same check on the tag. Exit 0 ready, 1 not.
set -Eeuo pipefail
cd "$(dirname "$0")/.."

version=$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' src/frameledger/cli.py)
outdir=$(mktemp -d)
trap 'rm -rf "$outdir"' EXIT
sha=$(python3 -I scripts/build_release.py "$outdir" check | tail -n 1)
python3 -I scripts/release_notes.py "$version" --sha256 "$sha" >/dev/null
echo "check-release: $version section states this tree's archive, SHA256 $sha"
# The archive is built from the working tree, so name any uncommitted file
# that went into the hash. At bump time that is the VERSION edit; anything
# else will not be in the tag, and release.yml will then fail on it.
uncommitted=$(git status --short -- src include LICENSE)
[[ -z $uncommitted ]] || printf 'check-release: built from uncommitted files:\n%s\n' "$uncommitted"
