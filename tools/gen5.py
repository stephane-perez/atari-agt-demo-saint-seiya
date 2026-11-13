#!/usr/bin/env python3
"""Generate AGT source assets for the 5-character run (Seiya, Shiryu, Hyoga, Shun, Ikki):
joint 16-colour STE palette (slot 0 = background-only sky colour), per-character sprite sheets, redrawn background."""
import json, math, random, struct, sys, os
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sff
ROOT = os.path.dirname(HERE)
OUT = ROOT + '/source_assets/'
os.makedirs(OUT, exist_ok=True)
C = os.environ.get('CHARS', ROOT + '/chars') + '/'   # your own Mugen character folders (not included)
# name, sff, palette source, frame ids, run sequence (indices into frame ids), Mugen ticks per image
CHARS = [
 ('seiya',  ''+C+'Seiya de Pegaso III/'+'seiya2.sff', 'sff', [(100, i) for i in range(5)], [0, 1, 2, 0, 3, 4], 4),
 ('shiryu', C+'Shiryu/shiryu/shiryu.sff', C+'Shiryu/shiryu/001.act', [(100, i) for i in range(2, 8)], [0, 1, 2, 3, 4, 5], 5),
 ('hyoga',  C+'Hyoga2/Hyoga de Cisne/Cisne_Hyoga.sff', C+'Hyoga2/Hyoga de Cisne/Hyoga1.act', [(100, i) for i in range(7)], list(range(7)), 5),
 ('shun',   C+'Shun/Shun2/Andromeda.sff', 'sff', [(101, i) for i in range(6)], list(range(6)), 6),
 ('ikki',   C+'Phoenix/Phoenix/Phoenix.sff', C+'Phoenix/Phoenix/001.act', [(100, i) for i in range(8)], list(range(8)), 5),
]
AIRS = {'seiya': ''+C+'Seiya de Pegaso III/'+'seiya2.air', 'shiryu': C+'Shiryu/shiryu/shiryu.air', 'hyoga': C+'Hyoga2/Hyoga de Cisne/Cisne_Hyoga.air',
        'shun': C+'Shun/Shun2/Andromeda.air', 'ikki': C+'Phoenix/Phoenix/Phoenix.air'}
def air_action(path, num):
    import re
    out = []; cur = None
    for ln in open(path, errors='replace'):
        ln = ln.split(';')[0].strip()
        m = re.match(r'\[Begin Action\s+(\d+)', ln, re.I)
        if m: cur = int(m.group(1)); continue
        if cur != num or ln.lower().startswith('clsn') or ln.lower().startswith('loopstart'): continue
        m = re.match(r'(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)', ln)
        if m: out.append(((int(m.group(1)), int(m.group(2))), int(m.group(5))))
    return out
BGW = float(os.environ.get('BGW', '0.6'))          # weight of the background anchor colours in the palette search

def srgb2lab(rgb):
    c = np.asarray(rgb, float) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)
def ste_rgb(c4): return tuple(int(v) * 17 for v in c4)

