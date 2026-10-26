"""Explicit, auditable rules for finding landscape words in OS place names.

Every rule is a regular expression applied to one lower-cased token (a word of the name, split on
spaces). A name gets at most one word per family, chosen in this order:

  1. "X of Y" names (Burn of Tafts, Water of Leith, Glen of Rothes): the first token, for words
     marked of_ok.
  2. The last token, if it is a whole generic word (Mill Beck, Stanage Edge, Hartside Fell).
  3. The first token, for words that come first in Welsh, Gaelic or English word order
     (Afon Conwy, Nant y Moch, Allt Beag, Cwm Idwal, Beinn Bhan, River Waveney).
  4. The last token as a compound ending (Borrowdale, Troutbeck, Scafell, Ashbourne) for words
     marked with a `compound` rule, with a minimum stem length and an exclusion list.
  5. The first token as a compound beginning, for words with a `pcompound` rule (Strathspey).

If name1 gives nothing, name2 (the Welsh or Gaelic alternative, where there is one) is tried.
Settlement elements are matched on any token of the name (Kirkby Lonsdale, Thorpe le Soken),
in the priority order of SETTLEMENT below; Norse elements are tried first.

Run this file directly to test the rules on hand-written examples.
"""
import re
import unicodedata


def W(key, label, origin, suffix=None, prefix=None, compound=None, pcompound=None, of_ok=False,
      exclude=(), note=""):
    return dict(key=key, label=label, origin=origin, suffix=suffix, prefix=prefix, compound=compound,
                pcompound=pcompound, of_ok=of_ok, exclude=set(exclude), note=note)


