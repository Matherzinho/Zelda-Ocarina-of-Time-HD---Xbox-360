#!/usr/bin/env python3
"""merge_packs: joins the converted mod archives into one .o2r per group, as the Xbox 360 port can't keep dozens open.

    merge_packs.py [--budget SECONDS] IN_DIR OUT_DIR

xsdk's C library has 32 file slots and every archive the game loads holds its file open; with 46 mod archives the
15th failed to open (test 15) and a settings file after it read as empty, which aborted the game. Archives are
grouped by the letter make_xbox_pack.py put in front of their names (A Djipi's 3DS Experience, B Art Plus Link,
C translations, Z the Xbox 360 button glyphs) and merged in name order, a later archive's file replacing an earlier
one's of the same path, as the game would have loaded them; so each group becomes one archive with the same result.

Resumable in time slices like make_xbox_pack.py (the device's shell stops background work) and deletes nothing.
"""
import argparse
import json
import os
import sys
import time
import zipfile

GROUPS = {
    "A": "A 3DS Experience.o2r",
    "B": "B Art Plus Link.o2r",
    "C": "C PT-BR 3DS Experience.o2r",
    "Z": "Z Xbox Buttons.o2r",
}


def plan(sources):
    """path -> source archive, the last archive having it winning, in a fixed order."""
    owner = {}
    for src in sources:
        with zipfile.ZipFile(src) as z:
            for name in z.namelist():
                if not name.endswith("/"):
                    owner[name] = src
    return sorted(owner.items())


def merge(sources, dst, deadline):
    state_path = dst + ".state"
    state = None
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
        if not os.path.exists(state.get("tmp", "")):
            state = None
    if state is None:
        n = 0
        while os.path.exists(f"{dst}.part{n}"):
            n += 1
        state = {"tmp": f"{dst}.part{n}", "done": 0}
    items = plan(sources)
    opened = {}
    finished = True
    with zipfile.ZipFile(state["tmp"], "a" if state["done"] else "w", zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for i in range(state["done"], len(items)):
            if time.time() > deadline:
                finished = False
                break
            name, src = items[i]
            if src not in opened:
                opened[src] = zipfile.ZipFile(src)
            out.writestr(name, opened[src].read(name))
            state["done"] = i + 1
    for z in opened.values():
        z.close()
    if finished:
        os.replace(state["tmp"], dst)
    with open(state_path, "w") as f:
        json.dump(state, f)
    return finished, state["done"], len(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--budget", type=float, default=0)
    args = ap.parse_args()
    deadline = time.time() + args.budget if args.budget else float("inf")
    os.makedirs(args.out_dir, exist_ok=True)
    archives = sorted(f for f in os.listdir(args.in_dir) if f.lower().endswith(".o2r"))
    for letter, out_name in GROUPS.items():
        sources = [os.path.join(args.in_dir, f) for f in archives if f.startswith(letter + " ")]
        dst = os.path.join(args.out_dir, out_name)
        if not sources or os.path.exists(dst):
            continue
        finished, done, total = merge(sources, dst, deadline)
        if not finished:
            print(f"{out_name}: {done} of {total} files so far; run again to go on", flush=True)
            sys.exit(2)
        print(f"{out_name}: {total} files from {len(sources)} archives, {os.path.getsize(dst) / 1e6:.1f} MB", flush=True)
    print("all done")


if __name__ == "__main__":
    main()
