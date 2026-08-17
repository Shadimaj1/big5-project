#!/usr/bin/env python3
"""
Big Five - data pre-processing pipeline
=======================================
Reads the raw season CSVs from github.com/datasets/football-datasets
(premier-league, la-liga, serie-a, bundesliga, ligue-1) and produces the single
bundle `data/big5.json` consumed by the D3 web app, plus `data.js` (the same
bundle inlined so the page opens from disk without a server).

Design rules
------------
1.  Window: 2000/01-2025/26, the 26 seasons with full coverage in all five
    leagues (26 x 5 = 130 league-season rows).
2.  Only matches with a valid result (FTHG/FTAG/FTR) are used.
3.  Every comparative metric is normalised PER MATCH, because the Bundesliga
    and Ligue 1 play 306 matches to the other leagues' 380. Comparing season
    totals would make the 20-team leagues look artificially "busier".
4.  A missing value is never turned into a zero. Each rate is computed only
    over matches where ALL the columns that rate needs are present, and the
    metric is simply absent for a season the source never recorded. The charts
    then show a gap rather than an invented value.
5.  Rates that are later divided by one another (cards per foul, goals per
    shot, on-target share) are computed over the INTERSECTION of the matches
    that have every column involved. Mixing denominators would bias the ratio:
    e.g. Serie A 2014/15 records yellows for 379 matches but reds for 380, so
    the old `(yellows + reds) / n_yellow_matches` divided a 380-match red total
    by a 379-match denominator.
6.  Standings are recomputed from results with each league's OWN tie-break:
    goal difference in England/Germany/France, head-to-head first in Spain and
    Italy. The head-to-head resolver is recursive, so blocks of three or more
    tied teams are separated correctly (the mini-table is rebuilt among the
    teams that are still level, exactly as the regulations prescribe).
7.  Two source-integrity flags mark seasons the raw feed cannot be trusted on,
    and a `champion_official` field records titles that were decided off the
    field and therefore cannot be derived from results at all.

Run:  python3 preprocess.py     (expects the five league folders alongside)
"""
import glob, os, json, sys, pandas as pd, numpy as np
from collections import defaultdict

LEAGUES = {'premier-league':'Premier League','la-liga':'La Liga','serie-a':'Serie A',
           'bundesliga':'Bundesliga','ligue-1':'Ligue 1'}
CODES = {'premier-league':'ENG','la-liga':'ESP','serie-a':'ITA','bundesliga':'GER','ligue-1':'FRA'}
# Leagues whose first tie-breaker is the head-to-head record, not goal difference.
H2H_LEAGUES = {'la-liga', 'serie-a'}
WINDOW = range(2000, 2026)
WIN, DRAW = 3, 1

SOT_RATE_MAX  = 42.0   # on-target share above this = the legacy counting definition
SHOTS_DEV_MAX = 12.0   # % deviation from the local median above which shot totals are untrustworthy

# Titles decided off the field, which a results-based table cannot know about.
# `official` is None where no title was awarded at all.
TITLE_OVERRIDES = {
    ('Serie A', '2004/05'): (None,
        'After the Calciopoli scandal the title was revoked and never awarded to anyone.'),
    ('Serie A', '2005/06'): ('Inter',
        'After the Calciopoli scandal the title was stripped and awarded to Internazionale, '
        'who finished third on the field.'),
}

def start_year(fn):
    s = os.path.basename(fn).replace('season-','').replace('.csv','')
    a = int(s[:2]); return 1900+a if a > 50 else 2000+a

def slabel(y): return f"{y}/{str(y+1)[-2:]}"


def rate(df, *cols):
    """Sum of `cols` over the matches where EVERY column in `cols` is present.

    Returns (total, n_matches) or (None, 0) if the source never recorded them.
    Callers that need several quantities on a common denominator pass every
    column they use in one call, so the resulting rates share one match set and
    their ratios are unbiased.
    """
    if any(c not in df.columns for c in cols):
        return None, 0
    mask = df[list(cols)].notna().all(axis=1)
    n = int(mask.sum())
    if n == 0:
        return None, 0
    return float(df.loc[mask, list(cols)].to_numpy().sum()), n


def goals_over(df, *cols):
    """Total goals scored in the matches where every column in `cols` is present."""
    mask = df[list(cols)].notna().all(axis=1)
    return float((df.loc[mask, 'FTHG'] + df.loc[mask, 'FTAG']).sum()), int(mask.sum())