# origin is a broad, cautious language label used only for colouring: "norse", "english",
# "brittonic" (Welsh, Cornish and Cumbric), "gaelic", "scots", "mixed" or "plain".
FAMILIES = {
    "stream": [
        W("beck", "beck", "norse", suffix=r"becks?", compound=r".{2,}beck"),
        W("burn", "burn", "scots", suffix=r"burns?", compound=r".{3,}burn", of_ok=True,
          exclude={"bourn"}),
        W("brook", "brook", "english", suffix=r"brooks?", compound=r".{3,}brook"),
        W("water", "water", "english", suffix=r"water", of_ok=True),
        W("river", "river", "plain", suffix=r"river", prefix=r"river"),
        W("afon", "afon", "brittonic", prefix=r"afon"),
        W("nant", "nant", "brittonic", prefix=r"nant"),
        W("allt", "allt", "gaelic", prefix=r"allt|alltan"),
        W("abhainn", "abhainn", "gaelic", prefix=r"abhainn|amhainn|abhuinn"),
        W("caochan", "caochan", "gaelic", prefix=r"caochan"),
        W("sike", "sike", "mixed", suffix=r"sikes?|sykes?", compound=r".{3,}(sike|syke)"),
        W("gill", "gill", "norse", suffix=r"gills?|ghylls?", compound=r".{2,}(gill|ghyll)"),
        W("bourne", "bourne", "english", suffix=r"bournes?|bourn", compound=r".{3,}bourne?"),
        W("rhyne", "rhyne", "plain", suffix=r"rhynes?|rhines?"),
        W("reen", "reen", "plain", suffix=r"reens?"),
        W("lode", "lode", "english", suffix=r"lodes?"),
        W("eau", "eau", "plain", suffix=r"eau"),
        W("rife", "rife", "plain", suffix=r"rife"),
        W("lake", "lake", "plain", suffix=r"lake", note="In south-west England 'lake' is a small stream"),
        W("dike", "dike / dyke", "mixed", suffix=r"dikes?|dykes?", compound=r".{3,}(dike|dyke)"),
        W("drain", "drain", "plain", suffix=r"drains?"),
        W("ditch", "ditch", "plain", suffix=r"ditch(es)?"),
        W("sewer", "sewer", "plain", suffix=r"sewers?"),
        W("fleet", "fleet", "english", suffix=r"fleet"),
        W("gutter", "gutter", "plain", suffix=r"gutters?"),
        W("grain", "grain", "plain", suffix=r"grains?"),
        W("cleugh", "cleugh", "scots", suffix=r"cleughs?|cleuchs?"),
        W("clough", "clough", "english", suffix=r"cloughs?"),
        W("pow", "pow", "scots", suffix=r"pow", of_ok=True),
        W("stream", "stream", "plain", suffix=r"stream"),
    ],
    "valley": [
        W("dale", "dale", "mixed", suffix=r"dales?", compound=r".{2,}dale"),
        W("dean", "dean / dene", "english", suffix=r"deans?|denes?", compound=r".{3,}(dean|dene)"),
        W("den", "den", "scots", suffix=r"dens?", of_ok=True),
        W("combe", "combe", "brittonic", suffix=r"combes?|coombes?|coombs?",
          compound=r".{3,}(combe|coombe|coomb)"),
        W("clough", "clough", "english", suffix=r"cloughs?", compound=r".{3,}clough"),
        W("cleugh", "cleugh", "scots", suffix=r"cleughs?|cleuchs?", compound=r".{3,}(cleugh|cleuch)"),
        W("cwm", "cwm", "brittonic", suffix=r"cwm", prefix=r"cwm"),
        W("glen", "glen", "gaelic", suffix=r"glens?", prefix=r"glen|gleann|ghleann", pcompound=r"glen.{3,}",
          of_ok=True, exclude={"glenn"}),
        W("coire", "coire / corrie", "gaelic", suffix=r"corries?", prefix=r"coire|coir'|coireag|coireachan|corrie|choire"),
        W("strath", "strath", "gaelic", prefix=r"strath|srath", pcompound=r"strath.{3,}"),
        W("glac", "glac", "gaelic", prefix=r"glac"),
        W("gill", "gill", "norse", suffix=r"gills?|ghylls?", compound=r".{2,}(gill|ghyll)"),
        W("hope", "hope", "english", suffix=r"hopes?"),
        W("slade", "slade", "english", suffix=r"slades?"),
        W("bottom", "bottom", "english", suffix=r"bottoms?"),
        W("dingle", "dingle", "english", suffix=r"dingles?"),
        W("slack", "slack", "mixed", suffix=r"slacks?"),
        W("chine", "chine", "english", suffix=r"chines?"),
        W("valley", "valley", "plain", suffix=r"valley"),
        W("vale", "vale", "plain", suffix=r"vale", of_ok=True),
        W("hollow", "hollow", "plain", suffix=r"hollows?"),
        W("dell", "dell", "plain", suffix=r"dells?"),
        W("gully", "gully", "plain", suffix=r"gull(y|ies)"),
        W("dyffryn", "dyffryn", "brittonic", prefix=r"dyffryn"),
    ],
    "hill": [
        W("hill", "hill", "english", suffix=r"hills?|hillocks?", compound=r".{3,}hill", of_ok=True),
        W("fell", "fell", "norse", suffix=r"fells?", compound=r".{2,}fell"),
        W("down", "down", "english", suffix=r"downs?"),
        W("tor", "tor", "english", suffix=r"tors?", compound=r".{2,}tor", exclude={"doctor", "mentor"}),
        W("pike", "pike", "plain", suffix=r"pikes?", compound=r".{3,}pike"),
        W("knott", "knott", "plain", suffix=r"knott?s?"),
        W("how", "how / howe", "norse", suffix=r"howe?s?"),
        W("law", "law", "scots", suffix=r"laws?"),
        W("knowe", "knowe", "scots", suffix=r"knowes?"),
        W("rigg", "rig / rigg", "plain", suffix=r"rigg?s?"),
        W("edge", "edge", "english", suffix=r"edges?"),
        W("beacon", "beacon", "english", suffix=r"beacons?"),
        W("crag", "crag", "plain", suffix=r"crags?"),
        W("bryn", "bryn", "brittonic", prefix=r"bryn"),
        W("moel", "moel / foel", "brittonic", prefix=r"moel|foel"),
        W("mynydd", "mynydd", "brittonic", prefix=r"mynydd|fynydd"),
        W("pen", "pen", "brittonic", prefix=r"pen"),
        W("cefn", "cefn", "brittonic", prefix=r"cefn"),
        W("ben", "ben / beinn", "gaelic", prefix=r"ben|beinn|bheinn|beinne", suffix=r"bheinn"),
        W("meall", "meall", "gaelic", prefix=r"meall|mheall|meallan"),
        W("cnoc", "cnoc / knock", "gaelic", prefix=r"cnoc|cnocan|chnoc|knock"),
        W("sgurr", "sgurr", "gaelic", prefix=r"sg[uù]rr|sgòrr|sgorr"),
        W("carn", "carn / cairn", "mixed", prefix=r"c[aà]rn|cairn"),
        W("creag", "creag", "gaelic", prefix=r"creag|chreag"),
    ],
    "fall": [
        W("force", "force", "norse", suffix=r"force", compound=r".{3,}force"),
        W("foss", "foss", "norse", suffix=r"foss"),
        W("linn", "linn", "scots", suffix=r"linns?", prefix=r"linn", of_ok=True),
        W("falls", "falls", "plain", suffix=r"falls?|waterfalls?", prefix=r"falls?", of_ok=True),
        W("spout", "spout", "plain", suffix=r"spout", prefix=r"spout|sp[uù]t", of_ok=True),
        W("eas", "eas", "gaelic", prefix=r"eas|easan"),
        W("pistyll", "pistyll", "brittonic", prefix=r"pistyll"),
        W("rhaeadr", "rhaeadr", "brittonic", prefix=r"rhaeadr"),
        W("sgwd", "sgwd", "brittonic", prefix=r"sg[wŵ]d"),
    ],
}

