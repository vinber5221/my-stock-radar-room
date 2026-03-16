import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import json

# --- 1. 雲端資料庫連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_cloud_data():
    """讀取試算表數據"""
    try:
        # ttl=0 確保每次重新整理都抓最新資料
        df = conn.read(worksheet="Sheet1", ttl=0)
        df = df.dropna(subset=['type']) # 移除空行
        cash = float(df[df['type'] == 'cash']['value1'].values[0])
        inventory = {}
        stock_df = df[df['type'] == 'stock']
        for _, row in stock_df.iterrows():
            inventory[str(row['id'])] = {"shares": int(row['value1']), "cost": float(row['value2'])}
        return cash, inventory
    except Exception:
        # 讀取失敗（例如網路問題或表格式不對）回傳預設值
        return 10000000.0, {}

def save_cloud_data(cash, inventory):
    """嘗試寫入雲端，若失敗則顯示警告但維持本地運作"""
    data = [{"type": "cash", "id": "balance", "value1": cash, "value2": 0}]
    for sid, info in inventory.items():
        data.append({"type": "stock", "id": sid, "value1": info['shares'], "value2": info['cost']})
    new_df = pd.DataFrame(data)
    
    try:
        conn.update(worksheet="Sheet1", data=new_df)
    except Exception as e:
        st.sidebar.warning("⚠️ 雲端備份失敗（權限受限），但本次交易已完成。")
        st.sidebar.info("提示：請確認試算表共用設定為『知道連結的人：編輯者』")

# --- 2. 帳戶狀態初始化 ---
if 'cash' not in st.session_state:
    st.session_state.cash, st.session_state.inventory = load_cloud_data()

# --- 3. UI 介面與數據核心 ---
st.set_page_config(page_title="Vincent 1000萬雲端戰情室", layout="wide")
st.sidebar.header("🕹️ 交易控制台")

# 初始化按鈕
if st.sidebar.button("⚠️ 初始化帳戶 (回歸1000萬)", type="primary", use_container_width=True):
    st.session_state.cash = 10000000.0
    st.session_state.inventory = {}
    save_cloud_data(10000000.0, {})
    st.rerun()

monitor_list = {"TAIEX": "台股大盤", "0050": "元大台灣50", "2330": "台積電", "2317": "鴻海", "2454": "聯發科"}
selected_label = st.sidebar.selectbox("🚀 選擇觀測標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

@st.cache_data(ttl=3600)
def get_stock_data(sid):
    dl = DataLoader()
    try:
        if sid == "TAIEX":
            df = dl.taiwan_stock_index(index_id="TAIEX", start_date="2024-01-01")
        else:
            df = dl.taiwan_stock_daily(stock_id=sid, start_date="2024-01-01")
        
        # 欄位名稱校正 (對應 KeyError 問題)
        df.columns = [c.lower() for c in df.columns]
        col_map = {'max': 'high', 'min': 'low', 'opening_price': 'open', 'closing_price': 'close', 'taiex': 'close'}
        df.rename(columns=col_map, inplace=True)
        return df
    except: return pd.DataFrame()

df = get_stock_data(target_id)

if not df.empty:
    latest_price = df.iloc[-1]['close']
    st.sidebar.divider()
    st.sidebar.write(f"💰 帳戶現金：**${st.session_state.cash:,.0f}**")
    
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
                else: st.sidebar.error("資金不足")
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
    stock_val = 0
    for sid, info in st.session_state.inventory.items():
        # 若是目前標的用現價，否則用成本估算
        p = latest_price if sid == target_id else info['cost']
        stock_val += info['shares'] * p
    
    total_assets = st.session_state.cash + stock_val
    m1, m2, m3 = st.columns(3)
    m1.metric("基金淨值", f"${total_assets:,.0f}", f"${total_assets - 10000000:,.0f}")
    m2.metric("可用現金", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 現價", f"${latest_price:.1f}")

    # K線圖
    fig = go.Figure(data=[go.Candlestick(
        x=df.tail(60)['date'], open=df.tail(60)['open'], 
        high=df.tail(60)['high'], low=df.tail(60)['low'], close=df.tail(60)['close']
    )])
    fig.update_layout(height=400, template="plotly_dark", xaxis_ranges
