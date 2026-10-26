"""Step 4. Build index.html from code/page_template.html, data/results.json, data/boundaries.geojson
and work/site_data.json. Every number in the text is filled from results.json here.

Usage: python3 code/build_site.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "results.json"), encoding="utf-8"))
G = json.load(open(os.path.join(ROOT, "data", "boundaries.geojson"), encoding="utf-8"))
S = json.load(open(os.path.join(ROOT, "work", "site_data.json"), encoding="utf-8"))
T = open(os.path.join(ROOT, "code", "page_template.html"), encoding="utf-8").read()


def n(v):
    return f"{int(round(v)):,}"


def pct(v, d=0):
    return f"{v * 100:.{d}f}%"


def km(v):
    return f"{v:.0f}" if v >= 20 else f"{v:.1f}".rstrip("0").rstrip(".")


B = R["boundaries"]
C = R["compare"]
cnt = R["counts"]
south = {w["word"]: w for w in R["danelaw_side_south"]["words"] if w["family"] in ("settlement", "stream")}
corrE = {r["word"]: r for r in R["norse_corr"] if r["region"] == "England"}
prof = {p["lo"]: p for p in R["danelaw_profile"]}
bands = R["beck_by_norse_band"]
ni = R["norse_index"]
nid = R["norse_index_detail"]
eau = next(r for r in R["rare"] if r["word"] == "eau")
fam_n = R["n_features"]

# brooks and becks in the Danelaw part of England south of 53.2N
dn_brook = round(south["brook"]["n"] * south["brook"]["share"])
dn_beck = round(south["beck"]["n"] * south["beck"]["share"])

V = dict(
    n_classified=n(R["n_landscape_classified"]), n_landscape=n(R["n_landscape"]),
    pct_classified=pct(R["n_landscape_classified"] / R["n_landscape"]),
    n_settle=n(fam_n["settlement"]), n_osnames=n(R["n_osnames"]),
    n_valleyfam=n(fam_n["valley"]), n_hillfam=n(fam_n["hill"]), n_fallfam=n(fam_n["fall"]),
    n_streams=n(R["streams"]["n_watercourses"]), n_links=n(R["streams"]["n_links"]),
    n_burn=n(cnt["stream"]["burn"]["n"]), n_allt=n(cnt["stream"]["allt"]["n"]), n_brook=n(cnt["stream"]["brook"]["n"]),
    n_beck=n(cnt["stream"]["beck"]["n"]), n_hill=n(cnt["hill"]["hill"]["n"]), n_down=n(cnt["hill"]["down"]["n"]),
    n_fell=n(cnt["hill"]["fell"]["n"]), n_tor=n(cnt["hill"]["tor"]["n"]), n_law=n(cnt["hill"]["law"]["n"]),
    n_combe=n(cnt["valley"]["combe"]["n"]), n_bottom=n(cnt["valley"]["bottom"]["n"]),
    n_via2=n(R["n_via_name2"]),
    hex_w=str(R["hex"]["width_km"]), hex_n=n(R["hex"]["n_hex"]),
    band_km=str(R["transects"]["stream"]["band_km"]),
    bb_w=km(B["beck_brook"]["width_km"]), bb_lat=f'{R["line_extent"]["beck_brook"]["lat_median"]:.1f}',
    bb_a_on=pct(B["beck_brook"]["a_on_a_side"]), bb_b_on=pct(B["beck_brook"]["b_on_b_side"]),
    bub_w=km(B["burn_beck"]["width_km"]), bub_in_eng=pct(C["burn_beck"]["share_in_england"]),
    bub_border=km(C["burn_beck"]["england_scotland"]["median_km"]),
    ab_w=km(B["allt_burn"]["width_km"]), ab_min=km(B["allt_burn"]["local_min_km"]), ab_max=km(B["allt_burn"]["local_max_km"]),
    ab_km=n(B["allt_burn"]["line_km"]), ab_pieces=str(B["allt_burn"]["n_pieces"]),
    nb_w=km(B["nant_brook"]["width_km"]), nb_border=km(C["nant_brook"]["england_wales"]["median_km"]),
    nb_border20=pct(C["nant_brook"]["england_wales"]["share_within_20km"]),
    dc_w=km(B["dale_clough"]["width_km"]), cb_w=km(B["combe_bottom"]["width_km"]),
    cb_a_on=pct(B["combe_bottom"]["a_on_a_side"]), cd_w=km(B["cwm_dingle"]["width_km"]),
    cd_border=km(C["cwm_dingle"]["england_wales"]["median_km"]),
    fl_w=km(B["fell_law"]["width_km"]), fl_border=km(C["fell_law"]["england_scotland"]["median_km"]),
    td_w=km(B["tor_down"]["width_km"]),
    nbs_beck=pct(R["norse_by_beck_side"]["beck_side"]), nbs_brook=pct(R["norse_by_beck_side"]["brook_side"]),
    dl_bb_med=km(C["beck_brook"]["danelaw"]["median_km"]), dl_bb_min=km(C["beck_brook"]["danelaw"]["min_km"]),
    bvn_n=n(R["beck_vs_norse"]["n_hex"]), bvn_rho=f'{R["beck_vs_norse"]["rho"]:.2f}',
    bvn_lo=f'{R["beck_vs_norse"]["ci"][0]:.2f}', bvn_hi=f'{R["beck_vs_norse"]["ci"][1]:.2f}',
    band0_beck=pct(bands[0]["beck_share"]), band4_beck=pct(bands[-1]["beck_share"]),
    c_dale=f'{corrE["dale"]["rho"]:.2f}', c_beck=f'{corrE["beck"]["rho"]:.2f}', c_gill=f'{corrE["gill"]["rho"]:.2f}',
    c_fell=f'{corrE["fell"]["rho"]:.2f}', c_brook=f'{corrE["brook"]["rho"]:.2f}', c_down=f'{corrE["down"]["rho"]:.2f}',
    s_base=pct(R["danelaw_side_south"]["baseline_all_features"]), s_norse=pct(R["danelaw_side_south"]["norse_settlements"]),
    s_by=pct(south["by"]["share"]), s_thorpe=pct(south["thorpe"]["share"]), s_ton=pct(south["ton"]["share"]),
    s_brook=pct(south["brook"]["share"]), dn_brook=n(dn_brook), dn_beck=n(dn_beck),
    pf_sw=pct(prof[-20]["norse"], 1), pf_ne=pct(prof[0]["norse"], 1), pf_far=pct(prof[60]["norse"], 1),
    ct_brook=str(R["county_top_counts"]["stream"].get("brook", 0)), ct_burn=str(R["county_top_counts"]["stream"].get("burn", 0)),
    ct_nant=str(R["county_top_counts"]["stream"].get("nant", 0)), ct_beck=str(R["county_top_counts"]["stream"].get("beck", 0)),
    eau_top=str(eau["top_n"]), eau_n=str(eau["n"]),
    mn_name=ni["most_norse"][0]["name"], mn_n=str(ni["most_norse"][0]["norse"]), mn_e=str(ni["most_norse"][0]["english"]),
    mn_town=ni["top_towns"][0]["name"],
    me_name=ni["most_english"][0]["name"], me_cty=ni["most_english"][0]["county"],
    me_clough=str(nid["most_english"]["words"].get("clough", 0)), me_brook=str(nid["most_english"]["words"].get("brook", 0)),
    me_km=km(nid["most_english_km_to_beck_brook"]),
    audit_n=str(R["audit_total"]["n"]), audit_false=str(R["audit_total"]["false"]),
    strat_n=str(R["audit_strat"]["n"]), strat_false=str(R["audit_strat"]["false"]), strat_unc=str(R["audit_strat"]["uncertain"]),
)
V["mn_e_word"] = "one" if ni["most_norse"][0]["english"] == 1 else "ones"

html = T
for k, v in V.items():
    html = html.replace("{{" + k + "}}", v)
left = re.findall(r"\{\{(\w+)\}\}", html)
assert not left, f"unfilled placeholders: {sorted(set(left))}"

Rsite = {k: R[k] for k in ("counts", "boundaries", "transects", "transect_band_lat", "line_extent", "beck_vs_norse",
                           "danelaw_side_south", "danelaw_profile", "hidden", "counties", "rare", "norse_index",
                           "n_features", "n_norse_settlements")}
Rsite["geo"] = G
html = html.replace("/*__SITE__*/null", json.dumps(S, separators=(",", ":"), ensure_ascii=False))
html = html.replace("/*__R__*/null", json.dumps(Rsite, separators=(",", ":"), ensure_ascii=False))
open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(html)
print(f"index.html written, {len(html.encode('utf-8')) / 1e6:.2f} MB")
