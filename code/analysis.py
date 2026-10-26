"""Step 3. Hex shares, fitted boundaries, sharpness, comparisons with Norse names, the Danelaw line
and the national borders. Writes data/hex_shares.csv, data/boundaries.geojson, data/results.json
and work/site_data.json (compact arrays for the page).

Method notes
  * Hexes are 10 km across (flat side to flat side) on the British National Grid.
  * Boundaries: for a pair of words A and B, I bin the points of each word on a 2 km grid and smooth
    each with a Gaussian kernel. P(A) = KA / (KA + KB). The kernel width is picked per pair from
    6, 8, 10, 14 and 20 km by leave-one-out likelihood. The 50% contour of P(A) is the boundary,
    drawn only where at least 5 kernel-weighted points of A or B are nearby and on land.
  * Sharpness: for every A or B point within 60 km of the line I take its signed distance to the
    line and fit a logistic regression of "is A" on that distance. The distance over which the
    fitted share falls from 80% to 20% is 2 ln 4 / slope. A 95% interval comes from 300 bootstrap
    resamples. The same fit is repeated on 60 km stretches of line for the local colouring.
  * Correlations are Spearman rank correlations between hexes, with a spatial block bootstrap
    (100 km blocks) for the interval, because neighbouring hexes are not independent.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy import ndimage
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from shapely.geometry import LineString, Point, Polygon
from skimage import measure
import statsmodels.api as sm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import words  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, "..", "osnames_gb.tsv")
TO_LL = Transformer.from_crs(27700, 4326, always_xy=True)
TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)
RNG = np.random.default_rng(1066)

FAMS = ["stream", "valley", "hill", "fall", "settlement"]
f = pd.read_csv(os.path.join(ROOT, "work", "features.csv"), keep_default_na=False)
f["county"] = f["county"].map(lambda c: c.split(" - ")[-1].strip() if " - " in c else c)
f["norse"] = (f.family == "settlement") & (f.via == "norse")
allos = pd.read_csv(TSV, sep="\t", usecols=["x", "y", "country"], dtype={"country": str})
META = words.word_meta()
R = {}

# ---------------------------------------------------------------- counts
R["n_features"] = {fam: int((f.family == fam).sum()) for fam in FAMS}
R["n_matched"] = {fam: int(((f.family == fam) & (f.word != "")).sum()) for fam in FAMS}
R["n_via_name2"] = int((f.via == "name2").sum())
R["n_osnames"] = int(len(allos))
st = pd.read_csv(os.path.join(ROOT, "work", "streams.csv"), keep_default_na=False)
R["streams"] = dict(n_watercourses=int(len(st)), n_links=int(st.n_links.sum()), n_names=int(st.name.nunique()))
counts = {}
for fam in FAMS:
    s = f[(f.family == fam) & (f.word != "")]
    vc = s.word.value_counts()
    counts[fam] = {w: dict(n=int(n), england=int(((s.word == w) & (s.country == "England")).sum()),
                           wales=int(((s.word == w) & (s.country == "Wales")).sum()),
                           scotland=int(((s.word == w) & (s.country == "Scotland")).sum()))
                   for w, n in vc.items()}
R["counts"] = counts
R["n_norse_settlements"] = int(f.norse.sum())

# ---------------------------------------------------------------- hex grid
HW = 10000.0
HR = HW / math.sqrt(3)


def hex_of(x, y):
    q = (math.sqrt(3) / 3 * x - y / 3) / HR
    r = (2 / 3 * y) / HR
    # cube rounding
    cx, cz = q, r
    cy = -cx - cz
    rx, ry, rz = round(cx), round(cy), round(cz)
    dx, dy, dz = abs(rx - cx), abs(ry - cy), abs(rz - cz)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def hex_centre(q, r):
    return HR * math.sqrt(3) * (q + r / 2), HR * 1.5 * r


hq = np.vectorize(hex_of)
allos["q"], allos["r"] = hq(allos.x.values, allos.y.values)
f["q"], f["r"] = hq(f.x.values, f.y.values)
land = allos.groupby(["q", "r"]).agg(n=("x", "size"), country=("country", lambda s: s.value_counts().index[0])).reset_index()
land = land[land.n >= 2].reset_index(drop=True)
land["hid"] = np.arange(len(land))
HID = {(q, r): i for i, (q, r) in enumerate(zip(land.q, land.r))}
f["hid"] = [HID.get((q, r), -1) for q, r in zip(f.q, f.r)]
cxy = np.array([hex_centre(q, r) for q, r in zip(land.q, land.r)])
land["cx"], land["cy"] = cxy[:, 0], cxy[:, 1]
lon, lat = TO_LL.transform(cxy[:, 0], cxy[:, 1])
land["lon"], land["lat"] = np.round(lon, 4), np.round(lat, 4)
ccounty = f[f.hid >= 0].groupby("hid").county.agg(lambda s: s.value_counts().index[0])
land["county"] = land.hid.map(ccounty).fillna("")

fam_tot = f[f.hid >= 0].groupby(["hid", "family"]).size().unstack(fill_value=0)
wc = f[(f.hid >= 0) & (f.word != "")].groupby(["hid", "family", "word"]).size().rename("n").reset_index()
wc["n_family"] = [int(fam_tot.loc[h, fm]) for h, fm in zip(wc.hid, wc.family)]
wc["share"] = (wc.n / wc.n_family).round(4)
norse_h = f[(f.family == "settlement") & (f.hid >= 0)].groupby("hid").agg(n=("norse", "size"), k=("norse", "sum"))
nz = norse_h[norse_h.k > 0]
extra = pd.DataFrame(dict(hid=nz.index, family="settlement", word="norse_any", n=nz.k.astype(int).values,
                          n_family=nz.n.values, share=(nz.k / nz.n).round(4).values))
wc = pd.concat([wc, extra], ignore_index=True)
out = wc.merge(land[["hid", "lon", "lat", "country", "county"]], on="hid")
out = out.rename(columns={"hid": "hex_id"})[["hex_id", "lon", "lat", "country", "county", "family", "word", "n", "n_family", "share"]]
out.sort_values(["hex_id", "family", "word"]).to_csv(os.path.join(ROOT, "data", "hex_shares.csv"), index=False)
R["hex"] = dict(n_hex=int(len(land)), width_km=10, area_km2=round(HW * HW * math.sqrt(3) / 2 / 1e6, 1))

# hex polygons in lon/lat for the web map
hex_poly = []
ang = [math.radians(30 + 60 * i) for i in range(6)]
for cx_, cy_ in cxy:
    xs = [cx_ + HR * math.cos(a) for a in ang]
    ys = [cy_ + HR * math.sin(a) for a in ang]
    lo, la = TO_LL.transform(xs, ys)
    hex_poly.append([v for pair in zip(np.round(la, 3), np.round(lo, 3)) for v in pair])

# ---------------------------------------------------------------- raster for boundaries
CELL = 2000.0
X0, Y0, NX, NY = 0.0, 0.0, 350, 625
allxy = allos[["x", "y"]].values
occ = np.zeros((NY, NX), bool)
ix = np.clip((allxy[:, 0] // CELL).astype(int), 0, NX - 1)
iy = np.clip((allxy[:, 1] // CELL).astype(int), 0, NY - 1)
occ[iy, ix] = True
LANDR = ndimage.binary_dilation(occ, iterations=2)
LANDR = ndimage.binary_closing(LANDR, iterations=2)


def raster(xy):
    a = np.zeros((NY, NX))
    i = np.clip((xy[:, 0] // CELL).astype(int), 0, NX - 1)
    j = np.clip((xy[:, 1] // CELL).astype(int), 0, NY - 1)
    np.add.at(a, (j, i), 1)
    return a, i, j


def contour_lines(p, mask, level=0.5):
    """Contours of p at level, inside mask. Returns list of (N,2) arrays in BNG metres."""
    arr = np.where(mask, p, np.nan)
    arr = np.nan_to_num(arr, nan=-1)
    cs = measure.find_contours(arr, level, mask=mask)
    out = []
    for c in cs:
        xy = np.column_stack([(c[:, 1] + 0.5) * CELL + X0, (c[:, 0] + 0.5) * CELL + Y0])
        if len(xy) < 3:
            continue
        ls = LineString(xy).simplify(400)
        if ls.length >= 30000:
            out.append(np.array(ls.coords))
    return out


def densify(lines, step=250.0):
    pts, seg = [], []
    for k, L in enumerate(lines):
        ls = LineString(L)
        n = max(2, int(ls.length // step))
        for t in np.linspace(0, ls.length, n):
            p = ls.interpolate(t)
            pts.append((p.x, p.y))
            seg.append((k, t))
    return np.array(pts), np.array(seg)


def logistic_width(d, y, boot=0):
    if len(d) < 30 or y.sum() < 10 or (1 - y).sum() < 10:
        return None
    X = sm.add_constant(d)
    try:
        b = sm.Logit(y, X).fit(disp=0).params[1]
    except Exception:
        return None
    if b <= 0:
        return None
    w = 2 * math.log(4) / b
    res = dict(width_km=round(w, 1))
    if boot:
        ws = []
        n = len(d)
        for _ in range(boot):
            i = RNG.integers(0, n, n)
            try:
                bb = sm.Logit(y[i], X[i]).fit(disp=0).params[1]
                if bb > 0:
                    ws.append(2 * math.log(4) / bb)
            except Exception:
                pass
        if ws:
            res["ci"] = [round(float(np.percentile(ws, 2.5)), 1), round(float(np.percentile(ws, 97.5)), 1)]
    return res


def fit_pair(fam_a, a_words, fam_b, b_words, key, label_a, label_b):
    A = f[(f.family == fam_a) & f.word.isin(a_words)][["x", "y"]].values.astype(float)
    B = f[(f.family == fam_b) & f.word.isin(b_words)][["x", "y"]].values.astype(float)
    ra, ia, ja = raster(A)
    rb, ib, jb = raster(B)
    best = None
    for sig_km in (6, 8, 10, 14, 20):
        s = sig_km * 1000 / CELL
        ka, kb = ndimage.gaussian_filter(ra, s, mode="constant"), ndimage.gaussian_filter(rb, s, mode="constant")
        imp = np.zeros((41, 41))
        imp[20, 20] = 1
        w0 = ndimage.gaussian_filter(imp, s, mode="constant")[20, 20]
        pa = (ka[ja, ia] - w0) / np.maximum(ka[ja, ia] + kb[ja, ia] - w0, 1e-12)
        pb = (kb[jb, ib] - w0) / np.maximum(ka[jb, ib] + kb[jb, ib] - w0, 1e-12)
        ll = np.log(np.clip(pa, 1e-4, 1)).sum() + np.log(np.clip(pb, 1e-4, 1)).sum()
        if best is None or ll > best[0]:
            best = (ll, sig_km, ka, kb, s)
    _, sig_km, ka, kb, s = best
    tot = ka + kb
    neff = tot * 4 * math.pi * s * s
    p = ka / np.maximum(tot, 1e-12)
    mask = (neff >= 5) & LANDR
    lines = contour_lines(p, mask)
    res = dict(key=key, a=label_a, b=label_b, n_a=int(len(A)), n_b=int(len(B)), bandwidth_km=sig_km,
               line_km=round(sum(LineString(L).length for L in lines) / 1000), n_pieces=len(lines))
    if not lines:
        res["width_km"] = None
        return res, [], p, mask
    dens, seg = densify(lines)
    tree = cKDTree(dens)
    P = np.vstack([A, B])
    y = np.r_[np.ones(len(A)), np.zeros(len(B))]
    dist, nn = tree.query(P)
    ii = np.clip((P[:, 0] // CELL).astype(int), 0, NX - 1)
    jj = np.clip((P[:, 1] // CELL).astype(int), 0, NY - 1)
    pp = p[jj, ii]
    ok = mask[jj, ii] & (dist <= 60000)
    sgn = np.where(pp >= 0.5, 1.0, -1.0)
    d = dist / 1000 * sgn
    glob_ = logistic_width(d[ok], y[ok], boot=300)
    res.update(glob_ or {"width_km": None})
    res["n_near"] = int(ok.sum())
    # purity: share of each word's points on its own side (within the masked area)
    inA = pp >= 0.5
    okm = mask[jj, ii]
    res["a_on_a_side"] = round(float((inA & okm)[:len(A)].sum() / max(okm[:len(A)].sum(), 1)), 3)
    res["b_on_b_side"] = round(float((~inA & okm)[len(A):].sum() / max(okm[len(A):].sum(), 1)), 3)
    # local widths along 60 km stretches
    pieces = []
    for k, L in enumerate(lines):
        ls = LineString(L)
        nchunk = max(1, int(round(ls.length / 60000)))
        edges = np.linspace(0, ls.length, nchunk + 1)
        for c in range(nchunk):
            sel = ok & (seg[nn, 0] == k) & (seg[nn, 1] >= edges[c]) & (seg[nn, 1] <= edges[c + 1])
            lw = logistic_width(d[sel], y[sel])
            sub = [ls.interpolate(t) for t in np.linspace(edges[c], edges[c + 1], max(3, int((edges[c + 1] - edges[c]) // 1500)))]
            lo_, la_ = TO_LL.transform([q.x for q in sub], [q.y for q in sub])
            pieces.append(dict(coords=[[round(a, 4), round(b, 4)] for a, b in zip(lo_, la_)],
                               width_km=(lw or {}).get("width_km"), n=int(sel.sum())))
    res["local_widths"] = [pc["width_km"] for pc in pieces]
    lw_ok = [w for w in res["local_widths"] if w is not None]
    if lw_ok:
        res["local_min_km"], res["local_max_km"] = min(lw_ok), max(lw_ok)
        # where is the sharpest stretch?
        k = int(np.argmin([w if w is not None else 1e9 for w in res["local_widths"]]))
        mid = pieces[k]["coords"][len(pieces[k]["coords"]) // 2]
        res["sharpest_at"] = mid
    res["lines_bng"] = [L.tolist() for L in lines]
    return res, pieces, p, mask


PAIRS = [
    ("beck_brook", "stream", ["beck"], "stream", ["brook"], "beck", "brook"),
    ("burn_beck", "stream", ["burn"], "stream", ["beck"], "burn", "beck"),
    ("allt_burn", "stream", ["allt"], "stream", ["burn"], "allt", "burn"),
    ("nant_brook", "stream", ["nant", "afon"], "stream", ["brook"], "nant or afon", "brook"),
    ("dale_clough", "valley", ["dale"], "valley", ["clough"], "dale", "clough"),
    ("combe_bottom", "valley", ["combe"], "valley", ["bottom"], "combe", "bottom"),
    ("cwm_dingle", "valley", ["cwm"], "valley", ["dingle"], "cwm", "dingle"),
    ("fell_law", "hill", ["fell"], "hill", ["law"], "fell", "law"),
    ("tor_down", "hill", ["tor"], "hill", ["down"], "tor", "down"),
]
BOUND = {}
GEO = []
pmaps = {}
for key, fa, aw, fb, bw, la, lb in PAIRS:
    res, pieces, p, mask = fit_pair(fa, aw, fb, bw, key, la, lb)
    BOUND[key] = res
    pmaps[key] = (p, mask)
    for pc in pieces:
        GEO.append(dict(type="Feature", properties=dict(kind="word_boundary", pair=key, a=la, b=lb,
                                                         width_km=pc["width_km"], n_points=pc["n"]),
                        geometry=dict(type="LineString", coordinates=pc["coords"])))
    print(key, {k: v for k, v in res.items() if k not in ("lines_bng", "local_widths")})

# ---------------------------------------------------------------- national borders from the country column
tree_all = cKDTree(allxy)
gx, gy = np.meshgrid((np.arange(NX) + 0.5) * CELL, (np.arange(NY) + 0.5) * CELL)
_, nidx = tree_all.query(np.column_stack([gx.ravel(), gy.ravel()]))
cty = np.asarray(allos.country.values, dtype=object)[nidx].reshape(NY, NX)
isE = (cty == "England").astype(float)
borders = {}
for name, other, ylim in (("england_wales", "Wales", (150000, 420000)), ("england_scotland", "Scotland", (480000, 700000))):
    m = LANDR & ((cty == "England") | (cty == other)) & (gy > ylim[0]) & (gy < ylim[1])
    m = ndimage.binary_erosion(m, iterations=1)
    sm_ = ndimage.gaussian_filter(isE, 1.0)
    cs = measure.find_contours(np.where(m, sm_, -1), 0.5, mask=m)
    best = max(cs, key=len)
    xy = np.column_stack([(best[:, 1] + 0.5) * CELL, (best[:, 0] + 0.5) * CELL])
    ls = LineString(xy).simplify(500)
    borders[name] = np.array(ls.coords)
    lo_, la_ = TO_LL.transform(ls.xy[0], ls.xy[1])
    GEO.append(dict(type="Feature", properties=dict(kind="national_border", name=name,
                                                     note="Derived from the country field of OS Open Names; approximate"),
                    geometry=dict(type="LineString", coordinates=[[round(a, 4), round(b, 4)] for a, b in zip(lo_, la_)])))
R["borders_km"] = {k: round(LineString(v).length / 1000) for k, v in borders.items()}

# ---------------------------------------------------------------- Danelaw line (approximate)
DANELAW = [  # lon, lat. Up the Thames, up the Lea to its source, straight to Bedford, up the Ouse to
    # Watling Street at Stony Stratford, along Watling Street to Wall, then a straight line to Chester.
    (0.80, 51.51), (0.45, 51.47), (0.25, 51.46), (0.07, 51.50), (0.005, 51.508),
    (-0.04, 51.565), (-0.02, 51.67), (-0.03, 51.81), (-0.08, 51.80), (-0.21, 51.80), (-0.36, 51.82),
    (-0.42, 51.88), (-0.465, 51.905),
    (-0.467, 52.136),
    (-0.53, 52.15), (-0.625, 52.165), (-0.70, 52.155), (-0.72, 52.087), (-0.853, 52.058),
    (-0.99, 52.134), (-1.08, 52.23), (-1.17, 52.335), (-1.30, 52.497), (-1.42, 52.55), (-1.55, 52.58),
    (-1.70, 52.61), (-1.855, 52.656),
    (-2.89, 53.19),
]
dx_, dy_ = TO_BNG.transform([p[0] for p in DANELAW], [p[1] for p in DANELAW])
DLINE = LineString(list(zip(dx_, dy_)))
poly_ll = DANELAW + [(-3.10, 53.35), (-3.6, 54.2), (-3.6, 55.1), (-2.0, 55.9), (2.2, 55.9), (2.2, 51.3), (0.80, 51.30)]
px_, py_ = TO_BNG.transform([p[0] for p in poly_ll], [p[1] for p in poly_ll])
DPOLY = Polygon(list(zip(px_, py_)))
GEO.append(dict(type="Feature", properties=dict(kind="danelaw", note=(
    "Approximate line of the treaty of Alfred and Guthrum: up the Thames, up the Lea to its source, "
    "straight to Bedford, up the Ouse to Watling Street, along Watling Street to Wall near Lichfield, "
    "then a straight line to Chester. Hand-placed coordinates; for orientation only.")),
    geometry=dict(type="LineString", coordinates=[list(p) for p in DANELAW])))
R["danelaw_coords"] = DANELAW

from shapely import contains_xy  # noqa: E402
eng = f[f.country == "England"].copy()
eng["dside"] = contains_xy(DPOLY, eng.x.values, eng.y.values)
allE = allos[allos.country == "England"]
base = float(contains_xy(DPOLY, allE.x.values, allE.y.values).mean())
dside = []
for (fam, w), g in eng[eng.word != ""].groupby(["family", "word"]):
    if len(g) >= 25:
        dside.append(dict(family=fam, word=w, n=int(len(g)), share=round(float(g.dside.mean()), 3)))
dside.sort(key=lambda r: -r["share"])
R["danelaw_side"] = dict(baseline_all_features=round(base, 3), words=dside,
                         norse_settlements=round(float(eng[eng.norse].dside.mean()), 3),
                         n_norse_settlements_england=int(eng.norse.sum()))

# A fairer test: only the part of England the treaty line actually crosses (south of 53.2 N, the
# latitude of Chester). North of that, everything is trivially "north and east of the line".
LATCUT = 53.2
engS = eng[eng.lat < LATCUT]
allEs = allE.copy()
allEs_lat = TO_LL.transform(allEs.x.values, allEs.y.values)[1]
allEs = allEs[allEs_lat < LATCUT]
baseS = float(contains_xy(DPOLY, allEs.x.values, allEs.y.values).mean())
dsS = []
for (fam, w), g in engS[engS.word != ""].groupby(["family", "word"]):
    if len(g) >= 25:
        dsS.append(dict(family=fam, word=w, n=int(len(g)), share=round(float(g.dside.mean()), 3)))
dsS.sort(key=lambda r: -r["share"])
R["danelaw_side_south"] = dict(lat_cut=LATCUT, baseline_all_features=round(baseS, 3), words=dsS,
                               norse_settlements=round(float(engS[engS.norse].dside.mean()), 3),
                               n_norse_settlements=int(engS.norse.sum()),
                               all_settlements=round(float(engS[engS.family == "settlement"].dside.mean()), 3))
# profile across the line: signed distance (positive = north and east), England south of 53.2 N
dl = np.array([DLINE.distance(Point(a, b)) for a, b in zip(engS.x.values, engS.y.values)]) / 1000
engS = engS.assign(sd=np.where(engS.dside, dl, -dl))
prof = []
for lo_b in range(-120, 120, 20):
    g = engS[(engS.sd >= lo_b) & (engS.sd < lo_b + 20)]
    se = g[g.family == "settlement"]
    stv = g[(g.family == "stream") & g.word.isin(["beck", "brook"])]
    prof.append(dict(lo=lo_b, hi=lo_b + 20, n_settle=int(len(se)), norse=round(float(se.norse.mean()), 3) if len(se) else None,
                     n_norse=int(se.norse.sum()), n_bb=int(len(stv)),
                     beck=round(float((stv.word == "beck").mean()), 3) if len(stv) >= 10 else None))
R["danelaw_profile"] = prof

# distance between word boundaries and the Danelaw line / national borders


def line_dist_stats(lines_bng, target, clip_poly=None, within=None):
    if not lines_bng:
        return None
    pts, _ = densify([np.array(L) for L in lines_bng], step=1000)
    if clip_poly is not None:
        pts = pts[contains_xy(clip_poly, pts[:, 0], pts[:, 1])]
    if not len(pts):
        return None
    tl = LineString(target)
    d = np.array([tl.distance(Point(p)) for p in pts]) / 1000
    out = dict(median_km=round(float(np.median(d)), 1), p25_km=round(float(np.percentile(d, 25)), 1),
               p75_km=round(float(np.percentile(d, 75)), 1), share_within_20km=round(float((d <= 20).mean()), 3),
               line_km=int(len(pts)))
    return out


# England-only polygon from the raster, used to clip word boundaries before comparing
eng_mask = (cty == "England") & LANDR
R["compare"] = {}
for key in BOUND:
    lines = BOUND[key].get("lines_bng") or []
    if not lines:
        continue
    pts, _ = densify([np.array(L) for L in lines], step=1000)
    ii = np.clip((pts[:, 0] // CELL).astype(int), 0, NX - 1)
    jj = np.clip((pts[:, 1] // CELL).astype(int), 0, NY - 1)
    c = {}
    for tname, tline in (("danelaw", np.array(DLINE.coords)), ("england_wales", borders["england_wales"]),
                         ("england_scotland", borders["england_scotland"])):
        d = np.array([LineString(tline).distance(Point(p)) for p in pts]) / 1000
        c[tname] = dict(median_km=round(float(np.median(d)), 1), share_within_20km=round(float((d <= 20).mean()), 3),
                        min_km=round(float(d.min()), 1))
    c["share_in_england"] = round(float(eng_mask[jj, ii].mean()), 3)
    c["share_on_danelaw_side"] = round(float(contains_xy(DPOLY, pts[:, 0], pts[:, 1]).mean()), 3)
    R["compare"][key] = c

# where does each line run? latitude and longitude range
R["line_extent"] = {}
for key in BOUND:
    bb = BOUND[key].get("lines_bng") or []
    if bb:
        pts, _ = densify([np.array(L) for L in bb], step=1000)
        lo_, la_ = TO_LL.transform(pts[:, 0], pts[:, 1])
        R["line_extent"][key] = dict(lat_median=round(float(np.median(la_)), 2), lat_min=round(float(np.min(la_)), 2),
                                     lat_max=round(float(np.max(la_)), 2), lon_min=round(float(np.min(lo_)), 2),
                                     lon_max=round(float(np.max(lo_)), 2))

# which counties does each line pass through? (nearest OS feature to each km of line)
tree_c = cKDTree(f[["x", "y"]].values)
R["line_counties"] = {}
for key in BOUND:
    bb = BOUND[key].get("lines_bng") or []
    if bb:
        pts, _ = densify([np.array(L) for L in bb], step=1000)
        _, ni = tree_c.query(pts)
        vc = f.county.values[ni]
        u, c = np.unique(vc, return_counts=True)
        o = np.argsort(-c)
        R["line_counties"][key] = [[str(u[i]), int(c[i])] for i in o[:6]]
R["line_pieces"] = {}
for key in BOUND:
    out_ = []
    for L in BOUND[key].get("lines_bng") or []:
        pts, _ = densify([np.array(L)], step=1000)
        _, ni = tree_c.query(pts)
        u, c = np.unique(f.county.values[ni], return_counts=True)
        o = np.argsort(-c)
        out_.append(dict(km=int(round(LineString(L).length / 1000)), counties=[[str(u[i]), int(c[i])] for i in o[:3]]))
    R["line_pieces"][key] = out_
R["n_landscape_classified"] = int(sum(R["n_matched"][k] for k in ("stream", "valley", "hill", "fall")))
R["n_landscape"] = int(sum(R["n_features"][k] for k in ("stream", "valley", "hill", "fall")))

# ---------------------------------------------------------------- hex-level correlations with Norse names
hexstat = pd.DataFrame(index=land.hid)
hexstat["country"] = land.set_index("hid").country
hexstat["cx"], hexstat["cy"] = land.set_index("hid").cx, land.set_index("hid").cy
hexstat["n_settle"] = norse_h.n
hexstat["norse_share"] = norse_h.k / norse_h.n
for fam in ["stream", "valley", "hill"]:
    hexstat[f"n_{fam}"] = fam_tot[fam] if fam in fam_tot else 0
piv = wc[wc.word != "norse_any"].pivot_table(index="hid", columns=["family", "word"], values="n", fill_value=0)


def block_boot_rho(xv, yv, bx, by, B=500):
    blocks = (bx // 100000).astype(int) * 1000 + (by // 100000).astype(int)
    ub = np.unique(blocks)
    idx = {b: np.where(blocks == b)[0] for b in ub}
    rs = []
    for _ in range(B):
        pick = RNG.choice(ub, len(ub))
        ii = np.concatenate([idx[b] for b in pick])
        if len(ii) > 10:
            rs.append(spearmanr(xv[ii], yv[ii]).statistic)
    return [round(float(np.nanpercentile(rs, 2.5)), 2), round(float(np.nanpercentile(rs, 97.5)), 2)]


CORR_WORDS = [("stream", "beck"), ("stream", "gill"), ("hill", "fell"), ("valley", "dale"), ("stream", "brook"),
              ("hill", "down"), ("valley", "combe"), ("valley", "bottom"), ("stream", "burn")]
corr = []
for region in ("England", "GB"):
    H = hexstat if region == "GB" else hexstat[hexstat.country == "England"]
    for fam, w in CORR_WORDS:
        n_f = H[f"n_{fam}"]
        sel = (H.n_settle >= 5) & (n_f >= 5)
        Hs = H[sel]
        share = piv.reindex(Hs.index).get((fam, w), pd.Series(0, index=Hs.index)).fillna(0) / Hs[f"n_{fam}"]
        r = spearmanr(Hs.norse_share.values, share.values).statistic
        ci = block_boot_rho(Hs.norse_share.values, share.values, Hs.cx.values, Hs.cy.values)
        corr.append(dict(region=region, family=fam, word=w, n_hex=int(len(Hs)), rho=round(float(r), 2), ci=ci))
R["norse_corr"] = corr
# beck share of beck+brook against Norse share (England), and points for a scatter
H = hexstat[hexstat.country == "England"].copy()
bk = piv.get(("stream", "beck"), pd.Series(0, index=piv.index)).reindex(H.index).fillna(0)
br = piv.get(("stream", "brook"), pd.Series(0, index=piv.index)).reindex(H.index).fillna(0)
H["bb"] = bk + br
H["beckshare"] = bk / H.bb
Hs = H[(H.bb >= 3) & (H.n_settle >= 5)]
R["beck_vs_norse"] = dict(n_hex=int(len(Hs)), rho=round(float(spearmanr(Hs.norse_share, Hs.beckshare).statistic), 2),
                          ci=block_boot_rho(Hs.norse_share.values, Hs.beckshare.values, Hs.cx.values, Hs.cy.values))
# split by Norse share bands
bands = [(0, 0.0001), (0.0001, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 1.01)]
R["beck_by_norse_band"] = []
for lo_b, hi_b in bands:
    g = Hs[(Hs.norse_share >= lo_b) & (Hs.norse_share < hi_b)]
    R["beck_by_norse_band"].append(dict(lo=lo_b, hi=hi_b, n_hex=int(len(g)),
                                        beck=int(bk.reindex(g.index).sum()), brook=int(br.reindex(g.index).sum()),
                                        beck_share=round(float(bk.reindex(g.index).sum() / max(g.bb.sum(), 1)), 3)))
scatter = [[round(float(a), 3), round(float(b), 3), int(c)] for a, b, c in zip(Hs.norse_share, Hs.beckshare, Hs.bb)]
# Norse share on each side of the beck/brook line, England
p_bb, m_bb = pmaps["beck_brook"]
E_set = f[(f.family == "settlement") & (f.country == "England")]
ii = np.clip((E_set.x.values // CELL).astype(int), 0, NX - 1)
jj = np.clip((E_set.y.values // CELL).astype(int), 0, NY - 1)
side = p_bb[jj, ii] >= 0.5
okm = m_bb[jj, ii]
R["norse_by_beck_side"] = dict(beck_side=round(float(E_set.norse.values[okm & side].mean()), 3),
                               brook_side=round(float(E_set.norse.values[okm & ~side].mean()), 3),
                               n_beck_side=int((okm & side).sum()), n_brook_side=int((okm & ~side).sum()))

# ---------------------------------------------------------------- transects (share by northing band)
TRANS = {
    "stream": ["beck", "brook", "burn"],
    "valley": ["dale", "clough", "cleugh", "combe", "bottom", "dean"],
    "hill": ["fell", "down", "tor", "law", "pike", "edge"],
}
R["transects"] = {}
for fam, ws in TRANS.items():
    g = f[(f.family == fam) & f.word.isin(ws) & (f.country != "Wales") & (f.y < 720000)]
    band = (g.y // 20000).astype(int)
    rows = []
    for b in range(0, 36):
        gg = g[band == b]
        if len(gg) < 8:
            rows.append(None)
            continue
        vc = gg.word.value_counts()
        rows.append([round(float(vc.get(w, 0) / len(gg)), 3) for w in ws] + [int(len(gg))])
    R["transects"][fam] = dict(words=ws, band_km=20, rows=rows)
# latitude of each band centre
R["transect_band_lat"] = [round(float(TO_LL.transform(400000, (b + .5) * 20000)[1]), 2) for b in range(36)]

# ---------------------------------------------------------------- counties
cnt = []
for (cty_, fam), g in f[(f.word != "") & (f.family.isin(["stream", "valley", "hill"]))].groupby(["county", "family"]):
    if len(g) < 10:
        continue
    vc = g.word.value_counts()
    gb = f[(f.family == fam) & (f.word != "")].word.value_counts(normalize=True)
    lq = ((vc / len(g)) / gb).dropna()
    lq = lq[vc.reindex(lq.index) >= 5]
    cnt.append(dict(county=cty_, family=fam, n=int(len(g)), top=vc.index[0], top_share=round(float(vc.iloc[0] / len(g)), 2),
                    distinct=(lq.idxmax() if len(lq) else None), distinct_lq=(round(float(lq.max()), 1) if len(lq) else None)))
ctab = pd.DataFrame(cnt)
cc = f[f.word != ""].groupby("county").country.agg(lambda s: s.value_counts().index[0])
county_rows = []
for c_, g in ctab.groupby("county"):
    row = dict(county=c_, country=cc.get(c_, ""))
    for _, r in g.iterrows():
        row[r.family] = [r.top, r.top_share, r.n, r.distinct, r.distinct_lq]
    county_rows.append(row)
R["counties"] = county_rows
# headline: how many counties have each top word per family
R["county_top_counts"] = {fam: ctab[ctab.family == fam].top.value_counts().to_dict() for fam in ["stream", "valley", "hill"]}

# ---------------------------------------------------------------- rare words
rare = []
for fam in ["stream", "valley", "hill", "fall"]:
    for w, c in counts[fam].items():
        if c["n"] <= 60:
            g = f[(f.family == fam) & (f.word == w)]
            vc = g.county.value_counts()
            mx, my = np.median(g.x), np.median(g.y)
            dist = np.hypot(g.x - mx, g.y - my) / 1000
            rare.append(dict(family=fam, word=w, n=c["n"], top_county=vc.index[0], top_n=int(vc.iloc[0]),
                             top_share=round(float(vc.iloc[0] / len(g)), 2),
                             radius80_km=round(float(np.percentile(dist, 80))),
                             examples=g.name.drop_duplicates().head(4).tolist()))
rare.sort(key=lambda r: r["n"])
R["rare"] = rare

# ---------------------------------------------------------------- hidden words in settlement names
hid = pd.read_csv(os.path.join(ROOT, "work", "hidden.csv"), keep_default_na=False)
R["hidden"] = []
for w, g in hid.groupby("word"):
    R["hidden"].append(dict(word=w, n=int(len(g)), lat_med=round(float(g.lat.median()), 2),
                            lat_p25=round(float(g.lat.quantile(.25)), 2), lat_p75=round(float(g.lat.quantile(.75)), 2),
                            england=int((g.country == "England").sum()), scotland=int((g.country == "Scotland").sum()),
                            wales=int((g.country == "Wales").sum()), examples=g.name.drop_duplicates().head(5).tolist()))
R["hidden"].sort(key=lambda r: -r["lat_med"])

# ---------------------------------------------------------------- most Norse / most English places
NORSE_W = {("stream", "beck"), ("stream", "gill"), ("valley", "gill"), ("hill", "fell"), ("hill", "how"),
           ("fall", "force"), ("fall", "foss"), ("settlement", "thwaite"), ("settlement", "toft"),
           ("settlement", "thorpe"), ("settlement", "by"), ("settlement", "holme"), ("settlement", "kirk")}
ENG_W = {("stream", "brook"), ("stream", "bourne"), ("stream", "burn"), ("stream", "fleet"), ("stream", "lode"),
         ("hill", "down"), ("hill", "edge"), ("valley", "dean"), ("valley", "bottom"), ("valley", "slade"),
         ("valley", "hope"), ("valley", "clough"), ("settlement", "ton"), ("settlement", "ham"),
         ("settlement", "worth"), ("settlement", "ley")}
fw = f[f.word != ""]
isN = np.array([(a, b) in NORSE_W for a, b in zip(fw.family, fw.word)])
isEn = np.array([(a, b) in ENG_W for a, b in zip(fw.family, fw.word)])
tN, tE = cKDTree(fw[isN][["x", "y"]].values), cKDTree(fw[isEn][["x", "y"]].values)
pl = f[(f.family == "settlement") & f.local_type.isin(["Town", "City", "Village"]) & (f.country == "England")].copy()
P = pl[["x", "y"]].values
pl["nN"] = [len(v) for v in tN.query_ball_point(P, 10000)]
pl["nE"] = [len(v) for v in tE.query_ball_point(P, 10000)]
pl = pl[(pl.nN + pl.nE) >= 25]
pl["idx"] = pl.nN / (pl.nN + pl.nE)
top = pl.sort_values(["idx", "nN"], ascending=[False, False]).drop_duplicates("name").head(10)
bot = pl.sort_values(["idx", "nE"], ascending=[True, False]).drop_duplicates("name").head(10)
R["norse_index"] = dict(radius_km=10, min_words=25, n_places=int(len(pl)),
                        norse_words=sorted(f"{a}:{b}" for a, b in NORSE_W), english_words=sorted(f"{a}:{b}" for a, b in ENG_W),
                        most_norse=[dict(name=r.name, county=r.county, type=r.local_type, norse=int(r.nN), english=int(r.nE),
                                         index=round(float(r.idx), 3), lat=round(r.lat, 3), lon=round(r.lon, 3)) for r in top.itertuples()],
                        most_english=[dict(name=r.name, county=r.county, type=r.local_type, norse=int(r.nN), english=int(r.nE),
                                           index=round(float(r.idx), 3), lat=round(r.lat, 3), lon=round(r.lon, 3)) for r in bot.itertuples()],
                        n_zero_norse=int((pl.nN == 0).sum()))
# what makes up the top place on each list?
fwN, fwE = fw[isN].reset_index(drop=True), fw[isEn].reset_index(drop=True)
for lst, frame in (("most_norse", top), ("most_english", bot)):
    r0 = frame.iloc[0]
    ids = (tN if lst == "most_norse" else tE).query_ball_point([r0.x, r0.y], 10000)
    sub = (fwN if lst == "most_norse" else fwE).iloc[ids]
    R.setdefault("norse_index_detail", {})[lst] = dict(name=r0["name"], words=sub.word.value_counts().to_dict())
bbl = BOUND["beck_brook"].get("lines_bng")
if bbl:
    r0 = bot.iloc[0]
    R["norse_index_detail"]["most_english_km_to_beck_brook"] = round(min(LineString(L).distance(Point(r0.x, r0.y)) for L in bbl) / 1000, 1)
towns = pl[pl.local_type.isin(["Town", "City"])].sort_values("idx", ascending=False)
R["norse_index"]["top_towns"] = [dict(name=r.name, county=r.county, index=round(float(r.idx), 3), norse=int(r.nN), english=int(r.nE))
                                 for r in towns.drop_duplicates("name").head(8).itertuples()]

# ---------------------------------------------------------------- audit (verdicts recorded in audit.py)
import audit  # noqa: E402
samp = audit.sample()
R["audit"] = {}
for fam, rows in samp.items():
    bad = [r[0] for r in rows if r[0] in audit.AUDIT_FALSE.get(fam, [])]
    R["audit"][fam] = dict(n=len(rows), false=len(bad), false_names=bad)
st_ = audit.strat_sample()
R["audit_strat"] = dict(seed=audit.STRAT_SEED, n=sum(len(v) for v in st_.values()),
                        false=sum(len([r for r in v if r[0] in audit.STRAT_FALSE.get(k, [])]) for k, v in st_.items()),
                        uncertain=sum(len([r for r in v if r[0] in audit.STRAT_UNCERTAIN.get(k, [])]) for k, v in st_.items()))
R["audit_total"] = dict(n=sum(v["n"] for v in R["audit"].values()), false=sum(v["false"] for v in R["audit"].values()),
                        seed=audit.SEED)

# ---------------------------------------------------------------- write
for k in BOUND:
    BOUND[k].pop("lines_bng", None)
R["boundaries"] = BOUND
json.dump(dict(type="FeatureCollection", name="dale-down-fell-beck boundaries", features=GEO),
          open(os.path.join(ROOT, "data", "boundaries.geojson"), "w"), separators=(",", ":"))
json.dump(R, open(os.path.join(ROOT, "data", "results.json"), "w"), indent=1, ensure_ascii=False, default=float)

# ---------------------------------------------------------------- compact site data
counties = sorted(f.county.unique())
CI = {c: i for i, c in enumerate(counties)}
LT = sorted(f.local_type.unique())
LTI = {c: i for i, c in enumerate(LT)}
pts = {}
names = []
for (fam, w), g in f[f.word != ""].groupby(["family", "word"]):
    arr = []
    for r in g.itertuples():
        arr += [int(round(r.lat * 1000)), int(round(r.lon * 1000)), len(names), CI[r.county], LTI[r.local_type]]
        names.append(r.name.replace("|", "/"))
    pts[f"{fam}:{w}"] = arr
hexw = {}
for (fam, w), g in wc.groupby(["family", "word"]):
    hexw[f"{fam}:{w}"] = [v for t in zip(g.hid, g.n) for v in (int(t[0]), int(t[1]))]
famtot = {fam: [int(fam_tot.loc[h, fam]) if (h in fam_tot.index and fam in fam_tot.columns) else 0 for h in land.hid] for fam in FAMS}
famtot["settlement"] = [int(norse_h.n.get(h, 0)) for h in land.hid]
site = dict(meta=META, counties=counties, lt=LT, names="|".join(names), pts=pts,
            hex=dict(poly=hex_poly, cx=[int(v / 1000) for v in land.cx], cy=[int(v / 1000) for v in land.cy],
                     country=[{"England": 0, "Wales": 1, "Scotland": 2}[c] for c in land.country], fam=famtot, w=hexw),
            scatter=scatter)
json.dump(site, open(os.path.join(ROOT, "work", "site_data.json"), "w"), separators=(",", ":"), ensure_ascii=False)
print("done")