def build_table(df, use_h2h):
    """Final standings recomputed from results, using this league's tie-break rule."""
    pts = defaultdict(int); gf = defaultdict(int); ga = defaultdict(int)
    # Seed every club at zero first: a side that lost every single match would
    # otherwise never be written to `pts` and would vanish from the table.
    for t in set(df.HomeTeam) | set(df.AwayTeam):
        pts[t] += 0; gf[t] += 0; ga[t] += 0
    results = []
    for h, a, hg, ag in zip(df.HomeTeam, df.AwayTeam, df.FTHG.astype(int), df.FTAG.astype(int)):
        results.append((h, a, hg, ag))
        gf[h] += hg; ga[h] += ag; gf[a] += ag; ga[a] += hg
        if hg > ag:   pts[h] += WIN
        elif hg < ag: pts[a] += WIN
        else:         pts[h] += DRAW; pts[a] += DRAW

    def overall_key(t):
        return (-pts[t], -(gf[t] - ga[t]), -gf[t], t)

    def mini_table(block):
        """Points and goal difference among the given teams only."""
        g = set(block)
        hp = defaultdict(int); hgd = defaultdict(int)
        for h, a, hg, ag in results:
            if h in g and a in g:
                hgd[h] += hg - ag; hgd[a] += ag - hg
                if hg > ag:   hp[h] += WIN
                elif hg < ag: hp[a] += WIN
                else:         hp[h] += DRAW; hp[a] += DRAW
        return {t: (hp[t], hgd[t]) for t in block}

    def resolve(block):
        """Order a set of teams level on points, head-to-head first.

        Recursive: once the mini-table splits the block, any sub-group that is
        still level has its mini-table rebuilt among just those teams — which is
        what the Spanish and Italian regulations actually specify, and what a
        single flat sort gets wrong for three-way and larger ties.
        """
        if len(block) == 1:
            return list(block)
        k = mini_table(block)
        ordered = sorted(block, key=lambda t: (-k[t][0], -k[t][1]))
        out, i = [], 0
        while i < len(ordered):
            j = i
            while j + 1 < len(ordered) and k[ordered[j + 1]] == k[ordered[i]]:
                j += 1
            sub = ordered[i:j + 1]
            if len(sub) == 1:
                out.extend(sub)
            elif len(sub) < len(block):
                out.extend(resolve(sub))          # rebuild the mini-table for the smaller block
            else:
                out.extend(sorted(sub, key=overall_key))   # h2h cannot separate them
            i = j + 1
        return out

    teams = sorted(pts, key=overall_key)
    if use_h2h:
        out, i = [], 0
        while i < len(teams):
            j = i
            while j + 1 < len(teams) and pts[teams[j + 1]] == pts[teams[i]]:
                j += 1
            block = teams[i:j + 1]
            out.extend(resolve(block) if len(block) > 1 else block)
            i = j + 1
        teams = out
    return [(t, pts[t], gf[t], ga[t]) for t in teams]


