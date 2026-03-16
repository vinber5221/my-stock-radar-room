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
def get_comprehensive_finance(stock_id):
    if stock_id == "TAIEX": return None
    dl = DataLoader()
    try:
        # 1. 抓取 EPS 與獲利指標
        fin_state = dl.taiwan_stock_financial_statements(stock_id=stock_id, start_date="2023-01-01")
        # 2. 抓取財務分析指標 (ROE, 毛利率, 營益率)
        fin_analysis = dl.taiwan_stock_financial_analysis(stock_id=stock_id, start_date="2023-01-01")
        return {"state": fin_state, "analysis": fin_analysis}
    except: return None

# --- 3. UI 介面 ---
st.set_page_config(page_title="Vincent 1000萬全功能戰情室", layout="wide")
st.title("🏛️ 1000萬虛擬基金監控中心")

# 側邊欄
st.sidebar.header("💼 基金帳戶管理")
initial_capital = st.sidebar.number_input("初始基金總額", min_value=0, value=10000000)
buy_price = st.sidebar.number_input("平均買入成本", min_value=0.0, value=0.0, step=0.1)
buy_shares = st.sidebar.number_input("持有股數 (1張=1000股)", min_value=0, value=0, step=100)

monitor_list = {"TAIEX": "台股大盤", "0050": "元大台灣50", "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達"}
selected_label = st.sidebar.selectbox("🚀 觀測標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]
chart_period = st.sidebar.radio("📅 顯示週期", ["日線", "週線", "月線"], horizontal=True)

# --- 4. 數據計算與顯示 ---
df = get_stock_data(target_id, chart_period)

if not df.empty:
    latest_price = df.iloc[-1]['close']
    
    # 基金邏輯
    current_stock_value = latest_price * buy_shares
    remaining_cash = initial_capital - (buy_price * buy_shares)
    total_assets = remaining_cash + current_stock_value
    profit_pct = ((total_assets / initial_capital) - 1) * 100 if initial_capital > 0 else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("基金總資產", f"${total_assets:,.0f}", f"{profit_pct:.2f}%")
    m2.metric("可用現金餘額", f"${remaining_cash:,.0f}")
    m3.metric(f"{selected_label} 即時報價", f"${latest_price:.2f}", "🔥 金叉" if df.iloc[-1]['DIF'] > df.iloc[-1]['DEA'] else "穩定")

    # 圖表
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.4])
    plot_df = df.tail(60)
    fig.add_trace(go.Candlestick(x=plot_df['date'], open=plot_df['open'], high=plot_df['high'], low=plot_df['low'], close=plot_df['close'], name='K線'), row=1, col=1)
    fig.add_trace(go.Bar(x=plot_df['date'], y=plot_df['Hist'], name='MACD柱', marker_color=['red' if h >= 0 else 'green' for h in plot_df['Hist']]), row=2, col=1)
    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=20, b=20, l=0, r=0))
    st.plotly_chart(fig, use_container_width=True)

   # --- 深度財務診斷區塊 (強化防錯版) ---
    if target_id != "TAIEX":
        st.divider()
        st.subheader(f"📊 {selected_label} 深度財務診斷")
        f_all = get_comprehensive_finance(target_id)
        
        if f_all is not None:
            c1, c2, c3, c4 = st.columns(4)
            
            # 1. EPS 處理
            with c1:
                st.write("**EPS (每股盈餘)**")
                try:
                    eps = f_all['state'][f_all['state']['type'] == 'EPSTaxAfter'].tail(4)
                    st.table(eps[['date', 'value']].rename(columns={'date':'季度', 'value':'元'}))
                except: st.warning("暫無 EPS 資料")
            
            # 2. 毛利率 處理
            with c2:
                st.write("**毛利率 (%)**")
                try:
                    gross = f_all['analysis'][f_all['analysis']['type'] == 'GrossProfitMargin'].tail(4)
                    st.table(gross[['date', 'value']].rename(columns={'date':'季度', 'value':'%'}))
                except: st.warning("暫無資料")

            # 3. 營業利益率 處理
            with c3:
                st.write("**營業利益率 (%)**")
                try:
                    op_margin = f_all['analysis'][f_all['analysis']['type'] == 'OperatingProfitMargin'].tail(4)
                    st.table(op_margin[['date', 'value']].rename(columns={'date':'季度', 'value':'%'}))
                except: st.warning("暫無資料")

            # 4. ROE 處理
            with c4:
                st.write("**ROE 報酬率 (%)**")
                try:
                    roe = f_all['analysis'][f_all['analysis']['type'] == 'ReturnOnEquityAftax'].tail(4)
                    st.table(roe[['date', 'value']].rename(columns={'date':'季度', 'value':'%'}))
                except: st.warning("暫無資料")
        else:
            st.info("💡 正在從 FinMind 伺服器獲取最新財報數據，請稍候約 10 秒...")
else:
    # 這是對應最上方 get_stock_data 的 else
    st.warning("📡 股價數據連線中，若長時間沒反應請點擊右上角 Rerun")
