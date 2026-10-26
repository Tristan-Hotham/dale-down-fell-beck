"""Step 1. Collapse OS Open Rivers links to one point per named watercourse.

OS Open Rivers splits every river into short links between junction nodes. A watercourse that is
2 km long can be one link; the Thames is hundreds. Counting links would weight every word by how
fragmented its rivers are, so I count watercourses instead:

  * links with the same watercourse_name that share a start or end node are joined into one
    connected run (union-find on the node ids);
  * runs with the same name whose link midpoints come within 2 km of each other are also joined
    (a named river is sometimes broken by an unnamed link, a lake or a culvert);
  * each run becomes one point: the vertex of the run nearest its length-weighted centre, so the
    point always lies on the watercourse. Its total length is kept.

Output: work/streams.csv (name, alt_name, length_m, x, y, lon, lat, n_links).

Usage: python3 code/streams.py [path/to/oprvrs_gb.gpkg]
"""
import csv
import os
import sqlite3
import struct
import sys
from collections import defaultdict

import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GPKG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "..", "osrivers", "Data", "oprvrs_gb.gpkg")
os.makedirs(os.path.join(ROOT, "work"), exist_ok=True)

ENV_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def decode(blob):
    """GeoPackage binary -> (N,2) array of x,y. Handles 2D/3D LineString and MultiLineString WKB."""
    flags = blob[3]
    off = 8 + ENV_BYTES[(flags >> 1) & 7]
    wkb = blob[off:]

    def read(p):
        bo = "<" if wkb[p] == 1 else ">"
        typ = struct.unpack(bo + "I", wkb[p + 1:p + 5])[0]
        base, dim = typ % 1000, 3 if (typ // 1000 in (1, 2) or typ & 0x80000000) else 2
        base &= 0xFF
        p += 5
        if base == 2:
            n = struct.unpack(bo + "I", wkb[p:p + 4])[0]
            p += 4
            a = np.frombuffer(wkb[p:p + 8 * dim * n], dtype=bo + "f8").reshape(n, dim)[:, :2]
            return [a], p + 8 * dim * n
        if base == 5:
            n = struct.unpack(bo + "I", wkb[p:p + 4])[0]
            p += 4
            out = []
            for _ in range(n):
                a, p = read(p)
                out += a
            return out, p
        raise ValueError(f"geometry type {typ}")
    parts, _ = read(0)
    return np.vstack(parts)


def main():
    con = sqlite3.connect(GPKG)
    rows = con.execute("""select watercourse_name, watercourse_name_alternative, length, start_node, end_node,
                          geometry from watercourse_link where watercourse_name is not null""").fetchall()
    print(len(rows), "named links")
    by_name = defaultdict(list)
    for r in rows:
        by_name[r[0]].append(r)
    tr = Transformer.from_crs(27700, 4326, always_xy=True)
    out = []
    for name, links in by_name.items():
        parent = list(range(len(links)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(a, b):
            a, b = find(a), find(b)
            if a != b:
                parent[a] = b
        node_first = {}
        geoms = [decode(l[5]) for l in links]
        mids = np.array([g[len(g) // 2] for g in geoms])
        for i, l in enumerate(links):
            for nd in (l[3], l[4]):
                if nd in node_first:
                    union(i, node_first[nd])
                else:
                    node_first[nd] = i
        if len(links) > 1:
            tree = cKDTree(mids)
            for i, j in tree.query_pairs(2000):
                union(i, j)
        comps = defaultdict(list)
        for i in range(len(links)):
            comps[find(i)].append(i)
        for idx in comps.values():
            L = np.array([links[i][2] or 0 for i in idx])
            cen = (mids[idx] * L[:, None]).sum(0) / max(L.sum(), 1e-9)
            verts = np.vstack([geoms[i] for i in idx])
            v = verts[np.argmin(((verts - cen) ** 2).sum(1))]
            alts = sorted({links[i][1] for i in idx if links[i][1]})
            lon, lat = tr.transform(v[0], v[1])
            out.append([name, alts[0] if alts else "", round(float(L.sum())), int(v[0]), int(v[1]),
                        round(lon, 5), round(lat, 5), len(idx)])
    with open(os.path.join(ROOT, "work", "streams.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "alt_name", "length_m", "x", "y", "lon", "lat", "n_links"])
        w.writerows(out)
    print(len(out), "named watercourses from", len(by_name), "distinct names")


if __name__ == "__main__":
    main()
