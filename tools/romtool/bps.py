#!/usr/bin/env python3
"""Minimal BPS patch applier (format by byuu/Near), verifying all three CRC32s.

usage: bps.py SOURCE PATCH OUTPUT
The user applies the translation patch to their own ROM locally; the project never ships patched data.
"""
import sys, zlib


def apply(src: bytes, patch: bytes) -> bytes:
    if patch[:4] != b"BPS1":
        raise ValueError("not a BPS patch")
    pos = 4

    def num():
        nonlocal pos
        data, shift = 0, 1
        while True:
            x = patch[pos]
            pos += 1
            data += (x & 0x7F) * shift
            if x & 0x80:
                return data
            shift <<= 7
            data += shift

    src_size, dst_size, meta = num(), num(), num()
    pos += meta
    if len(src) != src_size:
        raise ValueError(f"source size {len(src)} != expected {src_size}")
    if zlib.crc32(src) != int.from_bytes(patch[-12:-8], "little"):
        raise ValueError("source CRC32 mismatch (wrong ROM, or byte order not z64)")
    if zlib.crc32(patch[:-4]) != int.from_bytes(patch[-4:], "little"):
        raise ValueError("patch file is corrupt")
    out = bytearray(dst_size)
    o = src_rel = dst_rel = 0
    end = len(patch) - 12
    while pos < end:
        d = num()
        cmd, length = d & 3, (d >> 2) + 1
        if cmd == 0:  # SourceRead
            out[o:o + length] = src[o:o + length]
            o += length
        elif cmd == 1:  # TargetRead
            out[o:o + length] = patch[pos:pos + length]
            pos += length
            o += length
        elif cmd == 2:  # SourceCopy
            v = num()
            src_rel += (-1 if v & 1 else 1) * (v >> 1)
            out[o:o + length] = src[src_rel:src_rel + length]
            src_rel += length
            o += length
        else:  # TargetCopy (may overlap: copy byte by byte)
            v = num()
            dst_rel += (-1 if v & 1 else 1) * (v >> 1)
            for _ in range(length):
                out[o] = out[dst_rel]
                o += 1
                dst_rel += 1
    if zlib.crc32(out) != int.from_bytes(patch[-8:-4], "little"):
        raise ValueError("output CRC32 mismatch")
    return bytes(out)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    s = open(sys.argv[1], "rb").read()
    p = open(sys.argv[2], "rb").read()
    open(sys.argv[3], "wb").write(apply(s, p))
    print("ok:", sys.argv[3])
