#!/usr/bin/env python3
"""make_xbox_buttons: draws the message font's controller glyphs as the Xbox 360 controller's and writes them as an
.o2r the port loads from game:\\mods (named to sort last, so it wins over texture packs).

    make_xbox_buttons.py OUT.o2r [PREVIEW.png]

Ship of Harkinian's default mapping on the Xbox 360 controller (libultraship ControllerDefaultMappings.cpp): N64 A
and B on A and B, Z on LT, R on RT, L on LB, Start on Start, the C buttons on the right stick. So A and B become
round buttons with their letter cut out (the game colours them green and red, z_message_PAL.c), Z, R and L become
LT, RT and LB, and the C buttons keep their arrows (the right stick's directions). The glyphs are drawn here from
DejaVu Sans Bold, no game data: 16x16 I4 textures under textures/nes_font_static, and the same under alt/ so a
texture pack's alternate font doesn't hide them.
"""
import struct
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SIZE = 16
# Glyph -> (shape, label).
GLYPHS = {
    "gMsgChar9FButtonATex": ("circle", "A"),
    "gMsgCharA0ButtonBTex": ("circle", "B"),
    "gMsgCharA2ButtonLTex": ("pill", "LB"),
    "gMsgCharA3ButtonRTex": ("pill", "RT"),
    "gMsgCharA4ButtonZTex": ("pill", "LT"),
}


def draw(shape, label):
    scale = 8  # drawn large, then box-filtered down for clean edges
    big = SIZE * scale
    img = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(img)
    if shape == "circle":
        d.ellipse((4, 4, big - 5, big - 5), fill=255)
        font = ImageFont.truetype(FONT, int(big * 0.62))
    else:
        d.rounded_rectangle((0, big * 0.18, big - 1, big * 0.82), radius=big * 0.22, fill=255)
        font = ImageFont.truetype(FONT, int(big * 0.46))
    box = d.textbbox((0, 0), label, font=font)
    x = (big - (box[2] - box[0])) / 2 - box[0]
    y = (big - (box[3] - box[1])) / 2 - box[1]
    d.text((x, y), label, font=font, fill=0)
    return img.resize((SIZE, SIZE), Image.BOX)


def i4(img):
    px = [p >> 4 for p in img.tobytes()]
    return bytes((px[i] << 4) | px[i + 1] for i in range(0, len(px), 2))


def texture_resource(data):
    h = bytearray(0x40)
    h[4:8] = b"XETO"  # 'OTEX' as a little-endian word
    struct.pack_into("<IQ", h, 8, 0, 0xDEADBEEFDEADBEEF)
    return bytes(h) + struct.pack("<IIII", 5, SIZE, SIZE, len(data)) + data


def main():
    out = sys.argv[1]
    previews = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, (shape, label) in GLYPHS.items():
            img = draw(shape, label)
            previews.append(img)
            res = texture_resource(i4(img))
            z.writestr("textures/nes_font_static/" + name, res)
            z.writestr("alt/textures/nes_font_static/" + name, res)
    if len(sys.argv) > 2:
        sheet = Image.new("L", (SIZE * len(previews), SIZE))
        for i, img in enumerate(previews):
            sheet.paste(img, (i * SIZE, 0))
        sheet.resize((sheet.width * 8, sheet.height * 8), Image.NEAREST).save(sys.argv[2])
    print(f"{out}: {len(GLYPHS)} glyphs")


if __name__ == "__main__":
    main()
