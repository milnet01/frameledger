#!/usr/bin/env bash
# Is the tree ready to tag? The analyser's VERSION has a CHANGELOG section,
# the SHA256 that section states is the archive this tree builds, and the
# result schemas frozen for VERSION are the ones this tree ships.
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
# FLED-0041 § 4.7: a release's schemas are frozen as shipped, so later
# releases are held to what scripts really got.
frozen=tests/fixtures/schemas/$version
for schema in src/frameledger/schemas/*.schema.json; do
    if ! cmp -s "$schema" "$frozen/$(basename "$schema")"; then
        echo "check-release: $frozen/$(basename "$schema") is not the tree's; run scripts/freeze_schemas.py" \
             "before the tag, and never change a frozen set after it" >&2
        exit 1
    fi
done
echo "check-release: $frozen holds this tree's result schemas"
# The archive is built from the working tree, so name any uncommitted file
# that went into the hash. At bump time that is the VERSION edit; anything
# else will not be in the tag, and release.yml will then fail on it.
uncommitted=$(git status --short -- src include LICENSE)
[[ -z $uncommitted ]] || printf 'check-release: built from uncommitted files:\n%s\n' "$uncommitted"