# Settlement-name elements, matched on any token. Tried in this order; the first match wins.
# `where` limits a rule to one or more countries, to avoid known false friends
# (Scots kirk = church in Kirkcaldy and Falkirk; Old English ceaster in Chester and Leicester;
# Balham and Kilburn in England; Tenby, which is Welsh Dinbych).
SETTLEMENT = [
    dict(key="thwaite", label="-thwaite", origin="norse", rx=r".*thwaite?s?"),
    dict(key="toft", label="-toft", origin="norse", rx=r".*tofts?"),
    dict(key="thorpe", label="-thorpe", origin="norse", rx=r".*thorpe?s?"),
    dict(key="by", label="-by", origin="norse", rx=r"[a-z]{2,}by", exclude={"tenby", "abby", "hobby", "lobby"}),
    dict(key="by", label="-by", origin="norse", rx=r"[a-z]{3,}bie", where={"Scotland"}),
    dict(key="holme", label="-holme", origin="norse", rx=r"(.*(holme|hulme)s?)|(.{0,}holm)"),
    dict(key="kirk", label="kirk-", origin="norse", rx=r"kirk.*|.*kirk", where={"England"},
         exclude={"dunkirk"}),
    dict(key="setter", label="-setter / -bister", origin="norse",
         rx=r".*(setter|bister|busta)|.{2,}ster", where={"Scotland"},
         exclude={"easter", "wester", "lister", "webster", "dempster"},
         exclude_rx=r".*(chester|caster|minster)"),
    dict(key="llan", label="llan-", origin="brittonic", rx=r"llan.+"),
    dict(key="aber", label="aber-", origin="brittonic", rx=r"aber.{2,}"),
    dict(key="tre", label="tre-", origin="brittonic", rx=r"tref?.{3,}", where={"Wales", "England_SW"},
         exclude_rx=r"tre(e|nt|nch|ntham|vor).*"),
    dict(key="bal", label="bal-", origin="gaelic", rx=r"bal{1,2}[a-z]{3,}", where={"Scotland"}),
    dict(key="inver", label="inver-", origin="gaelic", rx=r"inver.{2,}", where={"Scotland"}),
    dict(key="kil", label="kil-", origin="gaelic", rx=r"kil[a-z]{3,}", where={"Scotland"}),
    dict(key="ton", label="-ton", origin="english", rx=r"[a-z]{2,}tons?"),
    dict(key="ham", label="-ham", origin="english", rx=r"[a-z]{2,}ham", exclude={"graham"}),
    dict(key="ley", label="-ley / -leigh", origin="english", rx=r"[a-z]{2,}(ley|leigh)|leigh",
         exclude={"valley"}),
    dict(key="worth", label="-worth", origin="english", rx=r"[a-z]{2,}worthy?"),
]
NORSE_SETTLEMENT = {"thwaite", "toft", "thorpe", "by", "holme", "kirk", "setter"}
SW_COUNTIES = {"Cornwall", "Isles of Scilly", "Devon"}

