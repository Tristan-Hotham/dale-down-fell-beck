"""Step 2. Apply the rules in words.py to OS Open Names and the collapsed OS Open Rivers watercourses.

Outputs
  data/landscape_words.csv  one row per matched feature (name, word, family, local_type, lat, lon, county, country)
  work/features.csv         every feature in each family, matched or not (denominators), with x, y
  work/hidden.csv           settlement names that end in a landscape word (Ashbourne, Holbeck)

Usage: python3 code/match.py [osnames_gb.tsv]
"""
import csv
import os
import sys

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import words  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "..", "osnames_gb.tsv")

LOCAL = {
    "valley": {"Valley", "Cirque Or Hollow"},
    "hill": {"Hill Or Mountain", "Hill Or Mountain Ranges", "Cliff Or Slope", "Other Landform", "Spot Height",
             "Other Landcover"},
    "fall": {"Waterfall"},
}
# Most named downs and fells in OS Open Names are "Other Landcover" (open hill grazing), not
# "Hill Or Mountain". Landcover features join the hill family only when they are named fell or down;
# all other landcover names (moors, commons, heaths) are left out, matched or not.
LANDCOVER_ONLY = {"fell", "down"}


def main():
    d = pd.read_csv(TSV, sep="\t", dtype=str, keep_default_na=False)
    for c in ("lat", "lon"):
        d[c] = d[c].astype(float)
    for c in ("x", "y"):
        d[c] = d[c].astype(int)
    d["cty"] = d["county"].where(d["county"] != "", d["district"])
    # Welsh councils are written "Cymraeg - English" (e.g. "Sir Fynwy - Monmouthshire"); keep the English part
    d["cty"] = d["cty"].map(lambda c: c.split(" - ")[-1].strip() if " - " in c else c)
    rows = []
    for fam, lts in LOCAL.items():
        s = d[d.local_type.isin(lts)]
        for r in s.itertuples():
            w = words.classify(r.name1, fam)
            via = "name1"
            if w is None and r.name2:
                w = words.classify(r.name2, fam)
                via = "name2" if w else ""
            if r.local_type == "Other Landcover" and w not in LANDCOVER_ONLY:
                continue
            rows.append([r.name1, w or "", fam, r.local_type, r.lat, r.lon, r.x, r.y, r.cty, r.country, via])
    pp = d[d.type == "populatedPlace"]
    hidden = []
    for r in pp.itertuples():
        w = words.settlement_word(r.name1, r.country, r.cty)
        rows.append([r.name1, w or "", "settlement", r.local_type, r.lat, r.lon, r.x, r.y, r.cty, r.country,
                     "norse" if words.is_norse_settlement(r.name1, r.country, r.cty) else ""])
        h = words.hidden_word(r.name1)
        if h:
            hidden.append([r.name1, h, r.local_type, r.lat, r.lon, r.x, r.y, r.cty, r.country])
    # streams: county and country from the nearest OS Names feature
    st = pd.read_csv(os.path.join(ROOT, "work", "streams.csv"), dtype={"alt_name": str}, keep_default_na=False)
    tree = cKDTree(d[["x", "y"]].values)
    _, idx = tree.query(st[["x", "y"]].values)
    near = d.iloc[idx]
    for r, cty, ctry in zip(st.itertuples(), near.cty.values, near.country.values):
        w = words.classify(r.name, "stream")
        via = "name1"
        if w is None and r.alt_name:
            w = words.classify(r.alt_name, "stream")
            via = "name2" if w else ""
        rows.append([r.name, w or "", "stream", "Watercourse", r.lat, r.lon, r.x, r.y, cty, ctry, via])
    f = pd.DataFrame(rows, columns=["name", "word", "family", "local_type", "lat", "lon", "x", "y", "county",
                                    "country", "via"])
    f.to_csv(os.path.join(ROOT, "work", "features.csv"), index=False)
    m = f[f.word != ""].copy()
    m["lat"] = m.lat.round(5)
    m["lon"] = m.lon.round(5)
    m[["name", "word", "family", "local_type", "lat", "lon", "county", "country"]].to_csv(
        os.path.join(ROOT, "data", "landscape_words.csv"), index=False, quoting=csv.QUOTE_MINIMAL)
    pd.DataFrame(hidden, columns=["name", "word", "local_type", "lat", "lon", "x", "y", "county", "country"]).to_csv(
        os.path.join(ROOT, "work", "hidden.csv"), index=False)
    print(f.groupby("family").agg(n=("name", "size"), matched=("word", lambda s: (s != "").sum())))
    for fam in ["stream", "valley", "hill", "fall", "settlement"]:
        print(fam, m[m.family == fam].word.value_counts().to_dict())
    print("via name2:", (f.via == "name2").sum(), "hidden:", len(hidden))


if __name__ == "__main__":
    main()
