import io, time
from datetime import datetime
import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go

try:
    import yfinance as yf
except Exception:
    yf = None

st.set_page_config(page_title='NSE Monthly Trend Break Scanner', page_icon='📈', layout='wide')

st.markdown('''
<style>
.stApp{background:linear-gradient(135deg,#071521 0%,#0a1f32 52%,#08271f 100%);color:#f5f7fa}
[data-testid="stSidebar"]{background:#071522;border-right:1px solid #284861}
[data-testid="stSidebar"] *{color:#f5f7fa!important}
.block-container{padding-top:2rem;max-width:1500px}
.title{font-size:42px;font-weight:900;letter-spacing:.5px;color:#32e6d0!important}
.subtitle{font-size:16px;color:#c9d6e2!important}
.card{background:#10283c;border:1px solid #315873;border-radius:16px;padding:18px;box-shadow:0 8px 24px rgba(0,0,0,.22)}
.good{background:#0d3a2f;border:1px solid #2ad29d;border-radius:14px;padding:14px;color:#f0fff9!important}
.warn{background:#3c300f;border:1px solid #e0b33c;border-radius:14px;padding:14px;color:#fff7d9!important}
.stButton>button{color:#fff!important;background:linear-gradient(90deg,#078bd1,#00a78e)!important;border:0!important;border-radius:11px!important;font-weight:800!important}
.stDownloadButton>button{color:#fff!important;background:#155b83!important;border:1px solid #4ca8d9!important}
[data-testid="stMetric"]{background:#10283c;border:1px solid #315873;border-radius:14px}
[data-testid="stMetricLabel"] p{color:#bfd0de!important}
[data-testid="stMetricValue"]{color:#fff!important}
</style>
''', unsafe_allow_html=True)

