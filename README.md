# The Big Five — Data Visualization Final Project

This project is an interactive comparison of five major European football
leagues: England, Spain, Italy, Germany and France.

The analysis covers 26 seasons, from 2000/01 to 2025/26, and includes
46,709 matches. The website was built with D3.js v7, HTML, CSS and
JavaScript.

**Live website:**  
https://shadimaj1.github.io/big5-project/

---

## What the project looks at

The visualization is organized around four main research questions:

1. Is home advantage becoming weaker over time?
2. Are the five leagues becoming more similar in terms of goals and playing style?
3. Do the numbers support differences in fouls, cards and refereeing?
4. Are some leagues more competitive than others in the title race?

The website contains five sections:

- **Overview** — general comparison of the five leagues
- **Home Advantage** — changes in home-win rates
- **Goals & Style** — goals, shots and finishing
- **Discipline** — fouls, cards and fouls per card
- **Title Races** — winning margins and final standings

The charts are connected. Clicking a league in the legend focuses that
league across the different visualizations, while hovering provides more
details.

---

## Files

| File | Description |
|------|-------------|
| `index.html` | Main application containing the HTML, CSS and JavaScript |
| `data.js` | Processed data stored in `window.BIG5`, used directly by the website |
| `data/big5.json` | The same processed data in JSON format |
| `preprocess.py` | Python script used to process the original season CSV files |
| `build_report.js` | Script used to generate the Hebrew report from the processed data |
| `figures/` | Images used in the written report |
| `vendor-d3.min.js` | Local copy of D3.js used as a fallback when the CDN is unavailable |
| `Big5_Report_HE.docx` | Written project report in Hebrew |

---

## Data source

The original data comes from:

https://github.com/datasets/football-datasets

The repository contains season-level CSV files based on data from
football-data.co.uk.

For this project, data from the following leagues was used:

- Premier League — England
- La Liga — Spain
- Serie A — Italy
- Bundesliga — Germany
- Ligue 1 — France

The selected period is 2000/01–2025/26.

The preprocessing script combines the season files and creates the
league-season data used by the website.

---

## Data processing

The raw data cannot always be used directly. Several issues were found
during preprocessing and were handled in the Python script.

### 1. Different tie-break rules

The leagues do not all use the same tie-break rule.

England, Germany and France use goal difference when teams finish with
the same number of points.

Spain and Italy use head-to-head results first.

For this reason, the final standings were recalculated instead of simply
sorting every league by goal difference.

For example, in La Liga 2006/07, using goal difference instead of the
Spanish tie-break rule would incorrectly put Barcelona above Real Madrid.
The two teams finished level on 76 points, but Real Madrid won the title
on the head-to-head record.

The script also handles situations where more than two teams are tied.

---

### 2. Official title outcomes

The results data and the official title record are not always identical.

This is relevant to Serie A in the period affected by the Calciopoli
scandal.

- 2004/05 — the title was revoked and was not awarded
- 2005/06 — the title was taken from Juventus and awarded to Internazionale

The standings are still calculated from the match results, while the
title-count visualization uses the official outcome.

This difference is shown in the website instead of being hidden.

---

### 3. Rate calculations

Some metrics are ratios of two other measurements.

For example:

- fouls per yellow card
- goals per shot
- shots on target share

For these calculations, only matches where the required columns are
available are included.

This avoids using different denominators for the numerator and
denominator.

---

### 4. Shot data

The source data contains changes in the way shots on target were recorded.

The on-target share shows two different ranges in the source data.
Some seasons therefore cannot be compared directly with the later data.

Seven seasons were flagged during preprocessing and excluded from
shot-derived comparisons.

This prevents a change in the source definition from appearing as a
real change in finishing ability.

---

### 5. Ligue 1 2019/20

The 2019/20 Ligue 1 season was stopped early in March 2020.

Only 279 of the expected 380 matches were played.

Because the season was incomplete, a winning margin is not calculated for
that season. The missing value is shown as a gap rather than being
treated as zero.

---

### 6. Missing values

Missing values are kept as missing.

They are not replaced with zero and are not interpolated between two
existing values.

When a metric is unavailable for a season, the corresponding line in the
visualization contains a gap.

---

### 7. Comparing league averages

Detailed statistics are not available for exactly the same number of
seasons in every league.

Using a different time period for each league could affect the comparison,
especially for statistics such as fouls per game that changed over time.

For comparisons between all five leagues, the common available period is
used.

The time window used for a metric is also reported in the visualization
or its accompanying explanation.

---

## COVID-19 comparison

The home-advantage comparison uses 2018/19 as the baseline for the
COVID period.

This was chosen because some leagues had already completed the 2019/20
season under unusual conditions, including matches played without
spectators.

Compared with 2018/19, the home-win rate decreased across all five
leagues during the period affected by empty stadiums.

This result is consistent with the idea that the presence of spectators
may affect home advantage, but the analysis does not establish a causal
relationship.

---

## Visualization design

The project was built with D3.js v7.

The charts were created as SVG visualizations rather than using a
ready-made charting library.

The project uses several visualization types, including:

- line charts for changes over time
- bar charts for league comparisons
- slope/dumbbell charts for comparing two periods
- scatter plots for relationships between metrics
- stacked bars for result distributions
- radar charts for league profiles
- tables for detailed final standings

The visualization types were selected according to the type of comparison
being made.

For example, line charts are used when the main question is how a metric
changes over several seasons, while scatter plots are used when comparing
two metrics at the same time.

---

## Interactivity

The website includes several interactive features:

- league selection through the legend
- league focus across multiple charts
- hover tooltips
- metric selection
- season slider
- league and season selection for final standings
- linked visualizations between the different sections

Selecting a league does not only change one chart. The selected league is
highlighted across the relevant visualizations.

---

## Accessibility

The colour palette is based on the Okabe–Ito palette.

Colour is not used as the only way to identify a league. The charts also
include text labels and tooltips, and individual leagues can be isolated
through the legend.

The colour palette was checked using colour-vision simulations. The
measured separations were:

- Protanopia: ΔE 23.8
- Deuteranopia: ΔE 16.4
- Tritanopia: ΔE 10.7

Because the separation is weaker in some simulations, the visualization
does not rely on colour alone.

---

## Running the project locally

The website can be opened directly from `index.html`.

D3.js is normally loaded from the CDN. A local copy,
`vendor-d3.min.js`, is also included as a fallback if the CDN cannot be
reached.

The processed data is already included in `data.js`, so no server is
required just to view the visualization.

---

## Reproducing the data processing

The original season data can be obtained from:

https://github.com/datasets/football-datasets

After downloading the data, place the five league folders next to
`preprocess.py`.

Then run:

```bash
python3 preprocess.py