# ---------------------------------------------------------------- main pass
season_rows, standings_out = [], {}
for lg, name in LEAGUES.items():
    files = sorted(glob.glob(f'{lg}/season-*.csv'), key=start_year)
    if not files:
        sys.exit(f"missing raw CSVs for {lg}/ - clone github.com/datasets/football-datasets first")
    for f in files:
        y = start_year(f)
        if y not in WINDOW: continue
        df = pd.read_csv(f).dropna(subset=['FTHG','FTAG','FTR'])
        m = len(df)
        hw = int((df.FTR == 'H').sum()); dr = int((df.FTR == 'D').sum()); aw = int((df.FTR == 'A').sum())
        home_ppg = (WIN*hw + DRAW*dr)/m; away_ppg = (WIN*aw + DRAW*dr)/m
        rec = {'league':name,'code':CODES[lg],'startY':y,'season':slabel(y),'matches':m,
               'teams':int(len(set(df.HomeTeam) | set(df.AwayTeam))),
               # two distinct home-advantage measures, deliberately kept apart:
               'home_pct':round(hw/m*100,2),'draw_pct':round(dr/m*100,2),'away_pct':round(aw/m*100,2),
               'home_ppg':round(home_ppg,3),'away_ppg':round(away_ppg,3),
               'home_adv':round(home_ppg-away_ppg,3),          # points-per-game gap
               'goals_pg':round(float((df.FTHG+df.FTAG).sum())/m,3),
               'home_gpg':round(float(df.FTHG.sum())/m,3),
               'away_gpg':round(float(df.FTAG.sum())/m,3)}

        # --- shots: shots, on-target and conversion share ONE match set ------
        shots, n_sh = rate(df, 'HS', 'AS')
        sot,   n_st = rate(df, 'HST', 'AST')
        both,  n_bo = rate(df, 'HS', 'AS', 'HST', 'AST')
        if shots is not None:
            rec['shots_pg'] = round(shots/n_sh, 2)
            g_sh, _ = goals_over(df, 'HS', 'AS')
            rec['conversion'] = round(g_sh/shots*100, 2)       # goals per 100 shots, same matches
        if sot is not None:
            rec['sot_pg'] = round(sot/n_st, 2)
        if both is not None:                                   # ratio -> intersection only
            s_i, _ = rate(df, 'HS', 'AS', 'HST', 'AST')        # (kept explicit for clarity)
            mask = df[['HS','AS','HST','AST']].notna().all(axis=1)
            sh_i = float((df.loc[mask,'HS'] + df.loc[mask,'AS']).sum())
            st_i = float((df.loc[mask,'HST'] + df.loc[mask,'AST']).sum())
            rec['sot_pct'] = round(st_i/sh_i*100, 2) if sh_i else None
        rec['sot_suspect'] = bool(rec.get('sot_pct') is not None and rec['sot_pct'] > SOT_RATE_MAX)

        # --- discipline: yellows, reds and total cards share ONE match set ---
        fouls, n_f = rate(df, 'HF', 'AF')
        if fouls is not None:
            rec['fouls_pg'] = round(fouls/n_f, 2)
        cards_mask = None
        if all(c in df.columns for c in ('HY','AY','HR','AR')):
            cards_mask = df[['HY','AY','HR','AR']].notna().all(axis=1)
            n_c = int(cards_mask.sum())
            if n_c:
                yel = float((df.loc[cards_mask,'HY'] + df.loc[cards_mask,'AY']).sum())
                red = float((df.loc[cards_mask,'HR'] + df.loc[cards_mask,'AR']).sum())
                rec['yellows_pg'] = round(yel/n_c, 3)
                rec['reds_pg']    = round(red/n_c, 4)
                rec['cards_pg']   = round((yel+red)/n_c, 3)    # one denominator for both
                rec['n_card_matches'] = n_c
        # fouls per yellow is a ratio -> both columns on the same matches
        if all(c in df.columns for c in ('HF','AF','HY','AY')):
            fy = df[['HF','AF','HY','AY']].notna().all(axis=1)
            if fy.sum():
                f_i = float((df.loc[fy,'HF'] + df.loc[fy,'AF']).sum())
                y_i = float((df.loc[fy,'HY'] + df.loc[fy,'AY']).sum())
                rec['fouls_per_yellow'] = round(f_i/y_i, 2) if y_i else None

        # --- standings -------------------------------------------------------
        table = build_table(df, use_h2h=(lg in H2H_LEAGUES))
        pv = np.array([p for _, p, _, _ in table])
        leader = table[0][0]
        # A season the source never finished cannot be compared on raw points:
        # Ligue 1 2019/20 was abandoned in March 2020 with clubs on 27 or 28
        # games, so its points totals — and therefore its winning margin — are
        # not on the same footing as a completed 38-round season.
        rec['matches_expected'] = rec['teams']*(rec['teams']-1)
        rec['complete'] = bool(m == rec['matches_expected'])
        if not rec['complete']:
            played = defaultdict(int)
            for h, a in zip(df.HomeTeam, df.AwayTeam): played[h] += 1; played[a] += 1
            rec['games_played_range'] = [min(played.values()), max(played.values())]
        official, note = TITLE_OVERRIDES.get((name, slabel(y)), (leader, None))
        rec.update({'champion':leader,                 # finished top on the field
                    'champion_official':official,      # title as it stands in the record books
                    'champ_pts':int(pv[0]),
                    'points_spread':int(pv[0]-pv[-1]),'points_std':round(float(pv.std()),2),
                    'top_share':round(float(pv[0]/pv.sum()*100),2)})
        # Winning margin is only defined for a completed season.
        if rec['complete']:
            rec['title_margin'] = int(pv[0]-pv[1])
        if note: rec['champion_note'] = note
        standings_out.setdefault(name, {})[slabel(y)] = [
            {'team':t,'pts':int(p),'gd':int(gfv-gav),'gf':int(gfv)} for t, p, gfv, gav in table]
        season_rows.append(rec)

