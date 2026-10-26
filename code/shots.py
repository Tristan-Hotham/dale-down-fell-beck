"""Render index.html with Playwright Chromium at 1280px and 390px, light and dark, for checking.
Screenshots go to _shots/ (not part of the published site).

Usage: python3 code/shots.py [--vendor DIR]

Where Google Fonts and cdnjs are unreachable, pass --vendor with a folder holding the font files
(Fraunces, Source Serif 4, IBM Plex Mono TTFs) and leaflet/dist/. Map tiles are blocked; the map
background shows the page's sea colour instead.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = sys.argv[sys.argv.index("--vendor") + 1] if "--vendor" in sys.argv else None
OUT = os.path.join(ROOT, "_shots")
os.makedirs(OUT, exist_ok=True)


def fontcss():
    v = VENDOR
    return (f"@font-face{{font-family:'Fraunces';font-weight:100 900;src:url(file://{v}/Fraunces[SOFT,WONK,opsz,wght].ttf)}}"
            f"@font-face{{font-family:'Source Serif 4';font-weight:200 900;src:url(file://{v}/SourceSerif4[opsz,wght].ttf)}}"
            f"@font-face{{font-family:'Source Serif 4';font-style:italic;font-weight:200 900;src:url(file://{v}/SourceSerif4-Italic[opsz,wght].ttf)}}"
            f"@font-face{{font-family:'IBM Plex Mono';font-weight:400;src:url(file://{v}/IBMPlexMono-Regular.ttf)}}"
            f"@font-face{{font-family:'IBM Plex Mono';font-weight:500;src:url(file://{v}/IBMPlexMono-Medium.ttf)}}")


async def route(r):
    u = r.request.url
    if VENDOR and "fonts.googleapis.com" in u:
        return await r.fulfill(body=fontcss(), content_type="text/css")
    if VENDOR and "cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js" in u:
        return await r.fulfill(path=os.path.join(VENDOR, "leaflet", "dist", "leaflet.js"), content_type="application/javascript")
    if VENDOR and "cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" in u:
        return await r.fulfill(path=os.path.join(VENDOR, "leaflet", "dist", "leaflet.css"), content_type="text/css")
    if u.startswith("file://"):
        return await r.continue_()
    return await r.abort()


async def shoot(b, width, theme, extra=None):
    ctx = await b.new_context(viewport={"width": width, "height": 900}, color_scheme=theme, device_scale_factor=1)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
    await pg.route("**/*", route)
    await pg.goto("file://" + os.path.join(ROOT, "index.html"))
    await pg.wait_for_timeout(2500)
    sw = await pg.evaluate("document.documentElement.scrollWidth")
    tag = f"{width}_{theme}"
    await pg.screenshot(path=os.path.join(OUT, f"full_{tag}.png"), full_page=True)
    m = await pg.query_selector("#lmap")
    await m.scroll_into_view_if_needed()
    await pg.wait_for_timeout(400)
    fig = await pg.query_selector(".figure.bleed")
    await fig.screenshot(path=os.path.join(OUT, f"map_words_{tag}.png"))
    await pg.evaluate("window.__setView('bounds')")
    await pg.wait_for_timeout(800)
    await fig.screenshot(path=os.path.join(OUT, f"map_bounds_{tag}.png"))
    await pg.evaluate("window.__setView('words'); window.__setFam('hill'); window.__setWord('hill:fell')")
    await pg.wait_for_timeout(800)
    await fig.screenshot(path=os.path.join(OUT, f"map_fell_{tag}.png"))
    await pg.fill("#q", "Wensleydale")
    await pg.wait_for_timeout(500)
    await fig.screenshot(path=os.path.join(OUT, f"map_search_{tag}.png"))
    for sel in ["#transect", "#sharp", "#scatter", "#south", "#profile", "#sm", "#hidden", "#counts", "#ctab", "#rare"]:
        e = await pg.query_selector(sel)
        await e.scroll_into_view_if_needed()
        par = await e.evaluate_handle("n => n.closest('.figure') || n")
        await par.as_element().screenshot(path=os.path.join(OUT, f"fig_{sel[1:]}_{tag}.png"))
    print(tag, "scrollWidth", sw, "errors", errs[:5])
    await ctx.close()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w in (1280, 390):
            for t in ("light", "dark"):
                await shoot(b, w, t)
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())