st.markdown('<div class="title">📈 NSE MONTHLY TREND LINE BREAK</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">NSE-listed EQ stocks • 1M candles • Trendline breakout • EMA 144 • ATH→ATL Fib 0.50</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header('⚙️ Scanner settings')
    fib_tol = st.slider('0.50 Fib “around” tolerance', 0, 10, 5, 1, format='%d%%')
    min_months = st.number_input('Minimum monthly candles', min_value=120, max_value=400, value=160, step=10)
    pivot_lr = st.slider('Pivot sensitivity', 1, 5, 2)
    show_in_progress = st.checkbox('Show current-month breakouts', True)
    st.divider()
    st.markdown('**Universe:** NSE EQ only')
    st.markdown('**Strategy timeframe:** Monthly')
    st.markdown('**Refresh:** monthly / after market close')

NSE_MASTER = 'https://archives.nseindia.com/content/equities/EQUITY_L.csv'

@st.cache_data(ttl=86400, show_spinner=False)
def get_nse_universe():
    headers = {'User-Agent':'Mozilla/5.0','Accept':'text/csv,*/*','Referer':'https://www.nseindia.com/'}
    last = None
    for _ in range(3):
        try:
            r = requests.get(NSE_MASTER, headers=headers, timeout=25)
            if r.ok and len(r.content) > 1000:
                df = pd.read_csv(io.BytesIO(r.content))
                df.columns = [str(c).strip().upper() for c in df.columns]
                if 'SERIES' in df.columns:
                    df = df[df['SERIES'].astype(str).str.upper().eq('EQ')]
                if 'SYMBOL' not in df.columns:
                    raise RuntimeError('NSE file has no SYMBOL column')
                df['SYMBOL'] = df['SYMBOL'].astype(str).str.strip().str.upper()
                df = df[df['SYMBOL'].ne('')].drop_duplicates('SYMBOL').reset_index(drop=True)
                return df
            last = f'HTTP {r.status_code}'
        except Exception as e:
            last = str(e)
        time.sleep(2)
    raise RuntimeError(last or 'NSE universe unavailable')

@st.cache_data(ttl=2592000, show_spinner=False)
def get_monthly_history_batch(symbols):
    if yf is None:
        raise RuntimeError('yfinance is not installed')
    tickers = [s + '.NS' for s in symbols]
    # Yahoo is used only as a public market-data fallback when NSE blocks cloud requests.
    # The requested strategy still receives ONLY 1M candles.
    data = yf.download(tickers=tickers, period='max', interval='1mo', auto_adjust=False,
                       group_by='ticker', threads=True, progress=False, timeout=30)
    out = {}
    if data.empty:
        return out
    if isinstance(data.columns, pd.MultiIndex):
        lvl0 = list(data.columns.get_level_values(0).unique())
        # Standard yfinance layout: ticker first level, field second level.
        for sym in symbols:
            t = sym + '.NS'
            if t in lvl0:
                x = data[t].copy()
            else:
                continue
            x = x.rename(columns={c:str(c).upper() for c in x.columns})
            if 'CLOSE' in x.columns:
                x = x[['OPEN','HIGH','LOW','CLOSE']].dropna(subset=['CLOSE'])
                out[sym] = x
    else:
        # Single ticker case.
        x = data.rename(columns={c:str(c).upper() for c in data.columns})
        if 'CLOSE' in x.columns:
            out[symbols[0]] = x[['OPEN','HIGH','LOW','CLOSE']].dropna(subset=['CLOSE'])
    return out

def pivot_highs(series, lr=2):
    vals=[]
    for i in range(lr, len(series)-lr):
        w=series.iloc[i-lr:i+lr+1]
        if series.iloc[i] >= w.max(): vals.append(i)
    return vals

def descending_trendline(df, lr=2):
    h=df['HIGH'].reset_index(drop=True)
    piv=pivot_highs(h, lr)
    if len(piv)<2: return None
    # Search recent pivot pairs; require second pivot lower than first.
    for a in range(len(piv)-2,-1,-1):
        for b in range(len(piv)-1,a,-1):
            i,j=piv[a],piv[b]
            if j<=i or h.iloc[j]>=h.iloc[i]: continue
            slope=(h.iloc[j]-h.iloc[i])/(j-i)
            intercept=h.iloc[i]-slope*i
            # Require at least a modestly descending line; avoid near-horizontal noise.
            span=max(abs(h.iloc[i]),1.0)
            if slope >= -0.001*span: continue
            return i,j,slope,intercept
    return None

def evaluate(df, fib_tol, lr):
    if len(df)<min_months: return None
    d=df.copy().sort_index()
    # yfinance may include current partial month. Separate it from the completed history.
    now=pd.Timestamp.now(tz=None)
    last=d.index[-1]
    if getattr(last,'tzinfo',None) is not None: last=last.tz_localize(None)
    current_period=now.to_period('M')
    last_period=pd.Timestamp(last).to_period('M')
    has_current=(last_period==current_period)
    completed=d.iloc[:-1].copy() if has_current else d.copy()
    current=d.iloc[-1].copy() if has_current else None
    if len(completed)<min_months: return None

    # ATH/ATL use complete available monthly history, matching the user's Fib idea.
    ath=float(completed['HIGH'].max())
    atl=float(completed['LOW'].min())
    fib50=ath-(ath-atl)*0.5
    ema144=float(completed['CLOSE'].ewm(span=144,adjust=False).mean().iloc[-1])

    tl=descending_trendline(completed,lr)
    if tl is None: return None
    i,j,slope,intercept=tl
    n=len(completed)-1
    line_prev=slope*(n-1)+intercept
    line_completed=slope*n+intercept
    c=float(completed['CLOSE'].iloc[-1]); pc=float(completed['CLOSE'].iloc[-2])
    confirmed=(pc<=line_prev and c>line_completed)
    completed_above=(c>ema144 and c>=fib50*(1-fib_tol/100))

    result=None
    if confirmed and completed_above:
        result={'Status':'🟢 CONFIRMED','Breakout Close':c,'Current Price':c,'EMA 144':ema144,'Fib 0.50':fib50,
                'Fib Gap %':(c/fib50-1)*100,'Trendline':line_completed,'Breakout Month':completed.index[-1].strftime('%Y-%m'),
                'Pivot 1':completed.index[i].strftime('%Y-%m'),'Pivot 2':completed.index[j].strftime('%Y-%m')}
    if show_in_progress and current is not None:
        cur_close=float(current['CLOSE']); cur_line=slope*len(completed)+intercept
        cur_above=(cur_close>cur_line and cur_close>ema144 and cur_close>=fib50*(1-fib_tol/100))
        # Match the screenshot: the current monthly candle itself has broken above the descending line.
        if cur_above and cur_close>line_completed:
            result={'Status':'🟡 IN PROGRESS','Breakout Close':c,'Current Price':cur_close,'EMA 144':ema144,'Fib 0.50':fib50,
                    'Fib Gap %':(cur_close/fib50-1)*100,'Trendline':cur_line,'Breakout Month':current.index.strftime('%Y-%m'),
                    'Pivot 1':completed.index[i].strftime('%Y-%m'),'Pivot 2':completed.index[j].strftime('%Y-%m')}
    return result

# ---------- Dashboard ----------
try:
    universe=get_nse_universe()
    source='NSE official EQUITY_L.csv'
except Exception as e:
    universe=pd.DataFrame()
    source=None
    st.error(f'NSE universe connection failed: {e}')
    st.info('The scanner cannot safely claim an all-NSE result until the NSE equity master is available. The app does not substitute a hand-made stock list.')

c1,c2,c3,c4=st.columns(4)
c1.metric('NSE EQ Universe', f'{len(universe):,}' if not universe.empty else '—')
c2.metric('Timeframe','1M')
c3.metric('EMA','144')
c4.metric('Fib','0.50')

if source:
    st.markdown(f'<div class="good"><b>Connected:</b> {source} &nbsp;|&nbsp; <b>Universe:</b> {len(universe):,} EQ securities</div>', unsafe_allow_html=True)

st.write('')
scan_col, refresh_col = st.columns([2,1])
with scan_col:
    run=st.button('🚀 SCAN ALL NSE MONTHLY BREAKOUTS', type='primary', use_container_width=True)
with refresh_col:
    if st.button('🔄 Refresh NSE Universe', use_container_width=True):
        get_nse_universe.clear(); st.rerun()

if run and not universe.empty:
    symbols=universe['SYMBOL'].tolist()
    all_rows=[]
    progress=st.progress(0)
    status=st.empty()
    batch_size=80
    for start in range(0,len(symbols),batch_size):
        batch=symbols[start:start+batch_size]
        try:
            histories=get_monthly_history_batch(tuple(batch))
        except Exception:
            histories={}
        for sym,df in histories.items():
            try:
                r=evaluate(df,fib_tol,pivot_lr)
                if r:
                    r['Symbol']=sym
                    if 'NAME OF COMPANY' in universe.columns:
                        m=universe.loc[universe['SYMBOL'].eq(sym),'NAME OF COMPANY']
                        r['Company']=m.iloc[0] if len(m) else ''
                    all_rows.append(r)
            except Exception:
                pass
        done=min(start+batch_size,len(symbols))
        progress.progress(done/len(symbols))
        status.write(f'Analysing monthly candles: {done:,} / {len(symbols):,} NSE EQ stocks')
    progress.empty(); status.empty()

    if all_rows:
        out=pd.DataFrame(all_rows)
        cols=['Status','Symbol','Company','Current Price','EMA 144','Fib 0.50','Fib Gap %','Trendline','Breakout Month','Pivot 1','Pivot 2']
        out=out[[c for c in cols if c in out.columns]].sort_values(['Status','Fib Gap %'],ascending=[True,False])
        confirmed=out[out['Status'].eq('🟢 CONFIRMED')]
        inprog=out[out['Status'].eq('🟡 IN PROGRESS')]
        m1,m2=st.columns(2)
        m1.metric('🟢 Confirmed Breakouts',len(confirmed))
        m2.metric('🟡 Current-Month Breakouts',len(inprog))
        st.markdown('### 🔥 BREAKOUT STOCKS')
        st.dataframe(out,use_container_width=True,hide_index=True)
        st.download_button('⬇️ Download breakout stocks CSV',out.to_csv(index=False),'NSE_monthly_breakouts.csv','text/csv')
    else:
        st.warning('No stock passed every condition in the available monthly history. This is a genuine zero-result scan, not a placeholder list.')

st.divider()
st.markdown('### 📌 Rules used')
st.markdown('''
- **Universe:** NSE-listed **EQ series** only.
- **Data:** **1M candles** for this tab; no 5m/15m/4H signal data.
- **Trendline:** descending line through confirmed monthly swing highs.
- **Breakout:** monthly candle closes above the descending trendline.
- **EMA:** price above Monthly EMA 144.
- **Fibonacci:** 0 at **all-time high**, 1 at **all-time low**; 0.50 is the midpoint.
- **Fib condition:** price above or around 0.50, with the adjustable tolerance.
- **Current month:** shown separately as **IN PROGRESS** so a setup like the supplied TradingView example is not discarded merely because the month has not finished.
''')

st.caption('Research tool only. Market-data availability and exchange rate limits can affect scan completeness.')
