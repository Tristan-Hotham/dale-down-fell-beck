# Dale, Down, Fell and Beck

The words Britain uses for its hills, valleys and streams, mapped. Where beck gives way to brook and burn, where dale meets clough and combe, how sharp those lines are, and whether they follow Norse settlement names, the approximate Danelaw line and the borders with Wales and Scotland.

**Interactive version:** https://tristan-hotham.github.io/dale-down-fell-beck/

This repository holds the interactive page, the classified features, hexagon shares, fitted boundaries, results and the analysis code for the data post *Dale, Down, Fell and Beck* by Dr Tristan Hotham (Independent researcher, ORCID 0000-0003-4931-9349).

## Files

- `index.html`: the interactive page (Leaflet map with a word picker, boundaries view and name search; charts; small multiples; tables).
- `header.png`: social card.
- `data/landscape_words.csv`: one row per matched feature: name, word, family (stream, valley, hill, fall, settlement), OS local type, latitude, longitude, county or unitary area, country.
- `data/hex_shares.csv`: for each 10 km hexagon (British National Grid) and word, the count, the family total in that hexagon and the share. The pseudo-word `norse_any` gives the number and share of settlements with any Norse element.
- `data/boundaries.geojson`: fitted 50% lines between pairs of words (split into 60 km stretches, each with its local 80% to 20% distance), the approximate Danelaw line, and the England and Wales and England and Scotland borders derived from OS Open Names.
- `data/results.json`: every number quoted on the page.
- `code/`: Python scripts, run in this order:
  - `words.py`: the regular-expression rules for each word, with tests (`python3 code/words.py`).
  - `streams.py`: joins OS Open Rivers links into one point per named watercourse.
  - `match.py`: applies the rules to OS Open Names and the watercourses.
  - `analysis.py`: hexagon shares, boundary fitting and sharpness, Danelaw and border comparisons, correlations, county tables.
  - `audit.py`: the random samples used for the false-positive check, with the recorded verdicts.
  - `build_site.py`: fills `page_template.html` with numbers from `results.json` to make `index.html`.
  - `header.py`, `shots.py`: social card and test screenshots (Playwright).

The scripts expect the OS Open Names extract (`osnames_gb.tsv`) and the OS Open Rivers GeoPackage (`osrivers/Data/oprvrs_gb.gpkg`) one folder above this repository; both are free downloads from Ordnance Survey. Intermediate files go to `work/`, which is not part of the repository.

## Caveats

OS Open Names is a modern map, not a historical record. Many names are recent, and a name on the map says what a place is called now, not when it was first named. The Danelaw line is hand-placed from the treaty description and is approximate. Word rules were checked on random samples (see `audit.py`), but some matches will still be wrong.

## Sources and licence

- Contains OS data © Crown copyright and database right 2026. OS Open Names and OS Open Rivers, Ordnance Survey, Open Government Licence v3.0.
- Base map on the interactive page: tiles © Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community.

The derived data and the text are released under CC BY 4.0 (compatible with the Open Government Licence; please keep the Crown copyright statement above when reusing the data). Code is MIT (see `LICENSE`).

I wrote the text, with drafting and editing assistance from Claude (Anthropic), which also helped prepare the analysis code. I reviewed and checked all text and results.
