import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd

# --- 1. 基金大腦初始化 (Session State) ---
if 'cash' not in st.session_state:
    st.session_state.cash = 10000000.0
if 'inventory' not in st.session_state:
    st.session_state.inventory = {}

# --- 2. 核心功能：帳戶初始化 ---
def reset_account():
    st.session_state.cash = 10000000.0
    st.session_state.inventory = {}
    st.toast("🛡️ 帳戶已重設，回歸 1,000 萬本金與零持倉")
    st.rerun()

# --- 3. 數據核心 ---
@st.cache_data(ttl=3600)
def get_main_data(stock_id):
    dl = DataLoader()
    try:
        if stock_id == "TAIEX":
            df = dl.taiwan_stock_index(index_id="TAIEX", start_date="2024-01-01")
        else:
            df = dl.taiwan_stock_daily(stock_id=stock_id, start_date="2024-01-01")
        for col in df.columns:
            if col.upper() in ['TAIEX', 'VALUE']: df.rename(columns={col: 'close'}, inplace=True)
        df.rename(columns={'max': 'high', 'min': 'low'}, inplace=True)
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_comprehensive_finance(stock_id):
    if stock_id == "TAIEX": return None
    dl = DataLoader()
    try:
        fin_state = dl.taiwan_stock_financial_statements(stock_id=stock_id, start_date="2023-01-01")
        fin_analysis = dl.taiwan_stock_financial_analysis(stock_id=stock_id, start_date="2023-01-01")
        return {"state": fin_state, "analysis": fin_analysis}
    except: return None

# --- 4. UI 介面 ---
st.set_page_config(page_title="Vincent 1000萬實戰模擬", layout="wide")

# --- 側邊欄：控制中心 ---
st.sidebar.header("🕹️ 交易控制台")

# 初始化按鈕
if st.sidebar.button("⚠️ 初始化帳戶 (重回1000萬)", type="primary", use_container_width=True):
    reset_account()

monitor_list = {"TAIEX": "台股大盤", "0050": "元大台灣50", "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達"}
selected_label = st.sidebar.selectbox("🚀 選擇觀測標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

df = get_main_data(target_id)

st.sidebar.divider()
st.sidebar.subheader("💰 帳戶餘額")
st.sidebar.write(f"可用現金：**${st.session_state.cash:,.0f}**")

if not df.empty:
    latest_price = df.iloc[-1]['close']
    
    st.sidebar.divider()
    st.sidebar.subheader("🛒 下單設定")
    if target_id == "TAIEX":
        st.sidebar.info("指數標的僅供參考，請切換至個股交易。")
    else:
        trade_qty = st.sidebar.number_input("欲交易股數", min_value=0, step=1000, value=1000)
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.sidebar.button("🔴 買入", use_container_width=True):
                cost = trade_qty * latest_price
                if st.session_state.cash >= cost:
                    st.session_state.cash -= cost
                    if target_id in st.session_state.inventory:
                        inv = st.session_state.inventory[target_id]
                        new_shares = inv['shares'] + trade_qty
                        inv['cost'] = ((inv['shares'] * inv['cost']) + cost) / new_shares
                        inv['shares'] = new_shares
                    else:
                        st.session_state.inventory[target_id] = {"shares": trade_qty, "cost": latest_price}
                    st.rerun()
                else: st.sidebar.error("資金不足")
        with c2:
            if st.sidebar.button("🟢 賣出", use_container_width=True):
                if target_id in st.session_state.inventory and st.session_state.inventory[target_id]['shares'] >= trade_qty:
                    st.session_state.cash += trade_qty * latest_price
                    st.session_state.inventory[target_id]['shares'] -= trade_qty
                    if st.session_state.inventory[target_id]['shares'] == 0:
                        del st.session_state.inventory[target_id]
                    st.rerun()
                else: st.sidebar.error("持股不足")

    # --- 5. 主畫面顯示 ---
    total_stock_value = 0
    for sid, info in st.session_state.inventory.items():
        p = latest_price if sid == target_id else info['cost']
        total_stock_value += info['shares'] * p
    
    total_assets = st.session_state.cash + total_stock_value
    
    st.title("🏛️ 1,000 萬基金監控中心")
    m1, m2, m3 = st.columns(3)
    m1.metric("基金總資產 (淨值)", f"${total_assets:,.0f}", f"${total_assets - 10000000:,.0f}")
    m2.metric("可用現金", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 現價", f"${latest_price:.2f}")

    fig = go.Figure(data=[go.Candlestick(x=df.tail(100)['date'], open=df.tail(100)['open'], high=df.tail(100)['high'], low=df.tail(100)['low'], close=df.tail(100)['close'])])
    fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=10,b=10,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 基金持倉明細")
    if st.session_state.inventory:
        inv_data = [{"標的": monitor_list.get(sid, sid), "股數": info['shares'], "成本": round(info['cost'], 1)} 
                    for sid, info in st.session_state.inventory.items()]
        st.dataframe(pd.DataFrame(inv_data), use_container_width=True, hide_index=True)
    else:
        st.info("目前無持倉。")

    if target_id != "TAIEX":
        st.divider()
        st.subheader(f"📊 {selected_label} 財務診斷")
        f_all = get_comprehensive_finance(target_id)
        if f_all:
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                st.write("**EPS (每股盈餘)**")
                try: st.table(f_all['state'][f_all['state']['type']=='EPSTaxAfter'].tail(4)[['date','value']])
                except: st.write("無數據")
            with fc2:
                st.write("**毛利率 (%)**")
                try: st.table(f_all['analysis'][f_all['analysis']['type']=='GrossProfitMargin'].tail(4)[['date','value']])
                except: st.write("無數據")
            with fc3:
                st.write("**ROE (%)**")
                try: st.table(f_all['analysis'][f_all['analysis']['type']=='ReturnOnEquityAftax'].tail(4)[['date','value']])
                except: st.write("無數據")
else:
    st.warning("數據載入中...")
