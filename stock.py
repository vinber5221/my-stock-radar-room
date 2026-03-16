import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import requests

# --- 1. 系統通訊設定 ---
LINE_TOKEN = "hBmawO0uysekx/UhIGUNysagEuHJX7kvgXMkAQHSoOWPjvcVh/4j6oQBLDDuV2s+7iRV4q6cDIh2uy1tHenUb5jk3/GYmmBL32wipEOk5NHPzHNZLnKAU+ogwTsujwSMcpbFeq0bO7XkrjoGM//5TgdB04t89/1O/w1cDnyilFU="
MY_USER_ID = "Ubc4a3750cdea1cb6f51e00a534fd6e1a"

def send_line_notification(message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"to": MY_USER_ID, "messages": [{"type": "text", "text": message}]}
    try:
        requests.post(url, json=payload, headers=headers)
        return True
    except: return False

# --- 2. 數據抓取與計算核心 ---
@st.cache_data(ttl=3600)
def get_processed_data(stock_id, period="日線"):
    dl = DataLoader()
    df = pd.DataFrame()
    start_dt = "2020-01-01"
    
    try:
        if stock_id == "TAIEX":
            # 優先嘗試大盤，失敗則嘗試備援
            df = dl.taiwan_stock_index(index_id="TAIEX", start_date=start_dt)
            if df.empty:
                df = dl.taiwan_stock_daily(stock_id="0050", start_date=start_dt)
        else:
            df = dl.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
    except: return pd.DataFrame()

    if df.empty: return pd.DataFrame()

    # 欄位統整與 OHLC 補齊
    for col in df.columns:
        if col.upper() in ['TAIEX', 'VALUE']:
            df.rename(columns={col: 'close'}, inplace=True)
            break
    df.rename(columns={'max': 'high', 'min': 'low'}, inplace=True)
    for c in ['open', 'high', 'low']:
        if c not in df.columns: df[c] = df['close']

    # 週期重組
    if period != "日線":
        rule_map = {"週線": "W", "月線": "M", "年線": "Y"}
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').resample(rule_map[period]).agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
        }).dropna().reset_index()
    
    # 計算 MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = ema12 - ema26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['Hist'] = (df['DIF'] - df['DEA']) * 2
    return df

# --- 3. 網頁 UI 佈局 ---
st.set_page_config(page_title="Vincent 股市戰情室", layout="wide")
st.title("🏛️ 台股全方位監控中心")

# 側邊欄
st.sidebar.header("📡 系統偵測")
monitor_list = {
    "TAIEX": "台股大盤 (備援0050)", 
    "0050": "元大台灣50", 
    "2330": "台積電", 
    "2317": "鴻海", 
    "2454": "聯發科",
    "2382": "廣達", 
    "3324": "雙鴻"
}

scan_period = st.sidebar.selectbox("巡邏週期", ["月線", "週線", "日線"])
if st.sidebar.button("🔍 開始全標的掃描"):
    progress_bar = st.sidebar.progress(0)
    hits = []
    for i, (sid, name) in enumerate(monitor_list.items()):
        progress_bar.progress((i + 1) / len(monitor_list))
        scan_df = get_processed_data(sid, scan_period)
        if not scan_df.empty and len(scan_df) >= 2:
            last = scan_df.iloc[-1]
            prev = scan_df.iloc[-2]
            if prev['DIF'] < prev['DEA'] and last['DIF'] > last['DEA']:
                hits.append(f"✅ {name}")
    
    progress_bar.empty()
    if hits:
        st.sidebar.success(f"🔥 {scan_period}發現轉折：\n" + "\n".join(hits))
        send_line_notification(f"🔔 Vincent 大師，偵測到{scan_period}金叉：\n" + ", ".join(hits))
    else:
        st.sidebar.info(f"掃描完畢，{scan_period}暫無轉折。")

st.sidebar.divider()
selected_label = st.sidebar.selectbox("🚀 手動觀測標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]
chart_period = st.sidebar.radio("📅 圖表顯示週期", ["日線", "週線", "月線", "年線"], horizontal=True)

# --- 4. 繪製主圖表 ---
df = get_processed_data(target_id, chart_period)

if not df.empty:
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{selected_label}", f"{latest['close']:.2f}", f"{latest['close']-prev['close']:.2f}")
    c2.metric("趨勢診斷", "🔥 金叉翻多" if (prev['DIF'] < prev['DEA'] and latest['DIF'] > latest['DEA']) else "⚪ 趨勢穩定")
    c3.info(f"📅 數據日期：{pd.to_datetime(latest['date']).strftime('%Y-%m-%d')}")

    plot_df = df.tail(100 if chart_period == "日線" else 60)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.4])
    fig.add_trace(go.Candlestick(x=plot_df['date'], open=plot_df['open'], high=plot_df['high'], low=plot_df['low'], close=plot_df['close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['DIF'], name='DIF', line=dict(color='white')), row=2, col=1)
    fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df['DEA'], name='DEA', line=dict(color='yellow')), row=2, col=1)
    fig.add_trace(go.Bar(x=plot_df['date'], y=plot_df['Hist'], name='MACD柱', marker_color=['red' if h >= 0 else 'green' for h in plot_df['Hist']]), row=2, col=1)
    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    # 這裡做了視覺優化，讓大盤抓不到時顯示提示
    st.warning(f"📡 目前 {selected_label} 資料連線較慢，請嘗試切換其他標的或點選右上角 Rerun。")