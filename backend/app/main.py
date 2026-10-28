from __future__ import annotations
import io, json, os, sqlite3, uuid
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parents[2]; DATA=Path(os.getenv('GOLDLENS_DATA_DIR',ROOT/'data')); DATA.mkdir(parents=True,exist_ok=True); DB=DATA/'goldlens.sqlite3'
CONTRACTS=['GOLDM','GOLDTEN','GOLDGUINEA','GOLDPETAL']; NOTICE='SYNTHETIC DEMO DATA — NOT REAL MCX MARKET PRICES.'
app=FastAPI(title='GoldLens API',version='1.0.0',description='Commodity derivatives research prototype.'); app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['*'],allow_headers=['*'])
def dbopen():
 d=sqlite3.connect(DB); d.row_factory=sqlite3.Row
 d.execute('CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, import_id TEXT, trading_date TEXT, symbol TEXT, expiry_date TEXT, open REAL, high REAL, low REAL, close REAL, settlement_price REAL, volume REAL, open_interest REAL, source TEXT, synthetic INTEGER, original_price REAL, quotation_grams REAL, purity REAL, normalized_price REAL, normalization_method TEXT, spec_status TEXT)')
 d.execute('CREATE TABLE IF NOT EXISTS imports (id TEXT PRIMARY KEY, filename TEXT, imported_at TEXT, source TEXT, accepted INTEGER, rejected INTEGER, warnings INTEGER)'); d.execute('CREATE TABLE IF NOT EXISTS backtests (id TEXT PRIMARY KEY, created_at TEXT, result TEXT)'); return d
class Req(BaseModel):
 pair_a:str='GOLDM'; pair_b:str='GOLDPETAL'; lookback:int=Field(20,ge=5,le=250); entry_z:float=Field(2,gt=0,le=8); exit_z:float=Field(.5,ge=0,le=5); max_expiry_mismatch:int=Field(45,ge=0,le=365); min_volume:float=Field(0,ge=0); start:str|None=None; end:str|None=None
def seed():
 d=dbopen()
 if d.execute('SELECT COUNT(*) FROM records').fetchone()[0]: d.close(); return
 rng=np.random.default_rng(73); dates=pd.bdate_range(end=pd.Timestamp.today().normalize()-pd.Timedelta(days=1),periods=150); base=7200.; rows=[]
 for i,t in enumerate(dates):
  base+=rng.normal(0,22); shock=190*np.exp(-((i-112)/5)**2)
  for j,s in enumerate(CONTRACTS):
   p=base+[0,18,-12,0][j]+(shock if s=='GOLDPETAL' else 0)+rng.normal(0,6); exp=(t+pd.Timedelta(days=35+j*2)).date().isoformat()
   rows.append((None,t.date().isoformat(),s,exp,p,p+10,p-10,p,p,float(100+rng.integers(0,800)),float(2000+rng.integers(0,9000)),NOTICE,1,p,1.,1.,p,'P / 1 g; purity adjustment not applied','unverified demo unit; no official specification asserted'))
 d.executemany('INSERT INTO records (import_id,trading_date,symbol,expiry_date,open,high,low,close,settlement_price,volume,open_interest,source,synthetic,original_price,quotation_grams,purity,normalized_price,normalization_method,spec_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',rows); d.execute('INSERT INTO imports VALUES (?,?,?,?,?,?,?)',(str(uuid.uuid4()),'synthetic-demo','now','synthetic',len(rows),0,len(rows))); d.commit();d.close()
def frame():
 d=dbopen(); x=pd.read_sql_query('SELECT * FROM records ORDER BY trading_date,symbol',d);d.close()
 if len(x): x['trading_date']=pd.to_datetime(x.trading_date)
 return x
@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/demo/load')
def demo(): seed(); return summary()
@app.get('/api/data/summary')
def summary():
 x=frame(); d=dbopen(); imports=[dict(r) for r in d.execute('SELECT * FROM imports ORDER BY imported_at DESC')];d.close()
 return {'rows':len(x),'contracts':sorted(x.symbol.unique().tolist()) if len(x) else [],'latest_date':x.trading_date.max().date().isoformat() if len(x) else None,'sources':sorted(x.source.unique().tolist()) if len(x) else [],'synthetic_rows':int(x.synthetic.sum()) if len(x) else 0,'validation_pass_rate':100 if len(x) else None,'imports':imports}
@app.get('/api/market/contracts')
def contracts(): return {'contracts':CONTRACTS}
@app.get('/api/data/records')
def records(limit:int=Query(500,ge=1,le=5000),offset:int=Query(0,ge=0),symbol:str|None=None):
 d=dbopen(); q='SELECT * FROM records'; a=[]
 if symbol: q+=' WHERE symbol=?';a.append(symbol)
 out=[dict(r) for r in d.execute(q+' ORDER BY trading_date DESC LIMIT ? OFFSET ?',a+[limit,offset])];d.close();return {'records':out,'limit':limit,'offset':offset}
