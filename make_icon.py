"""Generate icon.ico (indigo rounded square + white play triangle). Needs: pip install pillow"""
from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.24), fill="#35479E")
d.polygon([(S * 0.38, S * 0.26), (S * 0.38, S * 0.74), (S * 0.76, S * 0.5)], fill="white")
img.save("icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