# ---- shot-total integrity: does a season break with its own neighbours? -----
by_league = defaultdict(list)
for r in season_rows: by_league[r['league']].append(r)
for name, rows in by_league.items():
    rows.sort(key=lambda r: r['startY'])
    for i, r in enumerate(rows):
        r['shots_suspect'] = False
        if r.get('shots_pg') is None: continue
        nb = [o['shots_pg'] for j, o in enumerate(rows)
              if j != i and abs(o['startY']-r['startY']) <= 3 and o.get('shots_pg') is not None]
        if len(nb) < 3: continue
        med = float(np.median(nb))
        r['shots_dev_pct'] = round((r['shots_pg']/med - 1)*100, 1)
        # Only a season already in the legacy on-target regime is blamed on the
        # provider; otherwise a big deviation just means a broken neighbour is
        # dragging the local median.
        r['shots_suspect'] = bool(r['sot_suspect'] and abs(r['shots_dev_pct']) > SHOTS_DEV_MAX)

sdf = pd.DataFrame(season_rows)
def avg(sub, c):
    if c not in sub: return None
    v = sub[c].dropna(); return round(float(v.mean()), 2) if len(v) else None

# ---- league averages, on a LIKE-FOR-LIKE window ----------------------------
# A league average is only comparable if every league is averaged over the same
# seasons. Detailed stats start in different years (England 2000/01, Spain and
# Italy 2005/06, French fouls only 2007/08) and foul rates drift downwards over
# time, so averaging each league over "whatever it happens to have" silently
# rewards the leagues with the longest history. Measured on its own coverage the
# Bundesliga looks like Europe's most-fouling league; on the window all five
# share it is only third. Every metric below is therefore averaged over the
# seasons in which ALL FIVE leagues have a usable value, and the window actually
# used is published alongside so no caption can claim more than was measured.
SHOT_METRICS = {'shots_pg', 'conversion', 'sot_pg', 'sot_pct'}
SUMMARY_METRICS = ['home_pct','home_adv','goals_pg','cards_pg','fouls_pg','shots_pg',
                   'conversion','fouls_per_yellow','reds_pg','yellows_pg','title_margin',
                   'points_std','top_share']

def usable(r, metric):
    if r.get(metric) is None: return False
    if metric in SHOT_METRICS and r['shots_suspect']: return False
    return True

windows = {}
for metric in SUMMARY_METRICS:
    years = sorted(y for y in WINDOW
                   if all(any(r['startY'] == y and r['league'] == name and usable(r, metric)
                              for r in season_rows) for name in LEAGUES.values()))
    windows[metric] = {'from': slabel(years[0]), 'to': slabel(years[-1]),
                       'n_seasons': len(years), 'years': years,
                       'full': len(years) == len(list(WINDOW))}

league_summary = []
for name in LEAGUES.values():
    rows = [r for r in season_rows if r['league'] == name]
    entry = {'league': name, 'code': rows[0]['code'],
             'home_pct_2000': float(next(r['home_pct'] for r in rows if r['startY'] == 2000)),
             'home_pct_2025': float(next(r['home_pct'] for r in rows if r['startY'] == 2025))}
    for metric in SUMMARY_METRICS:
        yrs = set(windows[metric]['years'])
        vals = [r[metric] for r in rows if r['startY'] in yrs and usable(r, metric)]
        nd = 3 if metric in ('reds_pg',) else 2
        entry[metric] = round(float(np.mean(vals)), nd) if vals else None
    league_summary.append(entry)

# ---- COVID natural experiment, computed rather than asserted ---------------
# 2019/20 is NOT a clean baseline: the Bundesliga and Serie A already finished
# that season behind closed doors, so 2018/19 is the last fully-attended one.
covid = []
for name in LEAGUES.values():
    sub = sdf[sdf.league == name].set_index('startY')
    covid.append({'league':name,'code':sub.code.iloc[0],
        'base_2018':float(sub.loc[2018,'home_pct']),'pre_2019':float(sub.loc[2019,'home_pct']),
        'covid_2020':float(sub.loc[2020,'home_pct']),'after_2021':float(sub.loc[2021,'home_pct']),
        'drop_vs_2018':round(float(sub.loc[2020,'home_pct']-sub.loc[2018,'home_pct']),2),
        'drop_vs_2019':round(float(sub.loc[2020,'home_pct']-sub.loc[2019,'home_pct']),2),
        'adv_base_2018':float(sub.loc[2018,'home_adv']),'adv_covid_2020':float(sub.loc[2020,'home_adv'])})

