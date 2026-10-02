#!/bin/sh
# Rebuild the clean ROM and the web site; with "push" as $1 also push gh-pages ($2 = commit message).
# Refuses to build the site unless the taint report says 0 failing.
#   sh tools/publish.sh            build + taint + site (local)
#   sh tools/publish.sh push "msg" same, then push the site to gh-pages
#   SKIP_BUILD=1 sh tools/publish.sh ...   reuse the ROM and taint report already in the build dir
set -e
W=/d/n64work/marioparty
RETAIL="$W/rom/Mario Party (USA).z64"
ROM=$W/build/marioparty.z64
SITE=$W/site
cd /d/n64work/marioparty-cleanroom
if [ -z "$SKIP_BUILD" ]; then
    python -m games.marioparty.generate "$RETAIL" $ROM | cut -c1-240
    python -m games.marioparty.taint "$RETAIL" $ROM TAINT.md | tee $W/build/taint.txt
fi
grep -q "^taint: 0 failing" $W/build/taint.txt || { echo "taint not clean: not publishing"; exit 1; }
grep -q "DEV BUILD" $W/build/taint.txt && { echo "dev build: not publishing"; exit 1; }
[ -d $W/devsite/cores_orig ] || cp -r $W/devsite/data/cores $W/devsite/cores_orig
python ports/ejs/patch_core.py $ROM $W/devsite/cores_orig $W/devsite/data/cores | tail -1
python ports/ejs/make_site.py $ROM $W/devsite $SITE
[ "$1" = push ] || exit 0
cd $SITE
[ -d .git ] || { git init -q && git remote add origin https://github.com/andrewnakas/marioparty-cleanroom.git; }
git config user.name andre && git config user.email treesixtyweather@gmail.com
# one orphan commit per deploy: the Pages builder chokes on a long history of 32 MB ROMs
git checkout -q --orphan tmp && git add -A && git commit -qm "Site: ${2:-rebuild}" \
    && { git branch -D gh-pages -q 2>/dev/null || true; } && git branch -m gh-pages \
    && git push -q -f origin gh-pages && git gc -q --prune=now && echo "pushed gh-pages"
