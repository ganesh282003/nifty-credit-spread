import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, time
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings("ignore")

# Try to import nsepython safely
try:
    from nsepython import nse_optionchain_scrapper, nse_eq
except Exception:
    nse_optionchain_scrapper = None
    nse_eq = None

# ------------------------- PAGE CONFIG -------------------------
st.set_page_config(
    page_title="Nifty Credit Spread Algo",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ------------------------- CUSTOM CSS -------------------------
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(180deg, #0B0F19 0%, #111827 100%);
    }
    .main-header {
        font-size: 1.85rem;
        font-weight: 800;
        background: linear-gradient(90deg, #3B82F6, #60A5FA);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.15rem;
    }
    .sub-header {
        text-align: center;
        color: #94A3B8;
        font-size: 0.88rem;
        margin-bottom: 1.4rem;
    }
    .signal-bull {
        background: linear-gradient(135deg, #064E3B, #047857);
        color: #A7F3D0;
        padding: 1.4rem;
        border-radius: 16px;
        text-align: center;
        font-size: 1.25rem;
        font-weight: 700;
        margin: 1.2rem 0;
        line-height: 1.55;
    }
    .signal-bear {
        background: linear-gradient(135deg, #7F1D1D, #B91C1C);
        color: #FECACA;
        padding: 1.4rem;
        border-radius: 16px;
        text-align: center;
        font-size: 1.25rem;
        font-weight: 700;
        margin: 1.2rem 0;
        line-height: 1.55;
    }
    .signal-none {
        background: #1E293B;
        color: #94A3B8;
        padding: 1.3rem;
        border-radius: 16px;
        text-align: center;
        font-size: 1.1rem;
        margin: 1.2rem 0;
        border: 1px solid #334155;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.2rem;
        font-weight: 650;
        font-size: 1.05rem;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------- TELEGRAM -------------------------
def send_telegram(token, chat_id, message):
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=8)
        return r.status_code == 200
    except:
        return False

# ------------------------- DATA FUNCTIONS -------------------------
@st.cache_data(ttl=40)
def get_nifty_spot():
    try:
        if nse_eq is None:
            return None
        data = nse_eq("NIFTY")
        return float(data["lastPrice"])
    except:
        return None

@st.cache_data(ttl=60)
def get_option_chain():
    try:
        if nse_optionchain_scrapper is None:
            return None
        return nse_optionchain_scrapper("NIFTY")
    except:
        return None

def calculate_signals(spot):
    now = datetime.now().time()
    if not (time(10, 15) <= now <= time(14, 15)):
        return None, None, "OUTSIDE TRADING WINDOW (10:15 – 14:15)"

    try:
        chain = get_option_chain()
        if not chain:
            # Fallback values when data is not available
            return 0.48, 0.47, None

        records = chain.get("records", {}).get("data", [])
        ce_oi = sum([x.get("CE", {}).get("openInterest", 0) for x in records[:15]])
        pe_oi = sum([x.get("PE", {}).get("openInterest", 0) for x in records[:15]])
        pcr = pe_oi / ce_oi if ce_oi > 0 else 1.0

        alpha = 0.50 + (pcr - 1.0) * 0.30
        alpha = max(0.05, min(0.95, round(alpha, 3)))
        alpha2 = round(min(0.95, max(0.05, alpha * 0.93 + 0.03)), 3)
        return alpha, alpha2, None
    except:
        return 0.48, 0.47, None

def build_spread(direction, spot):
    if spot is None:
        spot = 22750
    atm = int(round(spot / 50) * 50)
    if direction == "BULL":
        return {"type": "Credit Put Spread", "sell": f"{atm} PE", "buy": f"{atm-400} PE"}
    return {"type": "Credit Call Spread", "sell": f"{atm} CE", "buy": f"{atm+400} CE"}

def create_alpha_gauge(alpha, alpha2):
    fig = make_subplots(rows=1, cols=2, specs=[[{"type": "indicator"}, {"type": "indicator"}]])

    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=alpha,
        title={"text": "Alpha", "font": {"size": 16, "color": "#94A3B8"}},
        gauge={
            "axis": {"range": [0, 1]},
            "bar": {"color": "#3B82F6"},
            "bgcolor": "#1E293B",
            "steps": [
                {"range": [0, 0.2], "color": "#7F1D1D"},
                {"range": [0.2, 0.8], "color": "#1E293B"},
                {"range": [0.8, 1], "color": "#064E3B"}
            ],
        },
        number={"font": {"size": 28, "color": "white"}}
    ), row=1, col=1)

    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=alpha2,
        title={"text": "Alpha2", "font": {"size": 16, "color": "#94A3B8"}},
        gauge={
            "axis": {"range": [0, 1]},
            "bar": {"color": "#8B5CF6"},
            "bgcolor": "#1E293B",
            "steps": [
                {"range": [0, 0.2], "color": "#7F1D1D"},
                {"range": [0.2, 0.8], "color": "#1E293B"},
                {"range": [0.8, 1], "color": "#064E3B"}
            ],
        },
        number={"font": {"size": 28, "color": "white"}}
    ), row=1, col=2)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=220,
        margin=dict(t=30, b=10, l=20, r=20)
    )
    return fig

# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    capital = st.number_input("Capital (₹)", value=100000, step=10000)
    risk_pct = st.slider("Risk per trade (%)", 1.0, 5.0, 2.0, 0.5)

    st.markdown("---")
    st.markdown("### 📱 Telegram Alerts")
    telegram_token = st.text_input("Bot Token", type="password")
    telegram_chat_id = st.text_input("Chat ID")

    st.markdown("---")
    st.caption("Trading window: *10:15 AM – 2:15 PM IST*")

# ------------------------- MAIN UI -------------------------
st.markdown('<div class="main-header">Nifty Credit Spread Algo</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Mean-Reversion Strategy • Alpha + Alpha2</div>', unsafe_allow_html=True)

spot = get_nifty_spot()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Nifty Spot", f"{spot:,.1f}" if spot else "—")
with col2:
    st.metric("Time", datetime.now().strftime("%H:%M"))
with col3:
    st.metric("Capital", f"₹{capital:,.0f}")

st.markdown("")

if st.button("🔄 Check Live Signal", type="primary"):
    with st.spinner("Calculating Alphas..."):
        alpha, alpha2, error = calculate_signals(spot)

        if error:
            st.markdown(f'<div class="signal-none">{error}</div>', unsafe_allow_html=True)
        else:
            st.plotly_chart(create_alpha_gauge(alpha, alpha2), use_container_width=True)

            lots = max(1, int((capital * risk_pct / 100) / 6000))
            signal_text = None

            if alpha > 0.80 and alpha2 > 0.80:
                spread = build_spread("BULL", spot)
                st.markdown(f'''
                <div class="signal-bull">
                    🟢 BULLISH SIGNAL<br>
                    {spread["type"]}<br>
                    Sell <b>{spread["sell"]}</b> • Buy <b>{spread["buy"]}</b>
                </div>
                ''', unsafe_allow_html=True)
                st.success(f"Suggested Lots: *{lots}* | Risk ≈ ₹{int(capital*risk_pct/100):,}")
                signal_text = f"<b>🟢 BULLISH</b>\n{spread['type']}\nSell: {spread['sell']}\nBuy: {spread['buy']}\nLots: {lots}"

            elif alpha < 0.20 and alpha2 < 0.20:
                spread = build_spread("BEAR", spot)
                st.markdown(f'''
                <div class="signal-bear">
                    🔴 BEARISH SIGNAL<br>
                    {spread["type"]}<br>
                    Sell <b>{spread["sell"]}</b> • Buy <b>{spread["buy"]}</b>
                </div>
                ''', unsafe_allow_html=True)
                st.success(f"Suggested Lots: *{lots}* | Risk ≈ ₹{int(capital*risk_pct/100):,}")
                signal_text = f"<b>🔴 BEARISH</b>\n{spread['type']}\nSell: {spread['sell']}\nBuy: {spread['buy']}\nLots: {lots}"

            else:
                st.markdown('''
                <div class="signal-none">
                    ⚪ NO TRADE<br>
                    Alphas are not extreme enough
                </div>
                ''', unsafe_allow_html=True)

            if signal_text and telegram_token and telegram_chat_id:
                if send_telegram(telegram_token, telegram_chat_id, signal_text):
                    st.toast("Telegram alert sent!", icon="✈️")

st.markdown("---")
st.caption("Strategy: Both Alpha & Alpha2 > 0.80 (Bull) or < 0.20 (Bear). Only 10:15–14:15 IST.")
