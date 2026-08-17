# The Big Five — Data-Visualization Final Project

An interactive comparison of Europe's five elite football leagues (England, Spain, Italy,
Germany, France) across **26 seasons / 46,709 matches (2000/01–2025/26)**, built from scratch
with **D3.js v7**.

**Live:** https://shadimaj1.github.io/big5-project/

## Files
| File | Purpose |
|------|---------|
| `index.html` | The whole application (HTML + CSS + D3, single file). |
| `data.js` | The pre-processed bundle inlined as `window.BIG5`, so the page also opens from disk. |
| `data/big5.json` | The same bundle as standalone JSON. |
| `preprocess.py` | Reproducible pandas pipeline: raw CSVs → bundle, ending in a self-validating step. |
| `build_report.js` | Builds `Big5_Report_HE.docx` from `data/big5.json`, so the report cannot drift from the data. |
| `figures/` | Dashboard screenshots embedded in the report, plus their pixel sizes. |
| `vendor-d3.min.js` | Local D3, loaded automatically only if the CDN is unreachable. |
| `Big5_Report_HE.docx` | The written report (Hebrew). |

## Rebuild
```bash
git clone https://github.com/datasets/football-datasets   # raw season CSVs
# put the five league folders next to preprocess.py, then:
python3 preprocess.py     # -> data/big5.json + data.js  (fails loudly if a check breaks)
npm install docx
node build_report.js      # -> Big5_Report_HE.docx
```
Open `index.html` in any browser. D3 loads from a CDN with `vendor-d3.min.js` as an
automatic fallback, so the page works with or without a network.

## Publish on GitHub Pages
**Settings → Pages → Build and deployment → Source: "Deploy from a branch" → `main` / root → Save.**

## Data source
<https://github.com/datasets/football-datasets> — Premier League, La Liga, Serie A,
Bundesliga and Ligue 1, one CSV per season, derived from football-data.co.uk.

## Methodology: the decisions that change the answer
Seven things in the raw feed produce wrong charts if taken at face value. Each is handled
explicitly in `preprocess.py` and surfaced in the interface rather than hidden.

1. **Tie-break rules differ by league.** England, Germany and France separate teams level on
   points by goal difference; Spain and Italy use the head-to-head record first. The resolver
   is recursive, so a block of three or more tied teams has its mini-table rebuilt among the
   sides still level. Sorting everything by goal difference would award La Liga 2006/07 to
   Barcelona — the real champion is Real Madrid, on head-to-head, both on 76 points.
2. **Titles decided off the field.** Serie A 2004/05 (revoked, never awarded) and 2005/06
   (reassigned to Inter) after Calciopoli. Standings keep the on-field leader; title counts use
   the official outcome; both are shown.
3. **Rates that divide each other need one denominator.** Cards per foul, goals per shot and
   on-target share are computed over the intersection of matches that have every column
   involved. Serie A 2014/15, for instance, records yellows for 379 matches and reds for 380.
4. **The shot-counting definition changes mid-series.** On-target share is bimodal in the
   source (32–38% vs 43–57%), and in some seasons the shot totals move too. Seven such seasons
   are flagged and excluded from shot-derived charts; plotting them invents a 14% Italian
   finishing-efficiency spike.
5. **An abandoned season.** Ligue 1 2019/20 stopped in March 2020 after 279 of 380 matches with
   clubs on 27–28 games, so no winning margin is computed for it and the chart shows a gap.
6. **Missing is never zero.** A metric absent from the source stays absent, and the line breaks
   there instead of interpolating — including interior holes such as Bundesliga 2002/03.
7. **League averages need one shared window.** Detailed stats start in different years per
   league and foul rates drift down over time, so averaging each league over its own coverage
   quietly rewards the ones with the longest history. Measured that way the Bundesliga looks
   like Europe's most-fouling league; over the 19 seasons all five share it is only third, and
   Italy leads. Every league average is computed on the seasons all five have, and the window
   used is published with the metric and printed in the caption.

The COVID comparison uses **2018/19** as its baseline, not 2019/20: the Bundesliga and Serie A
already finished 2019/20 behind closed doors. Against 2018/19 the home-win rate fell in all five
leagues; against 2019/20 the effect all but disappears. The result is treated as strong evidence
consistent with a crowd contribution, not as causal proof.

## How to read the app
- **Legend chips** (top right): click a league to focus it across every chart and every
  dashboard; hover to preview.
- Five linked dashboards — **Overview**, **Home Advantage**, **Goals & Style**, **Discipline**,
  **Title Races** — one research question each.
- Rich tooltips everywhere, plus metric toggles, a season slider and a standings drill-down.
- Colours are the Okabe–Ito colour-blind-safe palette, used unmodified. Simulated worst-pair
  separation is ΔE 23.8 (protanopia), 16.4 (deuteranopia) and 10.7 (tritanopia) — the last is
  weak, so colour is never load-bearing: every series carries an end-of-line text label, every
  mark a tooltip, and any league can be isolated with one click.
