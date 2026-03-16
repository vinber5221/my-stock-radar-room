import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd
import json

# --- 1. 雲端永久記憶 (讀取 Secrets) ---
def load_account():
    if 'cash' not in st.session_state:
        try:
            # 優先從雲端 Secrets 讀取初始設定
            st.session_state.cash = float(st.secrets["CASH"])
            inv_str = st.secrets.get("INVENTORY", "{}")
            st.session_state.inventory = json.loads(inv_str)
        except:
            # 若 Secrets 讀取失敗的保險方案
            st.session_state.cash = 10000000.0
            st.session_state.inventory = {}

load_account()

# --- 2. 初始化功能 ---
def reset_account():
    # 這裡的重設是暫時的，重新整理網頁後會讀回 Secrets 的原始值
    st.session_state.cash = 10000000.0
    st.session_state.inventory = {}
    st.toast("🛡️ 帳戶已暫時重設，若要永久重設請修改 Secrets 設定")
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

# --- 4. UI 介面 ---
st.set_page_config(page_title="Vincent 1000萬永久戰情室", layout="wide")
st.sidebar.header("🕹️ 交易控制台")

if st.sidebar.button("⚠️ 初始化帳戶 (回歸1000萬)", type="primary", use_container_width=True):
    reset_account()

monitor_list = {"TAIEX": "台股大盤", "0050": "元大台灣50", "2330": "台積電", "2317": "鴻海", "2454": "聯發科"}
selected_label = st.sidebar.selectbox("🚀 選擇標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

df = get_main_data(target_id)

st.sidebar.divider()
st.sidebar.subheader("💰 帳戶餘額")
st.sidebar.write(f"可用現金：**${st.session_state.cash:,.0f}**")

if not df.empty:
    latest_price = df.iloc[-1]['close']
    
    if target_id != "TAIEX":
        qty = st.sidebar.number_input("欲交易股數 (張=1000)", min_value=0, step=1000, value=1000)
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.sidebar.button("🔴 買入", use_container_width=True):
                cost = qty * latest_price
                if st.session_state.cash >= cost:
                    st.session_state.cash -= cost
                    if target_id in st.session_state.inventory:
                        st.session_state.inventory[target_id]['shares'] += qty
                    else:
                        st.session_state.inventory[target_id] = {"shares": qty, "cost": latest_price}
                    st.rerun()
                else: st.sidebar.error("資金不足")
        with c2:
            if st.sidebar.button("🟢 賣出", use_container_width=True):
                if target_id in st.session_state.inventory and st.session_state.inventory[target_id]['shares'] >= qty:
                    st.session_state.cash += qty * latest_price
                    st.session_state.inventory[target_id]['shares'] -= qty
                    if st.session_state.inventory[target_id]['shares'] == 0:
                        del st.session_state.inventory[target_id]
                    st.rerun()

    # --- 5. 主畫面 ---
    stock_val = 0
    for sid, info in st.session_state.inventory.items():
        p = latest_price if sid == target_id else info['cost']
        stock_val += info['shares'] * p
    
    total_assets = st.session_state.cash + stock_val
    
    st.title("🏛️ 1,000 萬基金監控中心")
    m1, m2, m3 = st.columns(3)
    m1.metric("基金總資產 (淨值)", f"${total_assets:,.0f}", f"${total_assets - 10000000:,.0f}")
    m2.metric("可用現金", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 現價", f"${latest_price:.2f}")

    fig = go.Figure(data=[go.Candlestick(x=df.tail(60)['date'], open=df.tail(60)['open'], high=df.tail(60)['high'], low=df.tail(60)['low'], close=df.tail(60)['close'])])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=10,b=10,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 基金持倉明細")
    if st.session_state.inventory:
        inv_list = [{"標的": monitor_list.get(sid, sid), "股數": info['shares'], "平均成本價": round(info['cost'], 1)} 
                    for sid, info in st.session_state.inventory.items()]
        st.dataframe(pd.DataFrame(inv_list), use_container_width=True, hide_index=True)
    else:
        st.info("目前無持倉。")
else:
    st.warning("數據載網中，請稍候...")