def val(x): return float(x) if pd.notna(x) else None
@app.post('/api/data/upload')
async def upload(file:UploadFile=File(...)):
 if not file.filename or not file.filename.lower().endswith('.csv'): raise HTTPException(400,'Upload a .csv file.')
 raw=await file.read()
 if len(raw)>20_000_000: raise HTTPException(413,'CSV exceeds the 20 MB limit.')
 try: x=pd.read_csv(io.BytesIO(raw))
 except Exception as e: raise HTTPException(400,f'Could not parse CSV: {e}')
 if x.empty: raise HTTPException(400,'CSV contains no data rows.')
 aliases={'date':'trading_date','trade_date':'trading_date','contract':'symbol','expiry':'expiry_date','settle':'settlement_price','settlement':'settlement_price','price':'close','qty':'volume','oi':'open_interest'};x.columns=[aliases.get(str(c).strip().lower(),str(c).strip().lower()) for c in x.columns]
 if not {'trading_date','symbol'}.issubset(x.columns): raise HTTPException(422,'Required columns: trading_date, symbol. Provide close or settlement_price.')
 if 'settlement_price' not in x and 'close' in x:x['settlement_price']=x.close
 if 'settlement_price' not in x:raise HTTPException(422,'Provide settlement_price or close.')
 for c in ['open','high','low','close','settlement_price','volume','open_interest','quotation_grams','purity']:
  if c not in x:x[c]=np.nan
  x[c]=pd.to_numeric(x[c],errors='coerce')
 x['symbol']=x.symbol.astype(str).str.upper().str.strip().str.replace(' ','',regex=False);x['trading_date']=pd.to_datetime(x.trading_date,errors='coerce');x['expiry_date']=pd.to_datetime(x.get('expiry_date',pd.Series([None]*len(x))),errors='coerce').dt.strftime('%Y-%m-%d')
 bad=x.trading_date.isna()|~x.symbol.isin(CONTRACTS)|x.settlement_price.isna()|(x.settlement_price<=0); rejected=int(bad.sum());x=x.loc[~bad].copy()
 dup=x.duplicated(['trading_date','symbol','expiry_date']);rejected+=int(dup.sum());x=x.loc[~dup]
 if x.empty:raise HTTPException(422,'No valid rows. Check contract symbols, dates, and positive prices.')
 iid=str(uuid.uuid4());d=dbopen();rows=[]
 for _,r in x.iterrows():
  q=float(r.quotation_grams) if pd.notna(r.quotation_grams) and r.quotation_grams>0 else 1.; f=float(r.purity) if pd.notna(r.purity) and 0<r.purity<=1 else 1.;p=float(r.settlement_price)
  rows.append((iid,r.trading_date.date().isoformat(),r.symbol,r.expiry_date,*[val(r[c]) for c in ['open','high','low','close','settlement_price','volume','open_interest']],f'uploaded:{file.filename}',0,p,q,f,p/q*f,'P / quotation_grams × purity','user supplied; contract specification unverified'))
 d.executemany('INSERT INTO records (import_id,trading_date,symbol,expiry_date,open,high,low,close,settlement_price,volume,open_interest,source,synthetic,original_price,quotation_grams,purity,normalized_price,normalization_method,spec_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',rows);warnings=int(x.expiry_date.isna().sum()+x.volume.isna().sum()+x.quotation_grams.isna().sum()+x.purity.isna().sum());d.execute('INSERT INTO imports VALUES (?,?,?,?,?,?,?)',(iid,file.filename,datetime.utcnow().isoformat(),'uploaded',len(rows),rejected,warnings));d.commit();d.close()
 return {'import_id':iid,'accepted':len(rows),'rejected':rejected,'warnings':warnings,'warning':'Absent quotation_grams and purity default to 1.0. User-supplied specifications remain unverified.'}