# ---- official title counts (record books, not raw standings) --------------
titles = defaultdict(lambda: defaultdict(int))
onfield_only = defaultdict(lambda: defaultdict(int))
for r in season_rows:
    if r['champion_official']:
        titles[r['league']][r['champion_official']] += 1
    if r['champion'] != r['champion_official']:
        onfield_only[r['league']][r['champion']] += 1
title_counts = {lg: [{'team':t,'titles':n,'onfield_extra':onfield_only[lg].get(t,0)}
                     for t, n in sorted(c.items(), key=lambda kv: -kv[1])]
                for lg, c in titles.items()}

# ---------------------------------------------------------------- validation
errors, warnings = [], []
EXPECT = {18:306, 20:380}
for r in season_rows:
    tag = f"{r['code']} {r['season']}"
    s = r['home_pct'] + r['draw_pct'] + r['away_pct']
    if abs(s - 100) > 0.05: errors.append(f'{tag}: result shares sum to {s}')
    if not r['complete']:
        warnings.append(f"{tag}: incomplete season - {r['matches']}/{r['matches_expected']} matches, "
                        f"clubs on {r['games_played_range'][0]}-{r['games_played_range'][1]} games "
                        f"(winning margin withheld)")
    if r['teams'] not in EXPECT: warnings.append(f"{tag}: unusual team count {r['teams']}")
    if r.get('title_margin') is not None and r['title_margin'] < 0:
        errors.append(f'{tag}: negative title margin')
    if not (0 <= r['home_pct'] <= 100): errors.append(f'{tag}: home_pct out of range')
    st = standings_out[r['league']][r['season']]
    if sum(x['pts'] for x in st) != int(round(sum(x['pts'] for x in st))):
        errors.append(f'{tag}: non-integer points')
    if st[0]['pts'] != r['champ_pts']: errors.append(f'{tag}: champion points mismatch')
    if r.get('title_margin') is not None and st[0]['pts']-st[1]['pts'] != r['title_margin']:
        errors.append(f'{tag}: title margin mismatch')
    if not r['complete'] and 'title_margin' in r:
        errors.append(f'{tag}: winning margin stored for an incomplete season')
    if len(st) != r['teams']: errors.append(f'{tag}: standings rows != team count')
    if r.get('sot_pct') is not None and not (0 < r['sot_pct'] < 100):
        errors.append(f'{tag}: impossible on-target share')

n_seasons = sdf.startY.nunique()
if len(season_rows) != 130: errors.append(f'{len(season_rows)} league-season rows, expected 130')
if n_seasons != 26: errors.append(f'{n_seasons} distinct seasons, expected 26')

bundle = {'meta':{'window':'2000/01-2025/26','n_seasons':int(n_seasons),
          'n_matches':int(sdf.matches.sum()),'n_rows':len(season_rows),
          'leagues':list(LEAGUES.values()),'codes':CODES,
          'points':{'win':WIN,'draw':DRAW,'loss':0},
          'sot_rate_max':SOT_RATE_MAX,'shots_dev_max':SHOTS_DEV_MAX,
          'h2h_leagues':[LEAGUES[k] for k in H2H_LEAGUES],
          'summary_windows':{k:{kk:vv for kk,vv in v.items() if kk!='years'}
                             for k,v in windows.items()}},
          'seasons':season_rows,'league_summary':league_summary,'covid':covid,
          'title_counts':title_counts,'standings':standings_out}

os.makedirs('data', exist_ok=True)
json.dump(bundle, open('data/big5.json','w'), ensure_ascii=False)
open('data.js','w').write('window.BIG5=' + json.dumps(bundle, ensure_ascii=False) + ';')

print(f"data/big5.json + data.js: {int(sdf.matches.sum())} matches, {len(sdf)} league-seasons, "
      f"{n_seasons} seasons")
print("legacy on-target definition:", sum(r['sot_suspect'] for r in season_rows), "seasons")
print("broken shot totals        :", [f"{r['code']} {r['season']} ({r['shots_dev_pct']:+.0f}%)"
      for r in season_rows if r['shots_suspect']])
print("titles decided off-field  :", [f"{r['code']} {r['season']}" for r in season_rows
      if r['champion'] != r['champion_official']])
if warnings:
    print("\nWARNINGS"); [print('  -', w) for w in warnings]
if errors:
    print("\nVALIDATION FAILED"); [print('  !', e) for e in errors]; sys.exit(1)
print("\nvalidation: all", len(season_rows), "rows passed")
