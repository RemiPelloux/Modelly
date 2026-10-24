#!/usr/bin/env bash
# Put one built version into the assembled docs site, then refresh switcher.json.
#
#   bash scripts/assemble-docs-site.sh <site> <build> <version>
#
# <site>    a checkout of the docs-site branch (one folder per version, newest at the root)
# <build>   the HTML of one version, from scripts/build-docs-version.sh
# <version> dev or X.Y
#
# <build> replaces <site>/<version>. An X.Y at least as new as every X.Y already in the
# site also replaces the root files, leaving the version folders alone.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  sed -n '2,10p' "$0" >&2
  exit 2
fi
SITE="$1"
BUILD="$2"
VERSION="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
VERSION_FOLDERS=(--exclude='/dev/' --exclude='/[0-9]*.[0-9]*/')
SITE_FILES=(--exclude='/.git' --exclude='/switcher.json' --exclude='/.nojekyll')
if [[ ! "$VERSION" =~ ^(dev|[0-9]+\.[0-9]+)$ ]]; then
  echo "version must be dev or X.Y, got: '$VERSION'" >&2
  exit 2
fi

mkdir -p "$SITE/$VERSION"
rsync -a --checksum --delete "$BUILD/" "$SITE/$VERSION/"

newest="$("$PYTHON" "$HERE/docs_switcher.py" "$SITE" --newest)"
if [[ "$VERSION" != dev && "$VERSION" == "$newest" ]]; then
  rsync -a --checksum --delete "${VERSION_FOLDERS[@]}" "${SITE_FILES[@]}" "$BUILD/" "$SITE/"
  echo "root updated to $VERSION"
fi

# The roadmap is newer than some releases: until the root version has its own, /roadmap/
# sends readers to the dev build's.
if [[ ! -f "$SITE/roadmap/index.html" && -f "$SITE/dev/roadmap/index.html" ]]; then
  mkdir -p "$SITE/roadmap"
  cat > "$SITE/roadmap/index.html" <<'HTML'
<!doctype html>
<meta charset="utf-8">
<title>Roadmap</title>
<meta http-equiv="refresh" content="0; url=../dev/roadmap/">
<link rel="canonical" href="../dev/roadmap/">
<p>The roadmap is at <a href="../dev/roadmap/">dev/roadmap</a>.</p>
HTML
fi

"$PYTHON" "$HERE/docs_switcher.py" "$SITE"
touch "$SITE/.nojekyll"
echo "site assembled: $(du -sh "$SITE" --exclude=.git | cut -f1) in $SITE"
