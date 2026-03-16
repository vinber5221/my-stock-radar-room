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
chart_period = st.sidebar.radio("📅 顯示週期", ["日線", "週線", "月線"], horizontal=True)

# --- 4. 數據計算與顯示 ---
df = get_stock_data(target_id, chart_period)

if not df.empty:
    latest_price = df.iloc[-1]['close']
    
    # 基金損益核心邏輯
    current_stock_value = latest_price * buy_shares
    cost_basis = buy_price * buy_shares
    remaining_cash = initial_capital - cost_basis
    total_assets = remaining_cash + current_stock_value
    total_profit = total_assets - initial_capital
    profit_pct = (total_profit / initial_capital) * 100 if initial_capital > 0 else 0

    # 頂部三大指標
    m1, m2, m3 = st.columns(3)
    m1.metric("基金總資產 (淨值)", f"${total_assets:,.0f}", f"{profit_pct:.2f}%")
    m2.metric("可用現金餘額", f"${remaining_cash:,.0f}")
    m3.metric(f"{selected_label} 損益", f"${(current_stock_value - cost_basis):,.0f}")

    # K線與指標圖
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.4])
    plot_df = df.tail(60)
    fig.add_trace(go.Candlestick(x=plot_df['date'], open=plot_df['open'], high=plot_df['high'], low=plot_df['low'], close=plot_df['close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Bar(x=plot_df['date'], y=plot_df['Hist'], name='MACD柱', marker_color=['red' if h >= 0 else 'green' for h in plot_df['Hist']]), row=2, col=1)
    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=20, b=20, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)

    # 財報區域
    if target_id != "TAIEX":
        st.subheader(f"📊 {selected_label} 財務精華")
        f_info = get_financial_summary(target_id)
        if f_info:
            fc1, fc2 = st.columns(2)
            with fc1:
                st.write("**近四季 EPS (稅後)**")
                st.table(f_info['eps'][['date', 'value']].rename(columns={'date':'季度', 'value':'EPS'}))
            with fc2:
                st.write("**近四月營收 (百萬)**")
                rev_show = f_info['rev'][['date', 'revenue']].copy()
                rev_show['revenue'] = (rev_show['revenue'] / 1000000).round(0)
                st.table(rev_show.rename(columns={'date':'月份', 'revenue':'營收(M)'}))
else:
    st.info("數據載入中，請稍候...")