# Landscape words hidden inside settlement names (Ashbourne, Blackburn, Holbeck, Ilfracombe).
HIDDEN = [
    ("beck", r".{2,}beck"), ("burn", r".{2,}burn"), ("bourne", r".{2,}bourne?"), ("brook", r".{2,}brook"),
    ("dale", r".{2,}dale"), ("combe", r".{2,}(combe|coombe)"), ("dean", r".{2,}(dean|dene)"),
    ("thwaite", r".*thwaite"), ("hope", r".{2,}hope"),
]

FAMILY_LABEL = {"stream": "Streams", "valley": "Valleys", "hill": "Hills", "fall": "Waterfalls",
                "settlement": "Settlements"}


def tokens(name):
    s = unicodedata.normalize("NFC", name).lower().replace("’", "'").replace("`", "'")
    s = re.sub(r"\(.*?\)", " ", s)
    toks = [t.strip(".,;:!?\"") for t in s.split()]
    return [t for t in toks if t]


def _full(rx, t):
    return rx is not None and re.fullmatch(rx, t) is not None


def classify(name, family):
    """Return the word key for a landscape name, or None."""
    toks = tokens(name)
    if not toks:
        return None
    rules = FAMILIES[family]
    first, last = toks[0], toks[-1]
    if len(toks) >= 3 and toks[1] == "of":
        for r in rules:
            if r["of_ok"] and (_full(r["suffix"], first) or _full(r["prefix"], first)):
                return r["key"]
    for r in rules:
        if len(toks) > 1 or r["prefix"] is None:
            if _full(r["suffix"], last) and last not in r["exclude"]:
                return r["key"]
    if len(toks) > 1:
        for r in rules:
            if _full(r["prefix"], first):
                return r["key"]
    for r in rules:
        if _full(r["compound"], last) and last not in r["exclude"]:
            return r["key"]
    for r in rules:
        if _full(r["pcompound"], first) and first not in r["exclude"]:
            return r["key"]
    # a single-token name that is itself a prefix word ("Cwm", "Glen")
    if len(toks) == 1:
        for r in rules:
            if _full(r["prefix"], first):
                return r["key"]
    return None


def settlement_word(name, country, county=""):
    toks = tokens(name)
    for r in SETTLEMENT:
        where = r.get("where")
        if where:
            ok = country in where or ("England_SW" in where and county in SW_COUNTIES)
            if not ok:
                continue
        for t in toks:
            if t in r.get("exclude", ()):
                continue
            if r.get("exclude_rx") and re.fullmatch(r["exclude_rx"], t):
                continue
            if re.fullmatch(r["rx"], t):
                return r["key"]
    return None


def is_norse_settlement(name, country, county=""):
    """True if any token carries a Norse element (independent of the one-word assignment)."""
    toks = tokens(name)
    for r in SETTLEMENT:
        if r["key"] not in NORSE_SETTLEMENT:
            continue
        where = r.get("where")
        if where and country not in where:
            continue
        for t in toks:
            if t in r.get("exclude", ()):
                continue
            if r.get("exclude_rx") and re.fullmatch(r["exclude_rx"], t):
                continue
            if re.fullmatch(r["rx"], t):
                return True
    return False


def hidden_word(name):
    toks = tokens(name)
    if not toks:
        return None
    for key, rx in HIDDEN:
        if re.fullmatch(rx, toks[-1]):
            return key
    return None


def word_meta():
    out = {}
    for fam, rules in FAMILIES.items():
        for r in rules:
            out[f"{fam}:{r['key']}"] = dict(family=fam, key=r["key"], label=r["label"], origin=r["origin"])
    for r in SETTLEMENT:
        out[f"settlement:{r['key']}"] = dict(family="settlement", key=r["key"], label=r["label"],
                                            origin=r["origin"])
    return out


