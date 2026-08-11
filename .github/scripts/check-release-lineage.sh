#!/usr/bin/env bash
# Assert that this repository's default branch contains every release it shipped.
#
# Why this exists: on 2026-07-30 the default branch (`main`) did not contain its
# own latest release (v0.3.2). The release lineage had become the real trunk
# while `main` decayed into a stale fork missing the champion codec AND the
# fail-closed decode hardening. Anyone cloning the default branch got a weaker,
# less safe build than the one published on the releases page, and CI on the
# default branch never tested what shipped.
#
# Two independent invariants, either of which would have caught that:
#   1. every non-draft release tag is an ancestor of the default branch;
#   2. the crate version on the default branch is not behind the latest release.
#
# Usage:
#   check-release-lineage.sh                 # check all non-draft releases (detection)
#   check-release-lineage.sh --tag vX.Y.Z    # check one tag, version must EQUAL it (pre-release gate)
#   check-release-lineage.sh --ref <branch>  # compare against this ref instead of the resolved default
#
# Requires: git (full history + tags), gh, jq. Exits 0 on success, 1 on violation,
# 2 on a broken environment — never silently green.
set -euo pipefail

REPO="${REPO:-${GITHUB_REPOSITORY:-}}"
MANIFEST="${MANIFEST:-code/cubrim-rs/Cargo.toml}"
TAG_MODE=""
REF_OVERRIDE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG_MODE="${2:?--tag needs a value}"; shift 2 ;;
    --ref) REF_OVERRIDE="${2:?--ref needs a value}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

die_env() { echo "check-release-lineage: ENVIRONMENT ERROR: $*" >&2; exit 2; }

for tool in git gh jq; do
  command -v "$tool" >/dev/null || die_env "$tool not found"
done
[ -n "$REPO" ] || REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
[ -n "$REPO" ] || die_env "cannot resolve the repository (set REPO or GITHUB_REPOSITORY)"

# A shallow clone has no merge-base information, so `--is-ancestor` would answer
# a question it cannot actually see. Refuse rather than pass.
if [ "$(git rev-parse --is-shallow-repository)" = true ]; then
  die_env "shallow clone — ancestry cannot be determined (use actions/checkout with fetch-depth: 0)"
fi

# Never hardcode the default branch: a rename would silently neuter the guard.
DEFAULT="$(gh repo view "$REPO" --json defaultBranchRef -q .defaultBranchRef.name)"
[ -n "$DEFAULT" ] || die_env "cannot resolve the default branch of $REPO"

if [ -n "$REF_OVERRIDE" ]; then
  TRUNK="$REF_OVERRIDE"
elif git rev-parse --verify -q "refs/remotes/origin/$DEFAULT" >/dev/null; then
  TRUNK="origin/$DEFAULT"
elif git rev-parse --verify -q "refs/heads/$DEFAULT" >/dev/null; then
  TRUNK="$DEFAULT"
else
  die_env "neither origin/$DEFAULT nor $DEFAULT exists locally"
fi
git rev-parse --verify -q "$TRUNK^{commit}" >/dev/null || die_env "$TRUNK is not a commit"

echo "repository:     $REPO"
echo "default branch: $DEFAULT"
echo "comparing against: $TRUNK ($(git rev-parse --short "$TRUNK"))"
echo

# Resolve a tag name to the commit it points at, annotated or lightweight, and
# fall back to the API when the tag was never fetched locally.
tag_commit() {
  local tag="$1" sha type
  sha="$(git rev-list -n1 "refs/tags/$tag" 2>/dev/null || true)"
  if [ -z "$sha" ]; then
    sha="$(gh api "repos/$REPO/git/ref/tags/$tag" -q .object.sha 2>/dev/null || true)"
    type="$(gh api "repos/$REPO/git/ref/tags/$tag" -q .object.type 2>/dev/null || true)"
    if [ "$type" = tag ] && [ -n "$sha" ]; then
      sha="$(gh api "repos/$REPO/git/tags/$sha" -q .object.sha)"
    fi
  fi
  printf '%s' "$sha"
}

# Read the [package] version out of the manifest AS IT EXISTS ON $TRUNK, not in
# the working tree: the invariant is about what the default branch can rebuild,
# so reading a dirty or differently-checked-out worktree would answer the wrong
# question. Anchored to the [package] table so a [dependencies] version cannot
# be picked up by accident.
crate_version() {
  git show "$TRUNK:$MANIFEST" 2>/dev/null \
    | sed -n '/^\[package\]/,/^\[[^p]/{
                s/^[[:space:]]*version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p
              }' | head -1
}

fail=0

