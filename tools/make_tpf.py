"""Pack the textures in ../source into a TexMod .tpf file.

Usage:
    python tools/make_tpf.py                 # writes Jormungand_Numbered.tpf in the repo root
    python tools/make_tpf.py other_name.tpf

A .tpf is a ZIP archive whose entries are encrypted with TexMod's fixed ZipCrypto
password, with the whole file then XOR-ed with 0x3FA43FA4. texmod.def maps each
texture hash to the file that replaces it. Only the Python standard library is needed.
"""

import os
import random
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "source")

TPF_PASSWORD = bytes([
    0x73, 0x2A, 0x63, 0x7D, 0x5F, 0x0A, 0xA6, 0xBD, 0x7D, 0x65, 0x7E, 0x67, 0x61, 0x2A, 0x7F, 0x7F,
    0x74, 0x61, 0x67, 0x5B, 0x60, 0x70, 0x45, 0x74, 0x5C, 0x22, 0x74, 0x5D, 0x6E, 0x6A, 0x73, 0x41,
    0x77, 0x6E, 0x46, 0x47, 0x77, 0x49, 0x0C, 0x4B, 0x46, 0x6F,
])
XOR_KEY = bytes([0xA4, 0x3F, 0xA4, 0x3F])
COMMENT = (b"Yen Odah\r\n"
           b"Numbered Jormungand / Frost Wurm spawn points on the Bjora Marches Mission Map [U]. "
           b"Based on XTFOX's Jormungand texmod (GPL-3.0).")


def crc32_byte(crc, byte):
    return zlib.crc32(bytes([byte]), crc ^ 0xFFFFFFFF) ^ 0xFFFFFFFF


class ZipCrypto:
    def __init__(self, password):
        self.keys = [0x12345678, 0x23456789, 0x34567890]
        for byte in password:
            self.update(byte)

    def update(self, byte):
        k = self.keys
        k[0] = crc32_byte(k[0], byte)
        k[1] = ((k[1] + (k[0] & 0xFF)) * 134775813 + 1) & 0xFFFFFFFF
        k[2] = crc32_byte(k[2], k[1] >> 24)

    def encrypt(self, data):
        out = bytearray()
        for byte in data:
            t = (self.keys[2] | 2) & 0xFFFF
            out.append(byte ^ (((t * (t ^ 1)) >> 8) & 0xFF))
            self.update(byte)
        return bytes(out)


def build_zip(entries, comment):
    body, central = b"", b""
    for name, data in entries:
        crc = zlib.crc32(data)
        compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
        compressed = compressor.compress(data) + compressor.flush()
        header = bytes(random.randrange(256) for _ in range(11)) + bytes([crc >> 24])
        encrypted = ZipCrypto(TPF_PASSWORD).encrypt(header + compressed)
        fname = name.encode()
        local = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 1, 8, 0, 0x21, crc,
                            len(encrypted), len(data), len(fname), 0) + fname
        central += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 1, 8, 0, 0x21, crc,
                               len(encrypted), len(data), len(fname), 0, 0, 0, 0, 0x20, len(body)) + fname
        body += local + encrypted
    end = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entries), len(entries),
                      len(central), len(body), len(comment)) + comment
    return body + central + end


def main():
    out_path = os.path.join(ROOT, sys.argv[1] if len(sys.argv) > 1 else "Jormungand_Numbered.tpf")
    with open(os.path.join(SOURCE, "texmod.def"), "rb") as f:
        definition = f.read()
    entries = []
    for line in definition.decode().splitlines():
        if line.strip():
            _, filename = line.strip().split("|", 1)
            with open(os.path.join(SOURCE, filename), "rb") as f:
                entries.append((filename, f.read()))
    entries.append(("texmod.def", definition))
    zip_data = build_zip(entries, COMMENT)
    with open(out_path, "wb") as f:
        f.write(bytes(b ^ XOR_KEY[i % 4] for i, b in enumerate(zip_data)))
    print(f"Wrote {out_path} ({len(entries) - 1} textures)")


if __name__ == "__main__":
    main()
