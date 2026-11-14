"""Sinh file shini.ico cho ban Windows: o vuong bo goc xanh navy (logo Shini)
+ chu S trang dam o giua. Chay trong CI bang Python cua MSYS2 (co Pillow va
font he thong cua chinh may build). Dung: python tools/make_icon.py <out.ico>"""
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "packaging/shini.ico"
S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([4, 4, S - 4, S - 4], radius=52, fill=(16, 42, 92, 255))
d.rounded_rectangle([4, 4, S - 4, S - 4], radius=52, outline=(34, 211, 238, 255), width=6)

font = None
for path in (r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
             "/c/Windows/Fonts/segoeuib.ttf", "/c/Windows/Fonts/arialbd.ttf"):
    try:
        font = ImageFont.truetype(path, 150)
        break
    except Exception:
        continue
if font is None:
    font = ImageFont.load_default()
d.text((S / 2, S / 2 + 6), "S", font=font, fill=(255, 255, 255, 255), anchor="mm")

img.save(OUT, format="ICO",
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon ->", OUT)
