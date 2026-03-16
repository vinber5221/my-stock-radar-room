import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import requests

# --- 1. 系統設定 ---
LINE_TOKEN = "hBmawO0uysekx/UhIGUNysagEuHJX7kvgXMkAQHSoOWPjvcVh/4j6oQBLDDuV2s+7iRV4q6cDIh2uy1tHenUb5jk3/GYmmBL32wipEOk5NHPzHNZLnKAU+ogwTsujwSMcpbFeq0bO7XkrjoGM//5TgdB04t89/1O/w1cDnyilFU="
MY_USER_ID = "Ubc4a3750cdea1cb6f51e00a534fd6e1a"

def send_line_notification(message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"to": MY_USER_ID, "messages": [{"type": "text", "text": message}]}
    try: requests.post(url, json=payload, headers=headers)
    except: pass

# --- 2. 數據核心 ---
@st.cache_data(ttl=3600)
def get_stock_data(stock_id, period="日線"):
    dl = DataLoader()
    start_dt = "2020-01-01"
    try:
        if stock_id == "TAIEX":
            df = dl.taiwan_stock_index(index_id="TAIEX", start_date=start_dt)
            if df is None or df.empty:
                df = dl.taiwan_stock_daily(stock_id="0050", start_date=start_dt)
        else:
            df = dl.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
    except: return pd.DataFrame()

    if df is None or df.empty: return pd.DataFrame()

    for col in df.columns:
        if col.upper() in ['TAIEX', 'VALUE']:
            df.rename(columns={col: 'close'}, inplace=True)
            break
    df.rename(columns={'max': 'high', 'min': 'low'}, inplace=True)
    for c in ['open', 'high', 'low', 'close']:
        if c not in df.columns: df[c] = df.get('close', 0)

    if period != "日線":
        rule_map = {"週線": "W", "月線": "M", "年線": "Y"}
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').resample(rule_map[period]).agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
        }).dropna().reset_index()
    
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = ema12 - ema26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['Hist'] = (df['DIF'] - df['DEA']) * 2
    return df

@st.cache_data(ttl=86400)
def get_financial_summary(stock_id):
    if stock_id == "TAIEX": return None
    dl = DataLoader()
    try:
        eps = dl.taiwan_stock_financial_statements(stock_id=stock_id, start_date="2023-01-01")
        eps = eps[eps['type'] == 'EPSTaxAfter'].tail(4)
        rev = dl.taiwan_stock_month_revenue(stock_id=stock_id, start_date="2024-01-01").tail(4)
        return {"eps": eps, "rev": rev}
    except: return None

# --- 3. UI 介面 ---
st.set_page_config(page_title="Vincent 虛擬基金戰情室", layout="wide")
st.title("🏛️ 1000萬虛擬基金監控中心")

# 側邊欄：基金管理
st.sidebar.header("💼 基金帳戶管理")
initial_capital = st.sidebar.number_input("初始基金總額", min_value=0, value=10000000, step=1000000)

st.sidebar.divider()
st.sidebar.subheader("📍 當前持倉設定")
buy_price = st.sidebar.number_input("平均買入成本", min_value=0.0, value=0.0, step=0.1)
buy_shares = st.sidebar.number_input("持有股數", min_value=0, value=0, step=100)

monitor_list = {"TAIEX": "台股大盤", "0050": "元大台灣50", "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達"}
selected_label = st.sidebar.selectbox("🚀 觀測標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]
chart_period = st.sidebar.radio("📅 顯示週期", ["日線", "週線", "
