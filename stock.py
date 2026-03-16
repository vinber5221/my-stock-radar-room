import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 1. 雲端資料庫連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_cloud_data():
    """讀取試算表，若讀失敗則回歸初始 1,000 萬"""
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        cash = float(df[df['type'] == 'cash']['value1'].values[0])
        inventory = {}
        stock_df = df[df['type'] == 'stock']
        for _, row in stock_df.iterrows():
            inventory[str(row['id'])] = {"shares": int(row['value1']), "cost": float(row['value2'])}
        return cash, inventory
    except:
        return 10000000.0, {}

def save_cloud_data(cash, inventory):
    """同步資料到雲端"""
    data = [{"type": "cash", "id": "balance", "value1": cash, "value2": 0}]
    for sid, info in inventory.items():
        data.append({"type": "stock", "id": sid, "value1": info['shares'], "value2": info['cost']})
    new_df = pd.DataFrame(data)
    conn.update(worksheet="Sheet1", data=new_df)

# --- 2. 帳戶狀態讀取 ---
if 'cash' not in st.session_state:
    st.session_state.cash, st.session_state.inventory = load_cloud_data()

# --- 3. UI 介面 ---
st.set_page_config(page_title="Vincent 1000萬雲端戰情室", layout="wide")
st.sidebar.header("🕹️ 交易控制台")

# 初始化按鈕
if st.sidebar.button("⚠️ 初始化帳戶 (重置雲端)", type="primary", use_container_width=True):
    st.session_state.cash = 10000000.0
    st.session_state.inventory = {}
    save_cloud_data(10000000.0, {})
    st.rerun()

monitor_list = {"TAIEX": "台股大盤", "0050": "元大台灣50", "2330": "台積電", "2317": "鴻海", "2454": "聯發科"}
selected_label = st.sidebar.selectbox("🚀 選擇標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

# 下單設定
st.sidebar.divider()
st.sidebar.write(f"💰 帳戶現金：**${st.session_state.cash:,.0f}**")

@st.cache_data(ttl=3600)
def get_stock_data(sid):
    dl = DataLoader()
    try:
        df = dl.taiwan_stock_daily(stock_id=sid, start_date="2024-01-01") if sid != "TAIEX" else dl.taiwan_stock_index(index_id="TAIEX", start_date="2024-01-01")
        for col in df.columns:
            if col.upper() in ['TAIEX', 'VALUE']: df.rename(columns={col: 'close'}, inplace=True)
        return df
    except: return pd.DataFrame()

df = get_stock_data(target_id)

if not df.empty:
    latest_price = df.iloc[-1]['close']
    
    if target_id != "TAIEX":
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
                    save_cloud_data(st.session_state.cash, st.session_state.inventory)
                    st.rerun()
        with c2:
            if st.sidebar.button("🟢 賣出", use_container_width=True):
                if target_id in st.session_state.inventory and st.session_state.inventory[target_id]['shares'] >= trade_qty:
                    st.session_state.cash += trade_qty * latest_price
                    st.session_state.inventory[target_id]['shares'] -= trade_qty
                    if st.session_state.inventory[target_id]['shares'] == 0:
                        del st.session_state.inventory[target_id]
                    save_cloud_data(st.session_state.cash, st.session_state.inventory)
                    st.rerun()

    # --- 4. 主畫面分析 ---
    st.title("🏛️ 1,000 萬雲端戰情室")
    total_stock_value = 0
    for sid, info in st.session_state.inventory.items():
        p = latest_price if sid == target_id else info['cost']
        total_stock_value += info['shares'] * p
    
    total_assets = st.session_state.cash + total_stock_value
    
    m1, m2, m3 = st.columns(3)
    m1.metric("基金淨值", f"${total_assets:,.0f}", f"${total_assets - 10000000:,.0f}")
    m2.metric("可用現金", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 現價", f"${latest_price:.1f}")

    fig = go.Figure(data=[go.Candlestick(x=df.tail(60)['date'], open=df.tail(60)['open'], high=df.tail(60)['high'], low=df.tail(60)['low'], close=df.tail(60)['close'])])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=10,b=10,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 雲端同步持倉")
    if st.session_state.inventory:
        inv_df = pd.DataFrame([{"標的": monitor_list.get(s, s), "股數": i['shares'], "均價": round(i['cost'], 1)} for s, i in st.session_state.inventory.items()])
        st.dataframe(inv_df, use_container_width=True, hide_index=True)
    else: st.info("空倉中，數據已同步至雲端。")
else: st.warning("數據載入中...")
