"""Draw 30 random matches per family (fixed seed) for a by-eye false-positive check, plus every
compound-rule match for a few risky words. The verdicts I recorded are in AUDIT_FALSE below and are
copied into results.json by analysis.py.

Usage: python3 code/audit.py [seed]
"""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 2026

# Names from the seed-2026 samples judged to be wrong (word not used as that landscape generic).
AUDIT_FALSE = {
    "stream": [], "valley": [], "hill": [], "settlement": [], "fall": [],
}
# Second, stratified check (seed 11): 30 per family drawn after removing each family's two commonest
# words, so that the rarer rules are tested too. Judged wrong / uncertain:
STRAT_SEED = 11
STRAT_FALSE = {"stream": [], "valley": [], "hill": [], "settlement": []}
STRAT_UNCERTAIN = {"settlement": ["Killochyett"]}  # kil- here may not be Gaelic cill or coille
# Earlier targeted checks found and fixed: "Easter" and "Wester" caught by -ster, and Dunkirk by kirk.


def sample():
    m = pd.read_csv(os.path.join(ROOT, "data", "landscape_words.csv"), keep_default_na=False)
    out = {}
    for fam in ["stream", "valley", "hill", "settlement", "fall"]:
        s = m[m.family == fam].sample(30, random_state=SEED)
        out[fam] = s[["name", "word", "local_type", "county"]].values.tolist()
    return out


def strat_sample():
    m = pd.read_csv(os.path.join(ROOT, "data", "landscape_words.csv"), keep_default_na=False)
    out = {}
    for fam in ["stream", "valley", "hill", "settlement"]:
        s = m[m.family == fam]
        top = s.word.value_counts().index[:2]
        x = s[~s.word.isin(top)].sample(30, random_state=STRAT_SEED)
        out[fam] = x[["name", "word", "local_type", "county"]].values.tolist()
    return out


if __name__ == "__main__":
    for fam, rows in sample().items():
        print("==", fam)
        for r in rows:
            print("  ", r[1].ljust(8), "|", r[0], "|", r[2], "|", r[3])
    for fam, rows in strat_sample().items():
        print("== stratified", fam)
        for r in rows:
            print("  ", r[1].ljust(8), "|", r[0], "|", r[2], "|", r[3])
