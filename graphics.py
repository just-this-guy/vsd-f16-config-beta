import math
from PIL import Image, ImageDraw, ImageFont

def font(size): return ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', size)

def tile(label, state, kind='toggle', index=0, count=2, offline=False, active=None):
    im = Image.new('RGB', (256, 256), '#0c0d10'); d = ImageDraw.Draw(im)
    d.rounded_rectangle((3, 3, 252, 252), radius=17, outline='#9c9da3', width=3)
    size = 37
    lines = [label]
    if font(size).getlength(label) > 232:
        words = label.split(); split = min(range(1, len(words)), key=lambda i: max(font(size).getlength(' '.join(words[:i])), font(size).getlength(' '.join(words[i:])))) if len(words) > 1 else 1
        lines = [' '.join(words[:split]), ' '.join(words[split:])]
    while any(font(size).getlength(line)>232 for line in lines) and size>29:size-=1
    for i, line in enumerate(lines): d.text((128, 31 + i * 38), line, font=font(size), anchor='mm', fill='white')
    cy = 148 if len(lines) > 1 else 131
    if kind == 'rotary' or count > 3:
        scale=.8 if len(lines)>1 else 1
        start = math.radians(205); end = math.radians(515)
        for i in range(max(count, 3)):
            a = start + (end - start) * i / max(1, max(count, 3) - 1)
            d.line((128 + 58*scale * math.cos(a), cy + 58*scale * math.sin(a), 128 + 67*scale * math.cos(a), cy + 67*scale * math.sin(a)), fill='white', width=3)
        d.ellipse((128-48*scale, cy-48*scale, 128+48*scale, cy+48*scale), outline='white', width=4)
        a = start + (end - start) * index / max(1, count - 1)
        d.line((128, cy, 128 + 41*scale * math.cos(a), cy + 41*scale * math.sin(a)), fill='white', width=7)
        d.ellipse((121, cy - 7, 135, cy + 7), fill='#0c0d10', outline='white', width=2)
    elif kind in ('button', 'nav'):
        d.rounded_rectangle((65, cy - 29, 191, cy + 29), radius=9, outline='white', width=3)
        d.text((128, cy), 'PRESS' if kind == 'button' else state, font=font(28 if kind=='button' else 40), fill='white', anchor='mm')
    else:
        d.ellipse((93, cy - 35, 163, cy + 35), outline='white', width=4)
        y = cy - 39 + index * 78 / max(1, count - 1)
        if state in ('OFF', 'CLOSE', 'SEC', 'DISC', 'EXTEND', 'LOCK'): y = cy + 39
        elif state in ('ON', 'MAIN', 'PRI', 'OPEN'): y = cy - 39
        elif state in ('BATT', 'NORM', 'AUTO', 'STBY') and count == 3: y = cy
        d.line((128, cy, 128, y), fill='white', width=14)
        d.ellipse((120, y - 8, 136, y + 8), fill='white')
    text = 'NO DATA' if offline else state
    size = 31
    while font(size).getlength(text) > 184 and size > 14: size -= 1
    if kind!='nav':d.text((138, 225), text, font=font(size), fill='white', anchor='mm')
    if kind != 'nav':
        if active is None: active = state not in ('OFF', 'CLOSE', 'PRESS')
        color = '#74777e' if offline else '#20e62c' if active else '#ff2929'
        d.ellipse((10, 216, 34, 240), fill=color)
    return im