# ---------------------------------------------------------------- invariant 1
if [ -n "$TAG_MODE" ]; then
  echo "== Pre-release gate: $TAG_MODE must already be in $DEFAULT =="
  sha="$(tag_commit "$TAG_MODE")"
  [ -n "$sha" ] || die_env "cannot resolve tag $TAG_MODE"
  if git merge-base --is-ancestor "$sha" "$TRUNK"; then
    echo "  ok  $TAG_MODE ($sha) is contained in $DEFAULT"
  else
    echo "  ORPHANED  $TAG_MODE ($sha) is NOT contained in $DEFAULT"
    fail=1
  fi
else
  echo "== Every non-draft release must be an ancestor of $DEFAULT =="
  # "Latest release" is taken from the GitHub Releases API, not from the highest
  # semver tag: releases are what users download, and this repo has tags with no
  # release plus release tags that were split across two lineages. Checking ALL
  # non-draft releases is strictly stronger and needs no notion of "latest".
  gh release list --repo "$REPO" --limit 200 \
     --json tagName,isDraft,isPrerelease,isLatest > /tmp/rl.json
  jq -r '.[] | select(.isDraft | not)
         | [ .tagName,
             (if .isPrerelease then "prerelease" else "release" end),
             (if .isLatest then "LATEST" else "-" end) ] | @tsv' /tmp/rl.json > /tmp/rl.tsv

  [ -s /tmp/rl.tsv ] || die_env "no non-draft releases found — refusing to report success"

  printf '  %-24s %-11s %-7s %s\n' TAG KIND LATEST ANCESTRY
  latest_bad=0
  while IFS=$'\t' read -r tag kind latest; do
    sha="$(tag_commit "$tag")"
    if [ -z "$sha" ]; then
      printf '  %-24s %-11s %-7s UNRESOLVABLE\n' "$tag" "$kind" "$latest"
      fail=1
      continue
    fi
    if git merge-base --is-ancestor "$sha" "$TRUNK"; then
      printf '  %-24s %-11s %-7s ok\n' "$tag" "$kind" "$latest"
    else
      printf '  %-24s %-11s %-7s ORPHANED %s\n' "$tag" "$kind" "$latest" "$sha"
      fail=1
      if [ "$latest" = LATEST ]; then
        latest_bad=1
      fi
    fi
  done < /tmp/rl.tsv
  [ "${latest_bad:-0}" = 1 ] && echo "  note: the LATEST release is among the orphans — this is the severe case."
fi

# ---------------------------------------------------------------- invariant 2
echo
crate="$(crate_version)"
[ -n "$crate" ] || die_env "could not parse a [package] version out of $MANIFEST"

if [ -n "$TAG_MODE" ]; then
  want="${TAG_MODE#v}"
  echo "== Crate version must equal the tag being released =="
  echo "  $MANIFEST = $crate ; tag = $TAG_MODE"
  if [ "$crate" != "$want" ]; then
    echo "  MISMATCH: the published binary would report $crate while the release says $TAG_MODE"
    fail=1
  else
    echo "  ok"
  fi
else
  latest_tag="$(jq -r '.[] | select(.isLatest) | .tagName' /tmp/rl.json | head -1)"
  if [ -z "$latest_tag" ]; then
    latest_tag="$(gh release view --repo "$REPO" --json tagName -q .tagName 2>/dev/null || true)"
  fi
  if [ -n "$latest_tag" ]; then
    rel="${latest_tag#v}"
    echo "== Crate version must not be behind the latest release =="
    echo "  $MANIFEST = $crate ; latest release = $latest_tag"
    # Equal is fine; ahead is fine (post-release dev bump); behind is the defect.
    if [ "$crate" != "$rel" ] && \
       [ "$(printf '%s\n%s\n' "$crate" "$rel" | sort -V | tail -1)" != "$crate" ]; then
      echo "  BEHIND: the default branch cannot rebuild the shipped binary"
      fail=1
    else
      echo "  ok"
    fi
  fi
fi

echo
if [ "$fail" = 0 ]; then
  echo "PASS: $DEFAULT contains everything this repository has released."
  exit 0
fi

cat >&2 <<'EOT'
==============================================================
FAIL: released code is missing from the default branch.
==============================================================
A release marked ORPHANED above was built from a commit the default
branch does not contain, or the crate version on the default branch is
behind what was published. Either way: cloning the default branch does
not give you the shipped product, and CI on the default branch is not
testing it.

Fix it by moving history forward, never by rewriting it:

    git fetch --all --tags
    git switch <default-branch>
    git merge --no-ff <lineage-holding-the-orphaned-tag>
    # resolve conflicts in favour of the SHIPPED codec and its hardening
    git push

Then re-run this check. Going forward, cut release tags FROM the default
branch; if a hotfix lane is used, merge it back BEFORE pushing the tag.
==============================================================
EOT
exit 1