TESTS = [
    ("stream", "Mill Beck", "beck"), ("stream", "Troutbeck", "beck"), ("stream", "Burn of Tafts", "burn"),
    ("stream", "Water of Leith", "water"), ("stream", "Afon Conwy", "afon"), ("stream", "Nant y Moch", "nant"),
    ("stream", "Allt a' Mhaoilein", "allt"), ("stream", "River Waveney", "river"), ("stream", "Lealt River", "river"),
    ("stream", "Rough Sike", "sike"), ("stream", "Blankets Sewer", "sewer"), ("stream", "Glen Burn", "burn"),
    ("stream", "Holywell Brook", "brook"), ("stream", "River Nene (Whilton Branch)", "river"),
    ("stream", "Sherbourne", "bourne"), ("stream", "Huntspill Rhyne", "rhyne"), ("stream", "Thornship Gill", "gill"),
    ("stream", "Ashburn", "burn"), ("stream", "Ashbourn", "bourne"),
    ("valley", "Borrowdale", "dale"), ("valley", "Cwm Idwal", "cwm"), ("valley", "Glen Douglas", "glen"),
    ("valley", "Coire a' Ghaduiche", "coire"), ("valley", "Pinkie Cleugh", "cleugh"), ("valley", "Strathspey", "strath"),
    ("valley", "Little Dean Bottom", "bottom"), ("valley", "Riccarton Hope", "hope"), ("valley", "Hilldale", "dale"),
    ("valley", "Den of Airlie", "den"), ("valley", "Glenn", None), ("valley", "Golden Valley", "valley"),
    ("hill", "Scafell Pike", "pike"), ("hill", "Scafell", "fell"), ("hill", "Beinn Bhàn", "ben"),
    ("hill", "Ben Nevis", "ben"), ("hill", "Moel Famau", "moel"), ("hill", "Tod Law", "law"),
    ("hill", "Bodmin Downing", None), ("hill", "Haytor", "tor"), ("hill", "Silver How", "how"),
    ("hill", "Sgùrr na Coinnich", "sgurr"), ("hill", "Hill of Fare", "hill"), ("hill", "Cnoc Buidhe", "cnoc"),
    ("hill", "Stanage Edge", "edge"), ("hill", "Brecon Beacons", "beacon"),
    ("fall", "Aira Force", "force"), ("fall", "Falls of Clyde", "falls"), ("fall", "Pistyll Rhaeadr", "pistyll"),
]
STESTS = [
    ("Kirkby Lonsdale", "England", "by"), ("Bassenthwaite", "England", "thwaite"), ("Lowestoft", "England", "toft"),
    ("Scunthorpe", "England", "thorpe"), ("Tenby", "Wales", None), ("Lockerbie", "Scotland", "by"),
    ("Falkirk", "Scotland", None), ("Ormskirk", "England", "kirk"), ("Leicester", "England", None),
    ("Lerwick", "Scotland", None), ("Scrabster", "Scotland", "setter"), ("Balham", "England", "ham"),
    ("Llandudno", "Wales", "llan"), ("Inverness", "Scotland", "inver"), ("Kilburn", "England", None),
    ("Levenshulme", "England", "holme"), ("Valley", "Wales", None), ("Kettering", "England", None),
    ("Stow by Chartley", "England", "ley"), ("Easter Portclair", "Scotland", None), ("Wadbister", "Scotland", "setter"),
    ("Dunkirk", "England", None),
]

if __name__ == "__main__":
    bad = 0
    for fam, n, want in TESTS:
        got = classify(n, fam)
        if got != want:
            bad += 1
            print("FAIL", fam, n, "got", got, "want", want)
    for n, c, want in STESTS:
        got = settlement_word(n, c)
        if got != want:
            bad += 1
            print("FAIL settlement", n, "got", got, "want", want)
    print(f"{len(TESTS) + len(STESTS) - bad} of {len(TESTS) + len(STESTS)} tests pass")
