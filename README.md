# The Big Five — Data-Visualization Final Project

An interactive comparison of Europe's five elite football leagues (England, Spain, Italy,
Germany, France) across **26 seasons / 46,709 matches (2000/01–2025/26)**. Built from scratch
with **D3.js v7**.

## Files
| File | Purpose |
|------|---------|
| `index.html` | The whole application (HTML + CSS + D3 code, single file). |
| `data.js` | Pre-processed data bundle, inlined as `window.BIG5` (so the page also works when opened directly from disk). |
| `data/big5.json` | The same bundle as a standalone JSON. |
| `preprocess.py` | Reproducible Python (pandas) pipeline that builds the bundle from the raw CSVs. |

## Run it locally
Just open `index.html` in any modern browser (needs internet once, to load D3 from a CDN).

## Publish on GitHub Pages (gives you the working link for the report)
1. Create a new GitHub repository and upload the contents of this folder
   (`index.html`, `data.js`, and the `data/` folder).
2. Repo **Settings → Pages → Build and deployment → Source: “Deploy from a branch”**,
   pick `main` / root, **Save**.
3. After ~1 minute your project is live at
   `https://<your-username>.github.io/<repo-name>/`.

## Data source
Raw match data: <https://github.com/datasets/football-datasets>
(Premier League, La Liga, Serie A, Bundesliga, Ligue 1 — one CSV per season).

## How to read the app
- **Legend chips** (top-right): click a league to *focus* it across every chart; hover to preview.
- Five linked dashboards: **Overview**, **Home Advantage**, **Goals & Style**, **Discipline**, **Title Races**.
- Every mark has a rich tooltip; several charts have metric toggles, a season slider, and a standings drill-down.
