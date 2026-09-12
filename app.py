import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="NIFTY 100 Swing Lab", page_icon="📈", layout="wide")

st.markdown("""
<style>
.stApp{background:linear-gradient(135deg,#06111f,#0b2038 45%,#102b24);color:#eef7ff}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#071522,#10263b)}
h1{font-size:2.5rem!important;background:linear-gradient(90deg,#00e5ff,#72ff8c,#ffd166);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
div[data-testid="stMetric"]{background:linear-gradient(135deg,#102d49,#123c38);border:1px solid #2b6680;border-radius:16px;padding:12px}
div.stButton>button{border-radius:12px;background:linear-gradient(90deg,#087fdb,#00a88f);color:white;font-weight:800}
</style>
""", unsafe_allow_html=True)

st.title("📈 NIFTY 100 SWING LAB")
st.caption("Strategy-first Indian swing trading research dashboard • Long only • Educational use")

capital=st.sidebar.number_input("Starting capital ₹",10000,10000000,100000,10000)
risk=st.sidebar.selectbox("Risk per trade %",[3,3.5,4,4.5,5],0)
maxpos=st.sidebar.slider("Maximum positions",5,10,10)
hold=st.sidebar.slider("Holding period (months)",1,3,2)
fibtol=st.sidebar.slider("0.50 Fib tolerance %",0,10,5)
buffer=st.sidebar.slider("Breakout buffer %",0.0,5.0,0.5,0.1)

tabs=st.tabs(["🏠 Dashboard","🚀 Top Setups","📊 Multi-Timeframe","🔷 Monthly Trend Line Break","🧪 Backtest","📘 Rules"])

with tabs[0]:
    a,b,c,d=st.columns(4)
    a.metric("Capital",f"₹{capital:,.0f}")
    b.metric("Risk / Trade",f"{risk}%")
    c.metric("Max Positions",maxpos)
    d.metric("Holding",f"{hold} month(s)")
    st.success("Workflow: Monthly → Weekly → Daily → 4H → rank strongest long setups → size from stop distance.")
    st.info("New scanner: monthly trendline breakout + EMA 144 + all-time Fib 0.50 filter.")

with tabs[1]:
    st.subheader("🚀 Top Long Setups")
    st.write("Production version can rank the strongest Indian setups using the common signal engine.")
    st.dataframe(pd.DataFrame({
        "Rank":[1,2,3,4,5],
        "Setup":["Breakout + Retest","Trend Continuation","Structure Break","Momentum Pullback","Range Expansion"],
        "Score":[91,87,84,81,78],
        "R:R":["1:2.5","1:2.2","1:2.0","1:1.9","1:1.8"]}),use_container_width=True,hide_index=True)

with tabs[2]:
    st.subheader("📊 Multi-Timeframe")
    symbol=st.text_input("NSE symbol","RELIANCE").upper().strip()
    if st.button("Load price"):
        x=yf.download(symbol+".NS",period="3y",interval="1d",auto_adjust=False,progress=False)
        if not x.empty:
            if isinstance(x.columns,pd.MultiIndex): x.columns=x.columns.get_level_values(0)
            st.line_chart(x["Close"],height=400)
        else: st.warning("No data returned. Check the NSE symbol.")

with tabs[3]:
    st.subheader("🔷 Monthly Trend Line Break")
    st.markdown("**Rule:** descending monthly trendline → confirmed monthly close breakout → Close > EMA 144 → Close above or around 0.50 Fib.")
    st.warning("Confirmed mode uses the latest completed monthly candle to avoid look-ahead bias.")
    symbols=st.text_area("NSE symbols (one per line)","RELIANCE\nTCS\nINFY\nHDFCBANK\nICICIBANK\nSBIN\nLT\nITC\nAXISBANK\nKOTAKBANK\nMARUTI\nSUNPHARMA\nTATAMOTORS\nTATASTEEL\nADANIENT")
    if st.button("🔍 Scan Monthly Trendline Breaks",type="primary"):
        rows=[]
        for s in [z.strip().upper() for z in symbols.splitlines() if z.strip()]:
            try:
                df=yf.download(s+".NS",period="max",interval="1mo",auto_adjust=False,progress=False)
                if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
                if len(df)<160: continue
                df=df.iloc[:-1].copy()
                close=float(df.Close.iloc[-1])
                ema=float(df.Close.ewm(span=144,adjust=False).mean().iloc[-1])
                hi=float(df.High.max()); lo=float(df.Low.min())
                fib50=hi-(hi-lo)*0.5
                # descending line from two recent confirmed pivot highs
                highs=df.High.reset_index(drop=True)
                piv=[i for i in range(2,len(highs)-2) if highs.iloc[i]>=highs.iloc[i-2:i+3].max()]
                tl=None
                for ia in range(len(piv)-2,-1,-1):
                    for ib in range(len(piv)-1,ia,-1):
                        i,j=piv[ia],piv[ib]
                        if j>i and highs.iloc[j]<highs.iloc[i]:
                            slope=(highs.iloc[j]-highs.iloc[i])/(j-i)
                            intercept=highs.iloc[i]-slope*i
                            tl=(slope,intercept); break
                    if tl: break
                if not tl: continue
                slope,intercept=tl; n=len(df)-1
                line=slope*n+intercept; prev=slope*(n-1)+intercept
                prevclose=float(df.Close.iloc[-2])
                breakout=prevclose<=prev and close>line*(1+buffer/100)
                if breakout and close>ema and close>=fib50*(1-fibtol/100):
                    rows.append({"Symbol":s,"Close":round(close,2),"EMA144":round(ema,2),"Fib 0.50":round(fib50,2),"Fib gap %":round((close/fib50-1)*100,2),"Trendline":round(line,2),"Signal month":str(df.index[-1].date())})
            except Exception: pass
        if rows:
            out=pd.DataFrame(rows).sort_values("Fib gap %",ascending=False)
            st.success(f"{len(out)} confirmed setup(s) found.")
            st.dataframe(out,use_container_width=True,hide_index=True)
            st.download_button("⬇️ Download CSV",out.to_csv(index=False),"monthly_trendline_breaks.csv","text/csv")
        else: st.info("No matches in the sample universe. Replace the sample list with a complete NSE equity universe for a full-market scan.")

with tabs[4]:
    st.subheader("🧪 Backtest Lab")
    st.write("Backtest design: same signal engine as the scanner, next-session entry, risk-based sizing, and walk-forward/out-of-sample validation.")
    st.warning("3–5% risk per trade is aggressive; use portfolio-level risk limits.")

with tabs[5]:
    st.subheader("📘 Strategy Rules")
    st.table(pd.DataFrame([
        ["Direction","Long / BUY only"],["Timeframes","Monthly → Weekly → Daily → 4H"],
        ["Trendline","Descending line through confirmed monthly swing highs"],
        ["Breakout","Completed monthly close above trendline + configurable buffer"],
        ["EMA","Close above Monthly EMA 144"],
        ["Fibonacci","All-time high → all-time low; price above/around 0.50"],
        ["Entry","Next trading day after confirmed signal"],
        ["Risk","3% default, adjustable 3–5%"],["Positions","5–10 maximum"],["Holding","1–3 months"]
    ],columns=["Rule","Setting"]))
