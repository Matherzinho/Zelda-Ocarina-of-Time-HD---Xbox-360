#!/bin/bash
# The interface's and Link's textures at 4x as patches over the 2x pack (make_hd_patch.py), in time slices:
#   MODS    the PC's Ship of Harkinian mods folder (Djipi's 3DE archives, Skilar's Art Plus Link folder, EduardoA's
#           PT-BR archive)
#   OUT     where the console's archives go (with "Z Xbox Buttons.o2r" from tools/xboxbuttons, left out of A2)
#   BUDGET  seconds a run may take (default 160); run again until it prints "all done"
# The output stays on the player's own machine and console (docs/PLAYING.md).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
MODS="${MODS:?the mods folder}"
OUT="${OUT:?the output folder}"
BUDGET="${BUDGET:-160}"
T="$HERE/make_hd_patch.py"
start=$(date +%s)
left() { echo $((BUDGET - ($(date +%s) - start))); }
mkdir -p "$OUT"
A=()
while IFS= read -r f; do A+=("$f"); done < <(ls "$MODS"/Djipi*.otr "$MODS"/Djipi*.o2r 2>/dev/null |
	grep -v "Original N64 HUD" | grep -v "02 Link's Textures" | LC_ALL=C sort)
B=()
while IFS= read -r f; do B+=("$f"); done < <(ls "$MODS"/*/Art*.otr 2>/dev/null | LC_ALL=C sort)
C=("$MODS"/EduardoA*.otr)
EXCEPT=()
[ -f "$OUT/Z Xbox Buttons.o2r" ] && EXCEPT=(--except "$OUT/Z Xbox Buttons.o2r")
python3 "$T" --group ui "${EXCEPT[@]}" --budget "$(left)" "$OUT/A2 Interface 4x.o2r" "${A[@]}" || exit 2
python3 "$T" --group link --budget "$(left)" "$OUT/B1 Link 4x.o2r" "${B[@]}" || exit 2
python3 "$T" --group ui --budget "$(left)" "$OUT/C1 PT-BR Interface 4x.o2r" "${C[@]}" || exit 2
echo "all done"
