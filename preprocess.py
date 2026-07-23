#!/usr/bin/env python3
"""
Big Five — data pre-processing pipeline
=======================================
Reads the raw season CSVs from github.com/datasets/football-datasets
(premier-league, la-liga, serie-a, bundesliga, ligue-1) and produces the
single bundle `data/big5.json` consumed by the D3 web app.

Steps
-----
1. Keep the consistent window 2000/01–2025/26 (26 seasons per league).
2. Drop rows without a valid result (FTHG/FTAG/FTR).
3. Compute every league-season metric normalised PER MATCH so leagues with
   different numbers of teams (Bundesliga/Ligue 1 = 18, others = 20) are
   comparable.
4. Detailed stats (shots, fouls, cards) are computed nan-robustly: each rate
   uses only the matches where both the home and away column are present, so a
   metric is simply null in seasons where the source did not record it
   (Spain/Italy/France gained detailed stats in 2005/06–2007/08).
5. Recompute the full final standings from match results (3-1-0), then derive
   champion, title margin (1st−2nd), points spread and points std.

Run:  python3 preprocess.py  (expects the five league folders alongside).
"""
import glob, os, json, pandas as pd, numpy as np
from collections import defaultdict

LEAGUES = {'premier-league':'Premier League','la-liga':'La Liga','serie-a':'Serie A',
           'bundesliga':'Bundesliga','ligue-1':'Ligue 1'}
CODES = {'premier-league':'ENG','la-liga':'ESP','serie-a':'ITA','bundesliga':'GER','ligue-1':'FRA'}
WINDOW = range(2000, 2026)

def start_year(fn):
    s = os.path.basename(fn).replace('season-','').replace('.csv','')
    a = int(s[:2]); return 1900+a if a > 50 else 2000+a
def slabel(y): return f"{y}/{str(y+1)[-2:]}"

def pair_rate(df, hc, ac):
    """Sum of (home+away) over matches where both columns exist; and the count."""
    if hc not in df or ac not in df: return None, 0
    mask = df[hc].notna() & df[ac].notna()
    if mask.sum() == 0: return None, 0
    return float((df.loc[mask, hc] + df.loc[mask, ac]).sum()), int(mask.sum())

