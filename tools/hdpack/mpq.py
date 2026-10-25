"""mpq: reads the MPQ archives (.otr) Ship of Harkinian's older tools and mods write, StormLib's format.

    archive = Mpq(path)
    for name in archive.names(): data = archive.read(name)

Only what those archives use: format versions 1 to 4 read through the classic hash and block tables (StormLib still
writes them beside HET/BET), files whole or in sectors, stored, zlib, bzip2 or LZMA, optionally encrypted. Names come
from the archive's (listfile).
"""
import bz2
import lzma
import struct
import zlib

_CRYPT = []


def _crypt_table():
    seed = 0x00100001
    table = [0] * 0x500
    for index1 in range(0x100):
        index2 = index1
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp1 = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp2 = seed & 0xFFFF
            table[index2] = temp1 | temp2
            index2 += 0x100
    return table


def _hash(name, kind):
    if not _CRYPT:
        _CRYPT.extend(_crypt_table())
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in name.upper().encode("latin-1"):
        seed1 = (_CRYPT[(kind << 8) + ch] ^ (seed1 + seed2)) & 0xFFFFFFFF
        seed2 = (ch + seed1 + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return seed1


def _decrypt(data, key):
    if not _CRYPT:
        _CRYPT.extend(_crypt_table())
    n = len(data) // 4
    words = list(struct.unpack_from(f"<{n}I", data))
    seed = 0xEEEEEEEE
    for i in range(n):
        seed = (seed + _CRYPT[0x400 + (key & 0xFF)]) & 0xFFFFFFFF
        value = words[i] ^ ((key + seed) & 0xFFFFFFFF)
        key = ((((~key) << 0x15) + 0x11111111) | (key >> 0x0B)) & 0xFFFFFFFF
        seed = (value + seed + (seed << 5) + 3) & 0xFFFFFFFF
        words[i] = value
    return struct.pack(f"<{n}I", *words) + data[n * 4:]


FLAG_IMPLODE = 0x00000100
FLAG_COMPRESS = 0x00000200
FLAG_ENCRYPTED = 0x00010000
FLAG_FIX_KEY = 0x00020000
FLAG_SINGLE_UNIT = 0x01000000
FLAG_SECTOR_CRC = 0x04000000
FLAG_EXISTS = 0x80000000


def _decompress(data, size):
    """A sector: its first byte names the compressions applied, outermost last."""
    if len(data) >= size:
        return data[:size]
    mask, body = data[0], data[1:]
    if mask == 0x02:
        return zlib.decompress(body)
    if mask == 0x10:
        return bz2.decompress(body)
    if mask == 0x12:
        # StormLib's LZMA: a 5-byte properties header, then an 8-byte size, then the stream.
        props = body[:5]
        filters = [{"id": lzma.FILTER_LZMA1, "dict_size": struct.unpack_from("<I", props, 1)[0],
                    "lc": props[0] % 9, "lp": (props[0] // 9) % 5, "pb": props[0] // 45}]
        return lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=filters).decompress(body[13:], size)
    if mask == 0x00:
        return body
    raise ValueError(f"MPQ compression 0x{mask:02X} not handled")


class Mpq:
    def __init__(self, path):
        self.file = open(path, "rb")
        head = self.file.read(0x2C)
        offset = 0
        while head[:4] != b"MPQ\x1a":
            if head[:4] == b"MPQ\x1b":  # user data header points at the archive
                offset = struct.unpack_from("<I", head, 8)[0]
            else:
                offset += 0x200
            self.file.seek(offset)
            head = self.file.read(0x2C)
            if len(head) < 0x20:
                raise ValueError(f"{path}: not an MPQ archive")
        self.base = offset
        (_, header_size, _, version, sector_shift, hash_pos, block_pos, hash_count,
         block_count) = struct.unpack_from("<4sIIHHIIII", head)
        hash_hi = block_hi = 0
        if version >= 1:
            _, hash_hi, block_hi = struct.unpack_from("<QHH", head, 0x20)
        self.sector_size = 512 << sector_shift
        self.file.seek(self.base + (hash_hi << 32 | hash_pos))
        hashes = _decrypt(self.file.read(hash_count * 16), _hash("(hash table)", 3))
        self.file.seek(self.base + (block_hi << 32 | block_pos))
        blocks = _decrypt(self.file.read(block_count * 16), _hash("(block table)", 3))
        self.hashes = [struct.unpack_from("<IIHHI", hashes, i * 16) for i in range(hash_count)]
        self.blocks = [struct.unpack_from("<IIII", blocks, i * 16) for i in range(block_count)]

    def _find(self, name):
        start = _hash(name, 0) % len(self.hashes)
        a, b = _hash(name, 1), _hash(name, 2)
        i = start
        while True:
            ha, hb, _, _, block = self.hashes[i]
            if block == 0xFFFFFFFF:
                return None
            if ha == a and hb == b and block != 0xFFFFFFFE:
                return block
            i = (i + 1) % len(self.hashes)
            if i == start:
                return None

    def read(self, name):
        index = self._find(name)
        if index is None:
            raise KeyError(name)
        pos, packed, size, flags = self.blocks[index]
        if not flags & FLAG_EXISTS:
            raise KeyError(name)
        if flags & FLAG_IMPLODE:
            raise ValueError(f"{name}: PKWARE implode not handled")
        self.file.seek(self.base + pos)
        raw = self.file.read(packed)
        key = None
        if flags & FLAG_ENCRYPTED:
            key = _hash(name.replace("/", "\\").split("\\")[-1], 3)
            if flags & FLAG_FIX_KEY:
                key = ((key + pos) ^ size) & 0xFFFFFFFF
        if flags & FLAG_SINGLE_UNIT or not flags & FLAG_COMPRESS:
            if key is not None:
                raw = _decrypt(raw, key)
            return _decompress(raw, size) if flags & FLAG_COMPRESS else raw[:size]
        sectors = (size + self.sector_size - 1) // self.sector_size
        count = sectors + 1 + (1 if flags & FLAG_SECTOR_CRC else 0)
        table = raw[:count * 4]
        if key is not None:
            table = _decrypt(table, (key - 1) & 0xFFFFFFFF)
        offsets = struct.unpack_from(f"<{count}I", table)
        out = bytearray()
        for s in range(sectors):
            chunk = raw[offsets[s]:offsets[s + 1]]
            if key is not None:
                chunk = _decrypt(chunk, (key + s) & 0xFFFFFFFF)
            want = min(self.sector_size, size - s * self.sector_size)
            out += _decompress(chunk, want)
        return bytes(out)

    def names(self):
        text = self.read("(listfile)").decode("latin-1")
        return [n.strip() for n in text.replace(";", "\n").splitlines() if n.strip()]