def analyze(r):
 x=frame()
 if not len(x):return {'observations':[],'alerts':[],'message':'No records. Load demo data or upload CSV.'}
 x=x[x.symbol.isin([r.pair_a,r.pair_b])].copy()
 if r.start:x=x[x.trading_date>=pd.Timestamp(r.start)]
 if r.end:x=x[x.trading_date<=pd.Timestamp(r.end)]
 x['normalized_price']=x.settlement_price.fillna(x.close)/x.quotation_grams*x.purity
 p=x.pivot_table(index='trading_date',columns='symbol',values='normalized_price',aggfunc='last').dropna(subset=[r.pair_a,r.pair_b])
 for sym,suffix in [(r.pair_a,'a'),(r.pair_b,'b')]:
  y=x[x.symbol==sym].set_index('trading_date');p['expiry_'+suffix]=y.expiry_date.reindex(p.index);p['volume_'+suffix]=y.volume.reindex(p.index)
 p['expiry_gap']=(pd.to_datetime(p.expiry_a)-pd.to_datetime(p.expiry_b)).abs().dt.days;p['eligible']=(p.expiry_gap<=r.max_expiry_mismatch)&(p.volume_a.fillna(0)>=r.min_volume)&(p.volume_b.fillna(0)>=r.min_volume);p['spread']=p[r.pair_a]-p[r.pair_b];p['pct_spread']=p.spread/p[r.pair_b]*100
 prior=p.spread.shift(1);p['mean']=prior.rolling(r.lookback,min_periods=r.lookback).mean();p['std']=prior.rolling(r.lookback,min_periods=r.lookback).std(ddof=0);p['zscore']=(p.spread-p['mean'])/p['std'].replace(0,np.nan);p['anomaly']=p.eligible&p.zscore.abs().ge(r.entry_z)
 obs=[]
 for dt,row in p.iterrows():
  item={'date':dt.date().isoformat()}
  for k,v in row.items():item[k]=None if pd.isna(v) else (v.item() if isinstance(v,np.generic) else v)
  obs.append(item)
 alerts=[{'date':a['date'],'pair':[r.pair_a,r.pair_b],'price_a':a[r.pair_a],'price_b':a[r.pair_b],'expiry_a':a['expiry_a'],'expiry_b':a['expiry_b'],'spread':a['spread'],'mean':a['mean'],'zscore':a['zscore'],'volume_a':a['volume_a'],'volume_b':a['volume_b'],'explanation':'Research candidate: matched date and configured expiry/liquidity filters passed; rolling z-score exceeded threshold. Settlement prices and statistical anomalies do not establish executable opportunity.'} for a in obs if a.get('anomaly')]
 return {'pair':[r.pair_a,r.pair_b],'observations':obs,'alerts':alerts,'count':len(obs),'valid_comparisons':sum(bool(a['eligible']) for a in obs),'method':'Normalized = settlement/quotation grams × purity. Rolling baseline uses prior observations only.','source_notice':'Demo rows are synthetic; imported rows are user supplied and not independently authenticated.'}
@app.post('/api/analysis/spreads')
def spreads(r:Req):
 if r.pair_a==r.pair_b or r.pair_a not in CONTRACTS or r.pair_b not in CONTRACTS:raise HTTPException(422,'Choose two different supported contracts.')
 return analyze(r)
@app.post('/api/backtest/run')
def backtest(r:Req,cost_bps:float=Query(10,ge=0,le=1000),slippage_bps:float=Query(5,ge=0,le=1000),max_holding:int=Query(15,ge=1,le=250)):
 obs=analyze(r)['observations'];trades=[];side=0;entry=None;held=0;equity=0.;curve=[];rt=(cost_bps+slippage_bps)*2/10000
 for i,a in enumerate(obs):
  z=a.get('zscore');sp=a.get('spread')
  if not a.get('eligible') or z is None or sp is None:continue
  if side==0 and abs(z)>=r.entry_z:side=-1 if z>0 else 1;entry=i;held=0
  elif side:
   held+=1
   if abs(z)<=r.exit_z or held>=max_holding:
    gross=side*(sp-obs[entry]['spread']);cost=abs(obs[entry]['spread'])*rt;net=gross-cost;equity+=net;trades.append({'entry_date':obs[entry]['date'],'exit_date':a['date'],'gross_pnl_spread_units':gross,'estimated_cost_spread_units':cost,'net_pnl_spread_units':net,'holding_observations':held});side=0;entry=None
  curve.append({'date':a['date'],'equity_spread_units':equity})
 pnls=[t['net_pnl_spread_units'] for t in trades]; peak=0;dd=0
 for value in np.cumsum(pnls):peak=max(peak,value);dd=min(dd,value-peak)
 out={'id':str(uuid.uuid4()),'parameters':{'pair':[r.pair_a,r.pair_b],'lookback':r.lookback,'entry_z':r.entry_z,'exit_z':r.exit_z,'max_holding':max_holding,'round_trip_cost_bps':(cost_bps+slippage_bps)*2},'completed_trades':len(trades),'gross_pnl_spread_units':sum(t['gross_pnl_spread_units'] for t in trades),'estimated_cost_spread_units':sum(t['estimated_cost_spread_units'] for t in trades),'net_pnl_spread_units':sum(pnls),'win_rate':sum(v>0 for v in pnls)/len(pnls) if pnls else None,'max_drawdown_spread_units':dd if trades else None,'trades':trades,'equity_curve':curve,'incomplete_trade':{'entry_date':obs[entry]['date'],'status':'open at end; excluded'} if side and entry is not None else None,'out_of_sample':'Not computed; full sample is exploratory only.','limitations':'Settlement is not a guaranteed fill. P&L is in spread-price units; cost/slippage modeled as basis points of entry spread; no contract multipliers or hedge ratios.'}
 d=dbopen();d.execute('INSERT INTO backtests VALUES (?,?,?)',(out['id'],datetime.utcnow().isoformat(),json.dumps(out)));d.commit();d.close();return out
@app.get('/api/backtest/{bid}')
def get_backtest(bid:str):
 d=dbopen();r=d.execute('SELECT result FROM backtests WHERE id=?',(bid,)).fetchone();d.close()
 if not r:raise HTTPException(404,'Backtest not found.')
 return json.loads(r[0])
@app.get('/api/export/csv')
def export():
 x=frame()
 if x.empty:raise HTTPException(404,'No data to export.')
 return StreamingResponse(iter([x.to_csv(index=False)]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=goldlens-records.csv'})
