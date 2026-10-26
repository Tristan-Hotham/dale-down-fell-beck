"""Step 5. Make header.png (1200x630 social card) with Playwright, in the page's house style.
The map on the right colours each 10 km hexagon by its commonest stream word.

Usage: python3 code/header.py [--vendor DIR]   (DIR as in shots.py, for offline fonts)
"""
import asyncio
import json
import os
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shots  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(os.path.join(ROOT, "work", "site_data.json"), encoding="utf-8"))
R = json.load(open(os.path.join(ROOT, "data", "results.json"), encoding="utf-8"))
COL = {"beck": "#6E9FE0", "brook": "#F26A30", "burn": "#D6A136", "allt": "#7FAE58", "nant": "#C27BD3", "afon": "#C27BD3"}
nh = len(S["hex"]["cx"])
best = [None] * nh
for w in COL:
    a = S["hex"]["w"].get(f"stream:{w}", [])
    for i in range(0, len(a), 2):
        h, n = a[i], a[i + 1]
        if w == "afon":
            continue
        if w == "nant":
            n += dict(zip(S["hex"]["w"]["stream:afon"][0::2], S["hex"]["w"]["stream:afon"][1::2])).get(h, 0)
        if best[h] is None or n > best[h][1]:
            best[h] = (w, n)
hexes = [[S["hex"]["cx"][i], S["hex"]["cy"][i], COL[best[i][0]] if best[i] else "#2A2822"] for i in range(nh) if S["hex"]["cy"][i] < 1000]

HTML = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,900&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400&display=swap">
<style>
body{margin:0;width:1200px;height:630px;background:#15140F;color:#EDE8DC;overflow:hidden;position:relative;font-family:'Source Serif 4',Georgia,serif}
.l{position:absolute;left:72px;top:60px;width:700px}
.k{font:500 17px/1 'IBM Plex Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:#A59E8E;display:flex;gap:14px;align-items:center}
.k b{background:#F26A30;color:#15140F;padding:8px 10px;font-weight:500}
h1{font:900 100px/.9 'Fraunces',Georgia,serif;letter-spacing:-.02em;margin:26px 0 0}
h1 .b{color:#6E9FE0}h1 .o{color:#F26A30}
p{font-size:26px;line-height:1.36;margin:26px 0 0;color:#D9D3C5;max-width:600px}
.f{position:absolute;left:72px;bottom:38px;font:400 15px/1 'IBM Plex Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:#8C8577}
svg{position:absolute;right:40px;top:22px;height:586px}
.lg{position:absolute;left:72px;top:450px;font:400 16px/1.7 "IBM Plex Mono",monospace;color:#A59E8E}
.lg i{display:inline-block;width:12px;height:12px;margin:0 7px 0 0;vertical-align:-1px}.lg i~i{margin-left:18px}
</style></head><body>
<div class="l"><div class="k"><b>Data study</b><span>Landscape × language</span></div>
<h1>Dale, <span class="o">down</span>,<br><span class="b">fell</span> and <span class="b">beck</span></h1>
<p>The words Britain uses for its hills, valleys and streams, mapped from __N__ named features.</p></div>
<div class="f">Dr Tristan Hotham · Independent researcher</div>
<svg id="m" viewBox="60 0 600 1000"></svg>
<div class="lg">Commonest stream word in each 10 km hexagon<br><i style="background:#F26A30"></i>brook<i style="background:#6E9FE0"></i>beck<i style="background:#D6A136"></i>burn<br><i style="margin-left:0;background:#7FAE58"></i>allt<i style="background:#C27BD3"></i>nant / afon</div>
<script>
const H=__HEX__, R=10/Math.sqrt(3), s=document.getElementById('m');
for(const [x,y,c] of H){let d='';for(let i=0;i<6;i++){const a=Math.PI/180*(60*i+30);d+=(i?'L':'M')+(x+R*Math.cos(a)).toFixed(1)+' '+(1000-y-R*Math.sin(a)).toFixed(1);}
const p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('d',d+'Z');p.setAttribute('fill',c);s.appendChild(p);}
</script></body></html>"""


async def main():
    html = HTML.replace("__HEX__", json.dumps(hexes, separators=(",", ":"))).replace("__N__", f"{R['n_landscape_classified']:,}")
    tmp = os.path.join(ROOT, "work", "_header_tmp.html")
    open(tmp, "w", encoding="utf-8").write(html)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1200, "height": 630})
        await pg.route("**/*", shots.route)
        await pg.goto("file://" + tmp)
        await pg.wait_for_timeout(1200)
        await pg.screenshot(path=os.path.join(ROOT, "header.png"))
        await b.close()
    os.remove(tmp)
    print("header.png written")

if __name__ == "__main__":
    asyncio.run(main())