# ---------------- load frames (RGB, aligned on the Mugen axis) ----------------
chars = []
for name, path, palsrc, ids, seq, ticks in CHARS:
    S = sff.load(path); d = {(s['group'], s['index']): s for s in S}
    if palsrc == 'sff': pal = d[ids[0]]['pal']
    else:
        a = open(palsrc, 'rb').read()[:768]
        pal = bytes(sum(([a[(255 - i) * 3 + k] for k in range(3)] for i in range(256)), []))
    jump = air_action(AIRS[name], 42); jids = [k for k, _ in jump]
    for k in jids: assert k in d, (name, k)
    fr = [d[i] for i in ids + jids]
    ax = max(f['x'] for f in fr); top = max(f['y'] for f in fr)
    right = max(f['w'] - f['x'] for f in fr); bot = max(f['h'] - f['y'] for f in fr)
    W = ax + right; H = top + bot
    imgs = []
    for f in fr:
        rgb = np.zeros((H, W, 3), np.uint8); m = np.zeros((H, W), bool)
        ox = ax - f['x']; oy = top - f['y']
        for r, row in enumerate(f['rows']):
            for c, v in enumerate(row):
                if v: rgb[oy + r, ox + c] = tuple(pal[v * 3:v * 3 + 3]); m[oy + r, ox + c] = True
        imgs.append((rgb, m))
    # trim empty columns/rows common to all frames (keep axis bookkeeping)
    allm = np.any([m for _, m in imgs], axis=0)
    xs = np.where(allm.any(0))[0]; ys = np.where(allm.any(1))[0]
    x0, x1, y0, y1 = xs[0], xs[-1] + 1, ys[0], ys[-1] + 1
    imgs = [(r[y0:y1, x0:x1], m[y0:y1, x0:x1]) for r, m in imgs]
    chars.append(dict(name=name, jump=jump, nrun=len(ids), imgs=imgs, seq=seq, ticks=ticks, W=x1 - x0, H=y1 - y0, ax=ax - x0, ay=top - y0, nfr=len(imgs)))
    print(name, 'frames', len(imgs), 'cell', x1 - x0, 'x', y1 - y0, 'axis', ax - x0, top - y0)

# ---------------- joint palette ----------------
pts = []; wts = []
for ch in chars:
    cnt = {}
    for rgb, m in ch['imgs']:
        for c in map(tuple, rgb[m]): cnt[c] = cnt.get(c, 0) + 1
    tot = sum(cnt.values())
    for c, n in cnt.items(): pts.append(c); wts.append(n / tot)           # every character weighs the same
SKY = (1, 1, 4)                                                          # slot 0 : sky top (sprites never use slot 0)
anchors = [(3, 3, 8), (5, 5, 11), (9, 10, 15), (12, 8, 2), (14, 10, 6)]   # sky blues / road
for a in anchors: pts.append(ste_rgb(a)); wts.append(BGW / len(anchors) * len(chars) / 5 * 0 + BGW / len(anchors))
pts = np.array(pts); wts = np.array(wts); lab = srgb2lab(pts)
rng = np.random.RandomState(7)
K = 15
def kmeans(lab, w, K, rng, snap):
    # k-means++ init
    cen = [lab[rng.choice(len(lab), p=w / w.sum())]]
    for _ in range(K - 1):
        d = np.min([((lab - c) ** 2).sum(1) for c in cen], axis=0) * w
        cen.append(lab[rng.choice(len(lab), p=d / d.sum())])
    cen = np.array(cen)
    for it in range(60):
        d = ((lab[:, None, :] - cen[None]) ** 2).sum(2); a = d.argmin(1)
        for k in range(K):
            s = a == k
            if s.any(): cen[k] = (lab[s] * w[s, None]).sum(0) / w[s].sum()
        if snap and it > 30:   # snap to 4-bit STE grid through RGB
            rgb = np.array([ste_rgb(c4) for c4 in snapp(cen)])
            cen = srgb2lab(rgb)
    d = ((lab[:, None, :] - cen[None]) ** 2).sum(2)
    return cen, (d.min(1) * w).sum()
