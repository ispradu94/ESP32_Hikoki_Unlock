"""Generates icon.ico: a battery whose body contains a bold letter H."""
from PIL import Image, ImageDraw

S = 1024  # draw large, then downscale for smooth edges
GREEN = (8, 128, 77, 255)
DARK = (14, 20, 17, 255)
WHITE = (255, 255, 255, 255)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# battery body + terminal on the right
d.rounded_rectangle((40, 240, 880, 784), radius=120, fill=GREEN)
d.rounded_rectangle((72, 272, 848, 752), radius=90, fill=DARK)
d.rounded_rectangle((880, 400, 984, 624), radius=40, fill=GREEN)

# bold H centered in the body
x0, x1, y0, y1, t = 250, 670, 330, 694, 100
d.rectangle((x0, y0, x0 + t, y1), fill=WHITE)
d.rectangle((x1 - t, y0, x1, y1), fill=WHITE)
d.rectangle((x0, (y0 + y1) // 2 - t // 2 + 10, x1, (y0 + y1) // 2 + t // 2 - 10), fill=WHITE)

img.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.resize((256, 256), Image.LANCZOS).save("icon.png")
