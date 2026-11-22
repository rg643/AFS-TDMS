"""
TDMS graphics  -  smooth (anti-aliased) pictures made with Pillow:
app icon, file-type icons, rounded buttons / cards, gradients, round avatars, charts.
No tkinter needed here, so it can be tested without a window.
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

VERSION = "8.0"
FONT_DIRS = [r"C:\Windows\Fonts", "/usr/share/fonts/truetype/liberation",
             "/usr/share/fonts/truetype/dejavu", "/Library/Fonts",
             "/System/Library/Fonts/Supplemental"]
SANS_B = ["segoeuib.ttf", "arialbd.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"]
SANS = ["segoeui.ttf", "arial.ttf", "LiberationSans-Regular.ttf", "Arial.ttf", "DejaVuSans.ttf"]


_font_cache = {}


def get_font(names, size):
    key = (tuple(names), int(size))
    f = _font_cache.get(key)
    if f is not None:
        return f
    f = None
    for n in names:
        for folder in FONT_DIRS:
            p = os.path.join(folder, n)
            if os.path.exists(p):
                try:
                    f = ImageFont.truetype(p, int(size))
                    break
                except Exception:
                    pass
        if f is not None:
            break
    if f is None:
        try:
            f = ImageFont.load_default(int(size))
        except Exception:
            f = ImageFont.load_default()
    _font_cache[key] = f
    return f


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    ra, rb = rgb(a), rgb(b)
    return "#%02X%02X%02X" % tuple(int(round(ra[i] + (rb[i] - ra[i]) * t)) for i in range(3))


# ----------------------------------------------------------------- gradients
def gradient(w, h, c1, c2, vertical=False, diagonal=False):
    """Smooth two-colour gradient image."""
    a, b = rgb(c1), rgb(c2)
    base = Image.new("RGB", (w, h), c1)
    top = Image.new("RGB", (w, h), c2)
    if diagonal:
        mask = Image.linear_gradient("L").resize((max(w, h) * 2, max(w, h) * 2))
        mask = mask.rotate(45, expand=False).crop((0, 0, w, h)) if False else mask.resize((w, h))
        # real diagonal: blend horizontal and vertical ramps
        hx = Image.linear_gradient("L").rotate(90).resize((w, h))
        vy = Image.linear_gradient("L").resize((w, h))
        mask = Image.blend(hx, vy, 0.5)
    else:
        mask = Image.linear_gradient("L").resize((w, h))
        if not vertical:
            mask = Image.linear_gradient("L").rotate(90).resize((w, h))
    del a, b
    return Image.composite(top, base, mask)


# -------------------------------------------------------------- app icon TDMS
def make_icon_image(size=1024, navy="#1F3A5F", blue="#2E6DB4", red="#E8312F", text="TDMS", simple=False):
    """Rounded-square app icon: gradient background, folded document sheet, text lines, label.
    simple=True (used for 16-48 px) leaves out the label and uses bigger shapes so it stays sharp."""
    S = size
    bg = gradient(S, S, mix(navy, "#000000", 0.25), blue, diagonal=True).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    icon.paste(bg, (0, 0), mask)
    if simple:
        d = ImageDraw.Draw(icon)
        x0, y0, x1, y1, fold = S * .24, S * .14, S * .76, S * .86, S * .20
        d.polygon([(x0, y0), (x1 - fold, y0), (x1, y0 + fold), (x1, y1), (x0, y1)], fill="#FFFFFF")
        d.polygon([(x1 - fold, y0), (x1, y0 + fold), (x1 - fold, y0 + fold)], fill="#C9D6EA")
        d.rectangle([x0, y0 + S * .12, x0 + S * .30, y0 + S * .20], fill=red)
        for i, wd in enumerate((.38, .38, .24)):
            yy = y0 + S * (.30 + .13 * i)
            d.rectangle([x0 + S * .07, yy, x0 + S * .07 + S * wd, yy + S * .06], fill=navy)
        return icon
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([-S * 0.2, -S * 0.35, S * 0.7, S * 0.45], fill=(255, 255, 255, 40))
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.04))
    icon = Image.alpha_composite(icon, Image.composite(glow, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask))
    x0, y0, x1, y1 = S * 0.22, S * 0.10, S * 0.78, S * 0.66
    fold = S * 0.17
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon([(x0, y0 + S * 0.025), (x1 - fold, y0 + S * 0.025), (x1, y0 + fold + S * 0.025), (x1, y1 + S * 0.025), (x0, y1 + S * 0.025)], fill=(0, 0, 0, 110))
    icon = Image.alpha_composite(icon, sh.filter(ImageFilter.GaussianBlur(S * 0.02)))
    d = ImageDraw.Draw(icon)
    d.polygon([(x0, y0), (x1 - fold, y0), (x1, y0 + fold), (x1, y1), (x0, y1)], fill="#FFFFFF")
    d.polygon([(x1 - fold, y0), (x1, y0 + fold), (x1 - fold, y0 + fold)], fill="#D9E2EF")
    d.rounded_rectangle([x0 + S * 0.06, y0 + S * 0.07, x0 + S * 0.26, y0 + S * 0.10], radius=S * 0.015, fill=red)
    for i, wd in enumerate((0.40, 0.40, 0.26)):
        yy = y0 + S * (0.20 + 0.085 * i)
        d.rounded_rectangle([x0 + S * 0.06, yy, x0 + S * 0.06 + S * wd, yy + S * 0.032], radius=S * 0.016, fill=navy)
    f = get_font(SANS_B, S * 0.19)
    d.text((S / 2, S * 0.82), text, font=f, fill="#FFFFFF", anchor="mm")
    d.rounded_rectangle([S * 0.40, S * 0.925, S * 0.60, S * 0.94], radius=S * 0.008, fill=red)
    return icon


def write_ico(path, images):
    """Write a Windows .ico holding one PNG picture per size (small sizes stay sharp)."""
    import io
    import struct
    blobs = []
    for im in images:
        b = io.BytesIO()
        im.save(b, "PNG")
        blobs.append(b.getvalue())
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for im, blob in zip(images, blobs):
        w, h = im.size
        out += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    with open(path, "wb") as f:
        f.write(out + b"".join(blobs))


def save_icon(png_path, ico_path=None, **kw):
    big = make_icon_image(1024, **{k: v for k, v in kw.items() if k != "simple"})
    big.resize((256, 256), Image.LANCZOS).save(png_path, "PNG")
    if ico_path:
        imgs = []
        for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
            src = make_icon_image(512, simple=True, **{k: v for k, v in kw.items() if k in ("navy", "blue", "red")}) if s <= 48 else big
            imgs.append(src.resize((s, s), Image.LANCZOS))
        write_ico(ico_path, imgs)
    return png_path


# ------------------------------------------------------- file-type + folder icons
def ft_icon(label, color, px, ss=6, inverse=False):
    """Small document icon with a coloured body and a 3-letter label.  inverse = white body (for use on a coloured tab)."""
    S = int(px) * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = S * .16, S * .04, S * .84, S * .96
    fold = S * .26
    body, ink = ("#FFFFFF", color) if inverse else (color, "#FFFFFF")
    d.polygon([(x0, y0), (x1 - fold, y0), (x1, y0 + fold), (x1, y1), (x0, y1)], fill=body)
    d.polygon([(x1 - fold, y0), (x1, y0 + fold), (x1 - fold, y0 + fold)], fill=(0, 0, 0, 55) if inverse else (255, 255, 255, 170))
    f = get_font(SANS_B, S * (0.2 if len(label) > 3 else 0.23))
    d.text((S / 2, S * .67), label, font=f, fill=ink, anchor="mm")
    for i, yy in enumerate((.34, .44)):
        d.rounded_rectangle((S * .3, S * yy, S * (.7 if i == 0 else .6), S * (yy + .04)), radius=S * .02, fill=(ink if inverse else (255, 255, 255, 200)))
    return im.resize((int(px), int(px)), Image.LANCZOS)


def tab_icon(kind, px, color="#FFFFFF", ss=6):
    """Simple glyphs for the main tabs: library, dashboard, users, activity, admin."""
    S = int(px) * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = max(2, int(S * 0.09))
    if kind == "library":
        d.rounded_rectangle((S * .08, S * .20, S * .44, S * .50), radius=S * .05, fill=color)
        d.rounded_rectangle((S * .08, S * .32, S * .92, S * .82), radius=S * .08, fill=color)
    elif kind == "dashboard":
        for x, h in ((.14, .38), (.41, .62), (.68, .84)):
            d.rounded_rectangle((S * x, S * (.9 - h), S * (x + .19), S * .9), radius=S * .04, fill=color)
    elif kind == "users":
        d.ellipse((S * .33, S * .12, S * .67, S * .46), fill=color)
        d.pieslice((S * .14, S * .54, S * .86, S * 1.20), 180, 360, fill=color)
    elif kind == "activity":
        d.line([(S * .06, S * .55), (S * .27, S * .55), (S * .38, S * .22), (S * .54, S * .84), (S * .66, S * .42), (S * .74, S * .55), (S * .94, S * .55)], fill=color, width=w, joint="curve")
    else:   # admin = sliders
        for y, kx in ((.25, .66), (.50, .34), (.75, .70)):
            d.line([(S * .10, S * y), (S * .90, S * y)], fill=color, width=w)
            d.ellipse((S * (kx - .10), S * (y - .10), S * (kx + .10), S * (y + .10)), fill=color)
    return im.resize((int(px), int(px)), Image.LANCZOS)


def folder_icon(px, color=None, ss=6):
    """Folder picture. color = the front colour (default yellow); the back is a darker shade of it."""
    S = int(px) * ss
    front = color or "#FAC846"
    back = mix(front, "#000000", 0.18)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((S * .06, S * .2, S * .45, S * .8), radius=S * .06, fill=back)
    d.rounded_rectangle((S * .06, S * .32, S * .94, S * .84), radius=S * .09, fill=front)
    return im.resize((int(px), int(px)), Image.LANCZOS)


def trash_icon(px, color="#E0713F", ss=6):
    """Outline trash can (like the Trash folder of a file manager)."""
    S = int(px) * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = max(2, int(S * 0.075))
    d.rounded_rectangle((S * .14, S * .22, S * .86, S * .31), radius=S * .03, outline=color, width=w)
    d.rounded_rectangle((S * .37, S * .08, S * .63, S * .22), radius=S * .03, outline=color, width=w)
    d.line([(S * .24, S * .36), (S * .30, S * .90), (S * .70, S * .90), (S * .76, S * .36)], fill=color, width=w, joint="curve")
    for x in (.40, .50, .60):
        d.line([(S * x, S * .48), (S * x, S * .78)], fill=color, width=max(2, int(w * .75)))
    return im.resize((int(px), int(px)), Image.LANCZOS)


def find_logo(*folders):
    for f in folders:
        for n in ("logo.png", "Logo.png"):
            p = os.path.join(str(f), n)
            if os.path.exists(p):
                return p
    return None


# ------------------------------------------------------ rounded shapes / shadow
_cache = {}


def rounded_box(w, h, radius, fill, outline=None, outline_w=1, shadow=0, shadow_alpha=60,
                shadow_dy=3, canvas_bg=None, ss=3):
    """Anti-aliased rounded rectangle (optionally with a soft drop shadow).
    The picture is w x h; the shadow lives INSIDE it, so leave `shadow` px of margin."""
    key = ("rb", w, h, radius, fill, outline, outline_w, shadow, shadow_alpha, shadow_dy, canvas_bg)
    if key in _cache:
        return _cache[key]
    w, h = max(2, int(w)), max(2, int(h))
    W, H = w * ss, h * ss
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    m = shadow * ss
    if shadow:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            [m, m + shadow_dy * ss, W - m - 1, H - m - 1 + shadow_dy * ss],
            radius=radius * ss, fill=(15, 30, 55, shadow_alpha))
        sh = sh.filter(ImageFilter.GaussianBlur(shadow * ss * 0.55))
        base = Image.alpha_composite(base, sh)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([m, m, W - m - 1, H - m - 1], radius=radius * ss, fill=fill,
                        outline=outline, width=outline_w * ss if outline else 0)
    img = base.resize((w, h), Image.LANCZOS)
    if canvas_bg:                      # flatten so Tk shows no fringe
        bgim = Image.new("RGBA", (w, h), canvas_bg)
        img = Image.alpha_composite(bgim, img)
    if len(_cache) > 400:
        _cache.clear()
    _cache[key] = img
    return img


def circle_ring(size, color, width=3, fill=None, ss=4):
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([0, 0, S - 1, S - 1], outline=color, width=width * ss, fill=fill)
    return im.resize((size, size), Image.LANCZOS)


def initials_circle(size, text, fill, fg="#FFFFFF", ss=4, ring=None):
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=fill, outline=ring, width=(3 * ss if ring else 0))
    f = get_font(SANS_B, S * 0.40)
    d.text((S / 2, S / 2), text, font=f, fill=fg, anchor="mm")
    return im.resize((size, size), Image.LANCZOS)


def hero_panel(w, h, c1, c2, accent, title, subtitle, bullets, short="WRT", logo=None):
    """Big artistic left panel for the login screen (gradient, soft circles, text)."""
    img = gradient(w, h, c1, c2, diagonal=True).convert("RGBA")
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse([-w * 0.25, h * 0.62, w * 0.55, h * 1.25], fill=(255, 255, 255, 20))
    od.ellipse([w * 0.45, -h * 0.18, w * 1.2, h * 0.42], fill=(255, 255, 255, 18))
    od.ellipse([w * 0.62, h * 0.55, w * 1.05, h * 0.95], fill=(255, 255, 255, 14))
    od.rectangle([0, 0, 6, h], fill=accent)
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img)
    pad = int(w * 0.10)
    y = int(h * 0.10)
    if logo is not None:
        lh = int(h * 0.075)
        lw = int(logo.width * lh / logo.height)
        lg = logo.resize((lw, lh), Image.LANCZOS)
        chip = rounded_box(lw + 28, lh + 20, 12, "#FFFFFF")
        img.alpha_composite(chip, (pad - 14, y - 10))
        img.alpha_composite(lg, (pad, y))
        y += lh + 40
    else:
        d.text((pad, y), short, font=get_font(SANS_B, h * 0.09), fill="#FFFFFF")
        y += int(h * 0.12)
    d.text((pad, y), title, font=get_font(SANS_B, h * 0.062), fill="#FFFFFF")
    y += int(h * 0.085)
    d.text((pad, y), subtitle, font=get_font(SANS, h * 0.030), fill=(220, 230, 245, 255))
    y += int(h * 0.11)
    for b in bullets:
        d.ellipse([pad, y + 6, pad + 12, y + 18], fill=accent)
        d.text((pad + 26, y), b, font=get_font(SANS, h * 0.030), fill="#FFFFFF")
        y += int(h * 0.075)
    return img


# ------------------------------------------------------------------- charts
def donut(size, parts, bg, big="", small="", ink="#1E2A38", muted="#6B7785", hole=0.64, ss=3):
    """parts = [(value, '#hex'), ...]  ->  smooth donut picture (RGB, flat background)."""
    S = size * ss
    im = Image.new("RGB", (S, S), bg)
    d = ImageDraw.Draw(im)
    box = [S * 0.04, S * 0.04, S * 0.96, S * 0.96]
    total = sum(v for v, _c in parts)
    if total <= 0:
        d.ellipse(box, outline=mix(bg, "#8899AA", 0.35), width=int(S * 0.13))
    else:
        a = -90.0
        for v, col in parts:
            if v <= 0:
                continue
            sweep = 360.0 * v / total
            d.pieslice(box, a, a + sweep - (1.2 if len(parts) > 1 else 0), fill=col)
            a += sweep
        r = (box[2] - box[0]) / 2 * hole
        c = S / 2
        d.ellipse([c - r, c - r, c + r, c + r], fill=bg)
    if total <= 0:
        r = (box[2] - box[0]) / 2 * hole
        c = S / 2
        d.ellipse([c - r, c - r, c + r, c + r], fill=bg)
    if big:
        d.text((S / 2, S * (0.46 if small else 0.5)), str(big), font=get_font(SANS_B, S * 0.17),
               fill=ink, anchor="mm")
    if small:
        d.text((S / 2, S * 0.62), small, font=get_font(SANS, S * 0.07), fill=muted, anchor="mm")
    return im.resize((size, size), Image.LANCZOS)


def bars(w, h, labels, values, color, bg, ink="#1E2A38", muted="#6B7785", grid="#E3E8EF",
         vmax=None, highlight=None, ss=3, value_labels=True):
    """Vertical bar chart (rounded bar tops).  highlight = index drawn in a stronger colour."""
    W, H = w * ss, h * ss
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    n = max(1, len(values))
    vmax = vmax or max(max(values or [1]), 1)
    left, right, top, bottom = 10 * ss, 10 * ss, 22 * ss, 26 * ss
    ph = H - top - bottom
    f_l = get_font(SANS, 10 * ss)
    f_v = get_font(SANS_B, 10 * ss)
    for k in range(5):
        y = top + ph * k / 4
        d.line([left, y, W - right, y], fill=grid, width=max(1, ss // 2))
    slot = (W - left - right) / n
    bw = min(slot * 0.58, 46 * ss)
    for i, v in enumerate(values):
        cx = left + slot * (i + 0.5)
        bh = ph * (v / vmax) if vmax else 0
        col = color if highlight is None or i == highlight else mix(color, bg, 0.45)
        if bh > 0:
            d.rounded_rectangle([cx - bw / 2, top + ph - bh, cx + bw / 2, top + ph],
                                radius=min(6 * ss, bw / 2), fill=col)
            if value_labels:
                d.text((cx, top + ph - bh - 4 * ss), str(v), font=f_v, fill=ink, anchor="ms")
        d.text((cx, H - 8 * ss), str(labels[i]), font=f_l, fill=muted, anchor="ms")
    return im.resize((w, h), Image.LANCZOS)


def hbars(w, h, items, color, bg, ink="#1E2A38", muted="#6B7785", track="#E3E8EF", ss=3, colors=None, suffix="", label_w=150):
    """Horizontal bars: items = [(label, value)].  colors = one colour per bar (optional)."""
    W, H = w * ss, h * ss
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    if not items:
        d.text((W / 2, H / 2), "No data yet", font=get_font(SANS, 12 * ss), fill=muted, anchor="mm")
        return im.resize((w, h), Image.LANCZOS)
    vmax = max(v for _l, v in items) or 1
    row = H / max(len(items), 1)
    f = get_font(SANS, 11 * ss)
    fb = get_font(SANS_B, 11 * ss)
    lab_w = label_w * ss
    for i, (lab, v) in enumerate(items):
        cy = row * (i + 0.5)
        bh = min(14 * ss, row * 0.5)
        d.text((4 * ss, cy), str(lab)[:24] + ("..." if len(str(lab)) > 24 else ""), font=f, fill=ink, anchor="lm")
        x0, x1 = lab_w, W - (52 if suffix else 34) * ss
        d.rounded_rectangle([x0, cy - bh / 2, x1, cy + bh / 2], radius=bh / 2, fill=track)
        if v:
            d.rounded_rectangle([x0, cy - bh / 2, x0 + max(bh, (x1 - x0) * v / vmax), cy + bh / 2], radius=bh / 2, fill=(colors[i] if colors else color))
        d.text((W - 4 * ss, cy), f"{v}{suffix}", font=fb, fill=ink, anchor="rm")
    return im.resize((w, h), Image.LANCZOS)


def area(w, h, labels, values, color, bg, ink="#1E2A38", muted="#6B7785", grid="#E3E8EF", ss=3):
    """Smooth trend: filled area + line + dots + value labels."""
    W, H = w * ss, h * ss
    base = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(base)
    n = max(1, len(values))
    left, right, top, bottom = 30 * ss, 14 * ss, 22 * ss, 28 * ss
    ph, pw = H - top - bottom, W - left - right
    vmax = max(4, max(values or [1]))
    vmax = -(-vmax // 4) * 4
    f, fb = get_font(SANS, 10 * ss), get_font(SANS_B, 10 * ss)
    for k in range(5):
        y = top + ph * k / 4
        d.line([left, y, W - right, y], fill=grid, width=max(1, ss // 2))
        d.text((left - 6 * ss, y), str(vmax - vmax * k // 4), font=f, fill=muted, anchor="rm")
    pts = [(left + (pw * i / max(1, n - 1) if n > 1 else pw / 2), top + ph - ph * v / vmax) for i, v in enumerate(values)]
    if len(pts) > 1:
        r, gg, b = rgb(color)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(ov).polygon(pts + [(pts[-1][0], top + ph), (pts[0][0], top + ph)], fill=(r, gg, b, 55))
        base = Image.alpha_composite(base, ov)
        d = ImageDraw.Draw(base)
        d.line(pts, fill=color, width=3 * ss, joint="curve")
    for i, (x, y) in enumerate(pts):
        d.ellipse([x - 4 * ss, y - 4 * ss, x + 4 * ss, y + 4 * ss], fill="#FFFFFF", outline=color, width=2 * ss)
        if values[i]:
            d.text((x, y - 10 * ss), str(values[i]), font=fb, fill=ink, anchor="ms")
        if i % max(1, n // 8) == 0 or i == n - 1:
            d.text((x, H - 8 * ss), str(labels[i]), font=f, fill=muted, anchor="ms")
    return base.convert("RGB").resize((w, h), Image.LANCZOS)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    save_icon(os.path.join(here, "app_icon.png"), os.path.join(here, "app_icon.ico"))
    print("icon written")


# ------------------------------------------------------------------ login screen background
LOGIN_PRESETS = {"ocean": ("#DCE8F8", "#F8FAFE", "blue", "Ocean"), "midnight": ("#0A1424", "#23456F", "white", "Midnight"),
                 "sunrise": ("#FFEDE7", "#FFD9CF", "accent", "Sunrise"), "slate": ("#E9EDF3", "#D3DBE6", "navy", "Slate")}


def login_background(w, h, preset="ocean", accent="#E8312F", blue="#2E6DB4", navy="#1F3A5F"):
    """Soft full-window gradient with large faint circles (made at half size, then smoothly enlarged)."""
    c1, c2, tint, _n = LOGIN_PRESETS.get(preset, LOGIN_PRESETS["ocean"])
    W_, H_ = max(2, int(w)), max(2, int(h))
    sw, sh = max(2, W_ // 2), max(2, H_ // 2)
    hx = Image.linear_gradient("L").rotate(90).resize((sw, sh))
    vy = Image.linear_gradient("L").resize((sw, sh))
    mask = Image.blend(hx, vy, 0.5)
    img = Image.composite(Image.new("RGB", (sw, sh), c2), Image.new("RGB", (sw, sh), c1), mask).convert("RGBA")
    col = {"blue": blue, "white": "#FFFFFF", "accent": accent, "navy": navy}[tint]
    r, g_, b = rgb(col)
    a = 22 if tint == "white" else 30
    ov = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse([-sw * 0.15, sh * 0.55, sw * 0.35, sh * 1.35], fill=(r, g_, b, a))
    d.ellipse([sw * 0.60, -sh * 0.40, sw * 1.15, sh * 0.45], fill=(r, g_, b, a))
    d.ellipse([sw * 0.80, sh * 0.62, sw * 1.06, sh * 1.06], fill=(r, g_, b, int(a * 0.7)))
    d.ellipse([sw * 0.06, -sh * 0.22, sw * 0.28, sh * 0.12], fill=(r, g_, b, int(a * 0.6)))
    img = Image.alpha_composite(img, ov).filter(ImageFilter.GaussianBlur(max(1, min(sw, sh) * 0.004)))
    return img.convert("RGB").resize((W_, H_), Image.BILINEAR)
