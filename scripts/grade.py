"""Colour grading of the final renders (no re-render needed).
Run:  blender -b -P grade.py            -> writes render/graded/*.png
Reads render/final/*.png, never overwrites them.
"""
import bpy, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'final')
DST = os.path.join(HERE, '..', 'graded')
os.makedirs(DST, exist_ok=True)

EXTERIOR = {'tampak_depan', 'tampak_atas', 'carport', 'denah_3d'}
# per-look settings: exposure, contrast, vibrance, shadow tint, highlight tint, glow, vignette, de-purple
LOOKS = {
    'dusk':     dict(exp=1.03, con=0.32, vib=0.22, sh=(0.93, 1.00, 1.08), hi=(1.08, 1.02, 0.91), glow=0.6, vig=0.24, depurple=1.0),
    'interior': dict(exp=1.05, con=0.22, vib=0.12, sh=(0.98, 0.99, 1.02), hi=(1.06, 1.01, 0.93), glow=0.3, vig=0.16, depurple=0.0),
}

def blur(a, r):
    """Fast approximate gaussian: three box blurs via cumulative sums (per axis)."""
    for _ in range(3):
        for ax in (0, 1):
            c = np.cumsum(np.pad(a, [(r + 1, r) if i == ax else (0, 0) for i in range(3)], mode='edge'), axis=ax)
            if ax == 0:
                a = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
            else:
                a = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
    return a

def grade(img, L):
    lum = lambda x: x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722
    x = np.clip(img * L['exp'], 0, 1)
    # neutralise the purple cast (R and B both above G in the darker areas: roof, road at dusk)
    if L['depurple']:
        g = x[..., 1]; m = np.clip(np.minimum(x[..., 0], x[..., 2]) - g, 0, None)
        w = L['depurple'] * (0.55 + 0.45 * (1 - lum(x)))[..., None]
        x = x - np.stack([m * 0.8, -m * 0.3, m * 0.4], -1) * w
    # split toning: cool shadows, warm highlights
    l = lum(x)[..., None]
    x = x * (np.array(L['sh']) * (1 - l) ** 2 + np.array(L['hi']) * l ** 2 + (1 - (1 - l) ** 2 - l ** 2))
    # gentle S-curve on luminance
    l = np.clip(lum(x), 1e-4, 1)[..., None]
    s = l * l * (3 - 2 * l)
    x = x * ((l + (s - l) * L['con']) / l)
    # vibrance: boost low-saturation colours more than saturated ones
    l = lum(x)[..., None]; sat = np.abs(x - l).max(-1, keepdims=True)
    x = l + (x - l) * (1 + L['vib'] * (1 - np.clip(sat * 2, 0, 1)))
    # glow around lamps / LEDs / bright windows
    h, w_ = x.shape[:2]; f = 4
    small = x[:h // f * f, :w_ // f * f].reshape(h // f, f, w_ // f, f, 3).mean((1, 3))
    bright = np.clip((lum(small) - 0.72) / 0.28, 0, 1)[..., None] * small
    halo = blur(bright, max(2, w_ // 180)) * np.array([1.0, 0.85, 0.65])
    halo = np.repeat(np.repeat(halo, f, 0), f, 1)
    pad = np.zeros_like(x); pad[:halo.shape[0], :halo.shape[1]] = halo
    x = 1 - (1 - np.clip(x, 0, 1)) * (1 - pad * L['glow'])
    # vignette
    yy, xx = np.mgrid[0:h, 0:w_]
    d = ((xx / w_ - 0.5) ** 2 + (yy / h - 0.5) ** 2 * 0.8) * 2
    x = x * (1 - L['vig'] * np.clip(d, 0, 1) ** 1.5)[..., None]
    # light sharpening (unsharp mask)
    x = x + (x - blur(x, 1)) * 0.35
    return np.clip(x, 0, 1)

for fn in sorted(os.listdir(SRC)):
    if not fn.endswith('.png'):
        continue
    name = fn[:-4]
    im = bpy.data.images.load(os.path.join(SRC, fn))
    w, h = im.size
    px = np.empty(w * h * 4, dtype=np.float32); im.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    out = grade(px[..., :3].astype(np.float64), LOOKS['dusk' if name in EXTERIOR else 'interior'])
    res = np.concatenate([out, np.ones((h, w, 1))], -1).astype(np.float32).ravel()
    new = bpy.data.images.new(name + '_graded', w, h)
    new.pixels.foreach_set(res)
    new.filepath_raw = os.path.join(DST, fn); new.file_format = 'PNG'; new.save()
    print('GRADED', name, flush=True)