def lab2srgb(l):
    fy = (l[..., 0] + 16) / 116; fx = fy + l[..., 1] / 500; fz = fy - l[..., 2] / 200
    f = np.stack([fx, fy, fz], -1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * np.array([0.95047, 1.0, 1.08883])
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    c = xyz @ np.linalg.inv(M).T; c = np.clip(c, 0, 1)
    return np.where(c > 0.0031308, 1.055 * c ** (1 / 2.4) - 0.055, 12.92 * c) * 255
def snapp(cen):
    return np.clip(np.rint(lab2srgb(cen) / 17), 0, 15).astype(int)
best = None
for trial in range(12):
    cen, err = kmeans(lab, wts, K, np.random.RandomState(100 + trial), True)
    if best is None or err < best[1]: best = (cen, err)
pal15 = sorted({tuple(int(v) for v in c) for c in snapp(best[0])}, key=lambda c: (0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]))
while len(pal15) < 15: pal15.append(pal15[-1])
PAL = [SKY] + pal15
print('palette', PAL, 'err', best[1])
palrgb = np.array([ste_rgb(c) for c in PAL]); pallab = srgb2lab(palrgb)
def ste(c): return sum((((n & 1) << 3) | (n >> 1)) << sh for n, sh in zip(c, (8, 4, 0)))
open(OUT + 'pal.pi1', 'wb').write(struct.pack('>H', 0) + b''.join(struct.pack('>H', ste(c)) for c in PAL) + bytes(32000))
flat = []
for c in PAL: flat += [v * 17 for v in c]
def pimage(arr):
    im = Image.fromarray(arr.astype('uint8'), 'P'); im.putpalette(flat + [0] * (768 - len(flat))); return im

# ---------------- sprite sheets (index 0 = transparent, indices 1..15 = palette slots) ----------------
meta = {}
for ch in chars:
    W, H, n = ch['W'], ch['H'], ch['nfr']
    sheet = np.zeros((H, W * n), int)
    for k, (rgb, m) in enumerate(ch['imgs']):
        l = srgb2lab(rgb[m].astype(float)); d = ((l[:, None, :] - pallab[None, 1:, :]) ** 2).sum(2)
        idx = np.zeros((H, W), int); idx[m] = d.argmin(1) + 1
        sheet[:, k * W:(k + 1) * W] = idx
    pimage(sheet).save(OUT + ch['name'] + '_sheet.png')
    jt = [t for _, t in ch['jump']]; cum = []; acc = 0
    for t in jt[:-1]: acc += max(1, t); cum.append(acc)
    meta[ch['name']] = dict(jseq=[ch['nrun'] + i for i in range(len(jt))], jcum=cum, W=int(W), H=int(H), ax=int(ch['ax']), ay=int(ch['ay']), nfr=int(n), seq=[int(v) for v in ch['seq']], ticks=int(ch['ticks']))
json.dump(meta, open(OUT + 'meta.json', 'w'), indent=1)

# ---------------- background 320x208 (period 320), drawn with the joint palette ----------------
Wb, Hb = 320, 208
bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
def near(c4):
    l = srgb2lab(np.array(ste_rgb(c4), float)); return int(((pallab - l) ** 2).sum(1).argmin())
def dpick(y, x, c4):
    """ordered dither between the two palette entries that best approximate colour c4 (4-bit RGB, may be fractional)"""
    t = np.array([v * 17 for v in c4], float); l = srgb2lab(t)
    d = ((pallab - l) ** 2).sum(1); i1 = int(d.argmin())
    best = None
    for i2 in range(16):
        if i2 == i1: continue
        a, b = pallab[i1], pallab[i2]; ab = b - a; s = float(np.clip(((l - a) @ ab) / (ab @ ab), 0, 1))
        e = ((a + ab * s - l) ** 2).sum()
        if best is None or e < best[0]: best = (e, i2, s)
    return best[1] if best[2] > bayer[y & 3, x & 3] else i1
bg = np.zeros((Hb, Wb), int)
SKYC = [(1, 1, 4), (3, 3, 8), (4, 4, 9), (9, 10, 15)]
HORIZON = 150
for y in range(Hb):
    t = min(1.0, y / HORIZON) * (len(SKYC) - 1); k = min(int(t), len(SKYC) - 2); f = t - k
    c = tuple(SKYC[k][j] * (1 - f) + SKYC[k + 1][j] * f for j in range(3))
    for x in range(Wb): bg[y, x] = dpick(y, x, c)
rng = random.Random(1990)
for _ in range(46):
    sx, sy = rng.randrange(Wb), rng.randrange(4, 88)
    bg[sy, sx] = near((15, 15, 15))
    if rng.random() < .25:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)): bg[sy + dy, (sx + dx) % Wb] = near((9, 10, 15))
