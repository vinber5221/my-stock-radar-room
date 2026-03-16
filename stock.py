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
def get_financial_data(stock_id):
    if stock_id == "TAIEX": return None
    dl = DataLoader()
    try:
        eps = dl.taiwan_stock_financial_statements(stock_id=stock_id, start_date="2023-01-01")
        eps = eps[eps['type'] == 'EPSTaxAfter']
        rev = dl.taiwan_stock_month_revenue(stock_id=stock_id, start_date="2023-01-01")
        return {"eps": eps, "rev": rev}
    except: return None

# --- 3. UI 介面 ---
st.set_page_config(page_title="Vincent 智能投資戰情室", layout="wide")
st.title("🏛️ 台股全方位監控中心")

# 側邊欄
st.sidebar.header("📡 系統功能")
monitor_list = {"TAIEX": "台股大盤", "0050": "元大台灣50", "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達"}
scan_period = st.sidebar.selectbox("巡邏週期", ["月線", "週線", "日線"])

if st.sidebar.button("🔍 執行金叉掃描"):
    with st.spinner('掃描中...'):
        hits = []
        for sid, name in monitor_list.items():
            sdf = get_stock_data(sid, scan_period)
            if not sdf.empty and len(sdf) >= 2:
                if sdf.iloc[-2]['DIF'] < sdf.iloc[-2]['DEA'] and sdf.iloc[-1]['DIF'] > sdf.iloc[-1]['DEA']:
                    hits.append(name)
        if hits:
            st.sidebar.success(f"發現訊號：{', '.join(hits)}")
            send_line_notification(f"🔔 偵測到{scan_period}金叉：{', '.join(hits)}")
        else: st.sidebar.info("目前暫無訊號")

st.sidebar.divider()
st.sidebar.header("💰 模擬零股試算")
buy_price = st.sidebar.number_input("平均買入成本", min_value=0.0, value=0.0, step=0.1)
buy_shares = st.sidebar.number_input("持有股數 (1張=1000股)", min_value=0, value=0, step=1)

selected_label = st.sidebar.selectbox("🚀 觀測標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]
chart_period = st.sidebar.radio("📅 顯示週期", ["日線", "週線", "月線"], horizontal=True)

# --- 4. 繪製圖表與財報 ---
df = get_stock_data(target_id, chart_period)

if not df.empty:
    latest_price = df.iloc[-1]['close']
    
    c1, c2, c3 = st.columns(3)
    c1.metric(selected_label, f"{latest_price:.2f}")
    
    # 零股損益試算邏輯
    if buy_price > 0 and buy_shares > 0:
        profit = (latest_price - buy_price) * buy_shares
        profit_rate = ((latest_price / buy_price) - 1) * 100
        c2.metric("模擬損益", f"{profit:,.0f} 元", f"{profit_rate:.2f}%")
    else:
        c2.info("請輸入成本與股數")
    
    c3.metric("趨勢狀態", "🔥 金叉翻多" if df.iloc[-1]['DIF'] > df.iloc[-1]['DEA'] else "⚪ 趨勢穩定")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.4])
    fig.add_trace(go.Candlestick(x=df.tail(60)['date'], open=df.tail(60)['open'], high=df.tail(60)['high'], low=df.tail(60)['low'], close=df.tail(60)['close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Bar(x=df.tail(60)['date'], y=df.tail(60)['Hist'], name='MACD柱', marker_color=['red' if h >= 0 else 'green' for h in df.tail(60)['Hist']]), row=2, col=1)
    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

    if target_id != "TAIEX":
        st.subheader(f"📊 {selected_label} 財務精華")
        f_data = get_financial_data(target_id)
        if f_data:
            fc1, fc2 = st.columns(2)
            with fc1:
                st.write("**近四季 EPS (稅後)**")
                eps_df = f_data['eps'].tail(4)[['date', 'value']].copy()
                eps_df.columns = ['季度', 'EPS']
                st.dataframe(eps_df, hide_index=True, use_container_width=True)
            with fc2:
                st.write("**最近月營收 (百萬)**")
                rev_df = f_data['rev'].tail(4)[['date', 'revenue']].copy()
                rev_df['revenue'] = (rev_df['revenue'] / 1000000).round(2)
                rev_df.columns = ['月份', '營收(百萬)']
                st.dataframe(rev_df, hide_index=True, use_container_width=True)
else:
    st.warning("資料載入中...")