season_rows, standings_out = [], {}
for lg, name in LEAGUES.items():
    for f in sorted(glob.glob(f'{lg}/season-*.csv'), key=start_year):
        y = start_year(f)
        if y not in WINDOW: continue
        df = pd.read_csv(f).dropna(subset=['FTHG','FTAG','FTR'])
        m = len(df)
        hw = int((df.FTR=='H').sum()); dr = int((df.FTR=='D').sum()); aw = int((df.FTR=='A').sum())
        home_ppg = (3*hw+dr)/m; away_ppg = (3*aw+dr)/m
        tot_goals = int((df.FTHG+df.FTAG).sum())
        rec = {'league':name,'code':CODES[lg],'startY':y,'season':slabel(y),'matches':m,
               'teams':int(len(set(df.HomeTeam)|set(df.AwayTeam))),
               'home_pct':round(hw/m*100,2),'draw_pct':round(dr/m*100,2),'away_pct':round(aw/m*100,2),
               'home_ppg':round(home_ppg,3),'away_ppg':round(away_ppg,3),'home_adv':round(home_ppg-away_ppg,3),
               'goals_pg':round(tot_goals/m,3),'home_gpg':round(int(df.FTHG.sum())/m,3),
               'away_gpg':round(int(df.FTAG.sum())/m,3)}
        shots, ns = pair_rate(df,'HS','AS'); sot, _ = pair_rate(df,'HST','AST')
        if shots is not None:
            rec['shots_pg'] = round(shots/ns, 2)
            gmask = df['HS'].notna() & df['AS'].notna()
            g_valid = int((df.loc[gmask,'FTHG']+df.loc[gmask,'FTAG']).sum())
            rec['conversion'] = round(g_valid/shots*100, 2)
        if sot is not None:
            n_sot = int((df['HST'].notna()&df['AST'].notna()).sum())
            rec['sot_pg'] = round(sot/n_sot, 2)
            if shots is not None: rec['sot_pct'] = round(sot/shots*100, 2)
        fouls, nf = pair_rate(df,'HF','AF'); yel, ny = pair_rate(df,'HY','AY'); red, nr = pair_rate(df,'HR','AR')
        if fouls is not None: rec['fouls_pg'] = round(fouls/nf, 2)
        if yel is not None: rec['yellows_pg'] = round(yel/ny, 3)
        if red is not None: rec['reds_pg'] = round(red/nr, 4)
        if yel is not None and red is not None: rec['cards_pg'] = round((yel+red)/ny, 3)
        if fouls is not None and yel is not None:
            rec['fouls_per_yellow'] = round(fouls/yel*ny/nf, 2) if yel else None
        # recompute standings from results
        pts=defaultdict(int); gf=defaultdict(int); ga=defaultdict(int)
        for _, r in df.iterrows():
            h,a,hg,ag = r.HomeTeam, r.AwayTeam, int(r.FTHG), int(r.FTAG)
            gf[h]+=hg; ga[h]+=ag; gf[a]+=ag; ga[a]+=hg
            if hg>ag: pts[h]+=3
            elif hg<ag: pts[a]+=3
            else: pts[h]+=1; pts[a]+=1
        table = sorted(pts.items(), key=lambda x:(-x[1], -(gf[x[0]]-ga[x[0]])))
        pv = np.array([p for _,p in table])
        rec.update({'champion':table[0][0],'champ_pts':int(pv[0]),'title_margin':int(pv[0]-pv[1]),
                    'points_spread':int(pv[0]-pv[-1]),'points_std':round(float(pv.std()),2),
                    'top_share':round(float(pv[0]/pv.sum()*100),2)})
        standings_out.setdefault(name,{})[slabel(y)] = [
            {'team':t,'pts':int(p),'gd':int(gf[t]-ga[t])} for t,p in table]
        season_rows.append(rec)

sdf = pd.DataFrame(season_rows)
def avg(sub,c):
    v = sub[c].dropna(); return round(float(v.mean()),2) if len(v) else None
league_summary=[]
for name in LEAGUES.values():
    sub = sdf[sdf.league==name]
    league_summary.append({'league':name,'code':sub.code.iloc[0],
        'home_pct':avg(sub,'home_pct'),'goals_pg':avg(sub,'goals_pg'),'cards_pg':avg(sub,'cards_pg'),
        'fouls_pg':avg(sub,'fouls_pg'),'shots_pg':avg(sub,'shots_pg'),'conversion':avg(sub,'conversion'),
        'fouls_per_yellow':avg(sub,'fouls_per_yellow'),'reds_pg':round(sub['reds_pg'].dropna().mean(),3),
        'home_pct_2000':float(sub[sub.startY==2000].home_pct.iloc[0]),
        'home_pct_2025':float(sub[sub.startY==2025].home_pct.iloc[0]),
        'title_margin':avg(sub,'title_margin'),'points_std':avg(sub,'points_std')})

bundle={'meta':{'window':'2000/01-2025/26','n_seasons':int(sdf.startY.nunique()),
        'n_matches':int(sdf.matches.sum()),'leagues':list(LEAGUES.values()),'codes':CODES},
        'seasons':season_rows,'league_summary':league_summary,'standings':standings_out}
os.makedirs('data', exist_ok=True)
json.dump(bundle, open('data/big5.json','w'), ensure_ascii=False)
# also emit the inlined JS bundle used by index.html (avoids fetch/CORS when opened locally)
open('data.js','w').write('window.BIG5='+json.dumps(bundle, ensure_ascii=False)+';')
print(f"Wrote data/big5.json and data.js: {int(sdf.matches.sum())} matches, {len(sdf)} league-seasons.")