mx, my, R = 250, 44, 20
for y in range(my - 34, my + 35):
    for x in range(mx - 34, mx + 35):
        d = math.hypot(x - mx, y - my)
        if d <= R:
            lit = math.hypot(x - (mx - 5), y - (my - 4)) <= R - 3
            bg[y, x % Wb] = near((15, 15, 15) if lit else (11, 12, 15))
        elif d <= R + 9 and (x + y) % 2 == 0: bg[y, x % Wb] = near((9, 10, 15))
def ridge(x, base, amp, ks, ph): return base - sum(a * math.sin(2 * math.pi * k * x / Wb + p) for a, k, p in zip(amp, ks, ph))
GROUND = 172
for x in range(Wb):
    h1 = ridge(x, 128, (14, 9, 5, 3), (2, 3, 5, 9), (0.4, 1.9, 0.7, 2.6))
    h2 = ridge(x, 146, (9, 6, 3), (3, 4, 8), (2.2, 0.3, 1.1))
    for y in range(int(h1), GROUND):
        e = y - int(h1); t = min(1, (y - h1) / 60)
        bg[y, x] = near((4, 4, 9)) if e < 2 else dpick(y, x, tuple(a * (1 - t) + b * t for a, b in zip((3, 4, 5), (3, 3, 8))))
    for y in range(int(h2), GROUND):
        e = y - int(h2); t = min(1, (y - h2) / 40) * 0.7
        bg[y, x] = near((3, 4, 5)) if e < 2 else dpick(y, x, tuple(a * (1 - t) + b * t for a, b in zip((3, 3, 8), (3, 1, 0))))
BEAM0, BEAM1 = 60, 84
for y in range(BEAM0, BEAM1):
    for x in range(Wb):
        if y < BEAM0 + 3: c = (15, 15, 15)
        elif y < BEAM0 + 7: c = (11, 12, 15)
        elif y < BEAM0 + 10: c = (9, 10, 15)
        elif y < BEAM1 - 3: c = (3, 3, 8) if (x % 16) in (2, 3, 5, 6, 8, 9) else (11, 12, 15)
        elif y < BEAM1 - 1: c = (9, 10, 15)
        else: c = (3, 4, 5)
        bg[y, x] = near(c)
for cx in range(40, Wb, 80):
    for y in range(BEAM1, GROUND):
        cap = y < BEAM1 + 7; base = y >= GROUND - 9; half = 14 if (cap or base) else 10
        for dx in range(-half, half + 1):
            u = (dx + half) / (2.0 * half)
            if cap or base:
                c = (15, 15, 15) if u < .25 else ((11, 12, 15) if u < .7 else (9, 10, 15))
                if y == BEAM1 + 6 or y == GROUND - 9: c = (4, 4, 9)
            else:
                c = (15, 15, 15) if u < .2 else ((11, 12, 15) if u < .6 else ((9, 10, 15) if u < .85 else (4, 4, 9)))
                if dx % 4 == 0 and 0.2 < u < .85: c = (9, 10, 15) if c == (11, 12, 15) else c
            bg[y, (cx + dx) % Wb] = near(c)
for y in range(GROUND, Hb):
    r = y - GROUND
    for x in range(Wb):
        if r == 0: c = (14, 12, 10)
        elif r < 4: c = (14, 10, 6)
        elif r == 4: c = (3, 1, 0)
        else:
            row = (r - 5) // 11; ry = (r - 5) % 11; off = 20 if row & 1 else 0
            if ry == 10: c = (3, 1, 0)
            elif (x + off) % 40 == 0: c = (3, 1, 0)
            elif ry == 0 or (x + off) % 40 == 1: c = (14, 10, 6)
            else: c = (12, 8, 2) if bayer[y & 3, x & 3] > .35 * row else (10, 3, 2)
            if row == 0 and c == (12, 8, 2) and (x * 7 + y * 3) % 31 == 0: c = (14, 10, 6)
        bg[y, x] = dpick(y, x, c) if r >= 5 else near(c)
