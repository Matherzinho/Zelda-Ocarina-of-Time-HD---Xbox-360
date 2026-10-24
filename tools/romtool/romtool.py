#!/usr/bin/env python3
"""romtool: local-only helper for the user's own Ocarina of Time ROMs.

It never writes game data inside the repository: every output path must be outside it
(the default is ./localdata, which .gitignore and the pre-commit hook keep out of Git).

Commands
  id      FILE...              byte order, header, SHA-1 of the normalized (big-endian) image
  files   ROM                  list dmadata entries (index, vrom range, compressed?)
  diff    BASE ROM             list files whose *decompressed* contents differ
  extract BASE ROM OUTDIR      write the differing files of ROM (decompressed) to OUTDIR,
                               plus manifest.json with indexes, sizes and SHA-1s
"""
import argparse, hashlib, json, os, struct, sys

KNOWN = {
    "ad69c91157f6705e8ab06c79fe08aad47bb57ba7": "OoT NTSC-U 1.0 (clean)",
    "db757847a2a506d9012c104c7ac2b10c87026cb5": "OoT USA 1.0 + PT-BR v1.8 (Patcher64+, with Redux code changes)",
    "6d360761696d9da4645ff12f241865a96e34b31e": "OoT Master Quest (built from USA 1.0) + PT-BR v1.8",
}
DMADATA_START = {"ad69c91157f6705e8ab06c79fe08aad47bb57ba7": 0x7430}
DEFAULT_DMADATA = 0x7430  # NTSC 1.0


def normalize(raw: bytes):
    m = raw[:4]
    if m == b"\x80\x37\x12\x40":
        return raw, "z64 (big-endian)"
    if m == b"\x37\x80\x40\x12":
        a = bytearray(raw)
        a[0::2], a[1::2] = raw[1::2], raw[0::2]
        return bytes(a), "v64 (16-bit byteswapped)"
    if m == b"\x40\x12\x37\x80":
        a = bytearray(len(raw))
        for k in range(4):
            a[k::4] = raw[3 - k::4]
        return bytes(a), "n64 (32-bit little-endian)"
    raise SystemExit(f"not an N64 ROM (magic {m.hex()})")


def load(path):
    with open(path, "rb") as f:
        return normalize(f.read())


def yaz0(d: bytes) -> bytes:
    if d[:4] != b"Yaz0":
        raise ValueError("not Yaz0")
    size = struct.unpack(">I", d[4:8])[0]
    out = bytearray()
    i = 16
    while len(out) < size:
        code = d[i]
        i += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if code & (0x80 >> bit):
                out.append(d[i])
                i += 1
            else:
                b1, b2 = d[i], d[i + 1]
                i += 2
                dist = ((b1 & 0xF) << 8 | b2) + 1
                n = b1 >> 4
                if n == 0:
                    n = d[i] + 0x12
                    i += 1
                else:
                    n += 2
                for _ in range(n):
                    out.append(out[-dist])
    return bytes(out)


def dmatable(rom: bytes, start=DEFAULT_DMADATA):
    t, o = [], start
    while True:
        e = struct.unpack(">4I", rom[o:o + 16])
        o += 16
        if e == (0, 0, 0, 0) and t:
            return t
        t.append(e)


def file_data(rom, entry):
    vs, ve, rs, re_ = entry
    if rs == 0xFFFFFFFF:
        return None
    if re_:
        return yaz0(rom[rs:re_])
    return rom[rs:rs + (ve - vs)]


def names_from(path):
    if not path:
        return None
    with open(path) as f:
        rows = [line.split(",")[0].strip() for line in f]
    return rows[1:]  # header row


def cmd_id(a):
    for p in a.files:
        rom, fmt = load(p)
        sha = hashlib.sha1(rom).hexdigest()
        print(p)
        print(f"  format : {fmt}")
        print(f"  title  : {rom[0x20:0x34].decode('ascii', 'replace').rstrip()}")
        print(f"  id/rev : {rom[0x3B:0x3F].decode('ascii', 'replace')} rev {rom[0x3F]}")
        print(f"  sha1   : {sha}  ({KNOWN.get(sha, 'unknown')})")


def cmd_files(a):
    rom, _ = load(a.rom)
    names = names_from(a.names)
    for i, (vs, ve, rs, re_) in enumerate(dmatable(rom)):
        n = names[i] if names and i < len(names) else ""
        print(f"{i:4d} {vs:08x}-{ve:08x} {'yaz0' if re_ else '    '} {n}")


def changed(base, rom):
    ta, tb = dmatable(base), dmatable(rom)
    if len(ta) != len(tb):
        raise SystemExit("dmadata tables differ in length; not the same game layout")
    for i, (ea, eb) in enumerate(zip(ta, tb)):
        da, db = file_data(base, ea), file_data(rom, eb)
        if da != db:
            yield i, da, db


def cmd_diff(a):
    base, _ = load(a.base)
    rom, _ = load(a.rom)
    names = names_from(a.names)
    n = 0
    for i, da, db in changed(base, rom):
        n += 1
        nm = names[i] if names and i < len(names) else f"file_{i}"
        print(f"{i:4d} {nm:32s} {len(da or b''):8d} -> {len(db or b''):8d}")
    print(f"{n} files differ")


def inside_repo(path):
    repo = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    p = os.path.realpath(path)
    return p == repo or p.startswith(repo + os.sep) and not p.startswith(os.path.join(repo, "localdata"))


def cmd_extract(a):
    if inside_repo(a.outdir):
        raise SystemExit("refusing to write game data inside the repository (use localdata/ or a path outside it)")
    base, _ = load(a.base)
    rom, _ = load(a.rom)
    names = names_from(a.names)
    os.makedirs(a.outdir, exist_ok=True)
    manifest = {"base_sha1": hashlib.sha1(base).hexdigest(), "rom_sha1": hashlib.sha1(rom).hexdigest(), "files": []}
    for i, da, db in changed(base, rom):
        nm = names[i] if names and i < len(names) else f"file_{i}"
        with open(os.path.join(a.outdir, f"{i:04d}_{nm}.bin"), "wb") as f:
            f.write(db or b"")
        manifest["files"].append({"index": i, "name": nm, "base_size": len(da or b""), "size": len(db or b""),
                                  "sha1": hashlib.sha1(db or b"").hexdigest()})
    with open(os.path.join(a.outdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"wrote {len(manifest['files'])} files to {a.outdir}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--names", help="optional segments.csv (zeldaret/oot baseroms/<ver>/segments.csv) for file names")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("id"); p.add_argument("files", nargs="+"); p.set_defaults(f=cmd_id)
    p = sp.add_parser("files"); p.add_argument("rom"); p.set_defaults(f=cmd_files)
    p = sp.add_parser("diff"); p.add_argument("base"); p.add_argument("rom"); p.set_defaults(f=cmd_diff)
    p = sp.add_parser("extract"); p.add_argument("base"); p.add_argument("rom"); p.add_argument("outdir")
    p.set_defaults(f=cmd_extract)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    sys.exit(main())
