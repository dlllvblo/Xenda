from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs('static/icons', exist_ok=True)

for size in [192, 512]:
    img = Image.new('RGB', (size, size), color=(110, 21, 46))
    draw = ImageDraw.Draw(img)
    font_size = int(size * 0.55)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', font_size)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), 'X', font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1]
    draw.text((x, y), 'X', fill='white', font=font)
    img.save(f'static/icons/icon-{size}.png')
    print(f'Generado icon-{size}.png')