pimage(bg).save(OUT + 'bg_one.png')
NCOPY = int(sys.argv[1]) if len(sys.argv) > 1 else 100
pimage(np.tile(bg, (1, NCOPY))).save(OUT + 'bg.png')
# preview: palette swatches, background (2 periods) with all 5 runners at the target positions
prev = pimage(np.tile(bg, (1, 2))[:200]).convert('RGB').crop((0, 0, 320, 200))
SH = [24 + 32 * k for k in range(5)]                                    # placeholder x: finalised in the C++ (axis positions)
pv = prev.copy()
ground_y = 180
order = ['ikki', 'shun', 'hyoga', 'shiryu', 'seiya']
axx = {nm: 4 + 0 for nm in order}
x0 = None
for k, nm in enumerate(order):
    m = meta[nm]; sh = Image.open(OUT + nm + '_sheet.png').convert('RGBA')
    cell = sh.crop((0, 0, m['W'], m['H']))
    a = np.array(cell); a[..., 3] = np.where(np.array(Image.open(OUT + nm + '_sheet.png'))[:, :m['W']] == 0, 0, 255)
    cell = Image.fromarray(a)
    if k == 0: x0 = 2 + m['ax']
    pv.paste(cell, (x0 + 32 * k - m['ax'], ground_y - m['ay']), cell)
pv.resize((640, 400), Image.NEAREST).save(ROOT+'/build/preview_all.png')
sw = Image.new('RGB', (16 * 24, 24))
for i, c in enumerate(PAL): sw.paste(ste_rgb(c), (i * 24, 0, i * 24 + 24, 24))
sw.save(ROOT+'/build/preview_pal.png')
print('ok')

# ---------------- C++ table for the demo (positions: axis of the first = Ikki near the left border, +32 px each) ----------------
GROUND_Y = 180; MARGIN = 2; STEP = 32
order = ['ikki', 'shun', 'hyoga', 'shiryu', 'seiya']
tbl = ['// generated by gen5.py - do not edit', '#pragma once', '']
for nm in order:
    m = meta[nm]
    tbl.append('static const s16 c_seq_%s[%d] = { %s };' % (nm, len(m['seq']), ', '.join(map(str, m['seq']))))
    tbl.append('static const s16 c_jseq_%s[%d] = { %s };' % (nm, len(m['jseq']), ', '.join(map(str, m['jseq']))))
    tbl.append('static const s16 c_jcum_%s[%d] = { %s };' % (nm, len(m['jcum']), ', '.join(map(str, m['jcum']))))
tbl += ['', 'struct rundef_t { const s16 *seq; s16 len; s16 thresh; s16 left; s16 top; s16 w; s16 h; const s16 *jseq; s16 jlen; const s16 *jcum; s16 ax; s16 ay; };',
        '// index = order of appearance from the left; thresh = 5 x Mugen ticks (animation 2x slower than Mugen at 50Hz: +3 per VBL)',
        'static const rundef_t c_rundefs[%d] =' % len(order), '{']
axis0 = MARGIN + meta['ikki']['ax']
for k, nm in enumerate(order):
    m = meta[nm]; left = axis0 + STEP * k - m['ax']; top = GROUND_Y - m['ay']
    tbl.append('\t{ c_seq_%s, %d, %d, %d, %d, %d, %d, c_jseq_%s, %d, c_jcum_%s, %d, %d },\t// %s' % (nm, len(m['seq']), 5 * m['ticks'], left, top, m['W'], m['H'], nm, len(m['jseq']), nm, m['ax'], m['ay'], nm))
tbl.append('};')
open(ROOT+'/saints_tbl.h', 'w').write('\n'.join(tbl) + '\n')
print('\n'.join(tbl[-8:]))
