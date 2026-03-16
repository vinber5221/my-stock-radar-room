import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 1. 雲端資料庫連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_cloud_data():
    try:
        # ttl=0 確保不使用舊快取，每次都抓最新的 Google Sheet 資料
        df = conn.read(worksheet="Sheet1", ttl=0)
        # 清洗資料：移除空行並確保格式正確
        df = df.dropna(subset=['type'])
        
        # 抓取現金：找 type 等於 cash 的那一行
        cash_row = df[df['type'] == 'cash']
        if not cash_row.empty:
            cash = float(cash_row['value1'].values[0])
        else:
            cash = 10000000.0
            
        # 抓取持倉：找 type 等於 stock 的行
        inventory = {}
        stock_df = df[df['type'] == 'stock']
        for _, row in stock_df.iterrows():
            inventory[str(row['id'])] = {"shares": int(row['value1']), "cost": float(row['value2'])}
        return cash, inventory
    except Exception as e:
        # 如果這裡報錯，代表連線網址或 Secrets 沒設好
        st.error(f"📡 雲端同步失敗，請檢查 Secrets 網址。錯誤訊息: {e}")
        return 10000000.0, {}

def save_cloud_data(cash, inventory):
    """將當前財產狀態寫入 Google Sheet"""
    # 建立要上傳的資料包
    data = [{"type": "cash", "id": "balance", "value1": cash, "value2": 0}]
    for sid, info in inventory.items():
        data.append({"type": "stock", "id": sid, "value1": info['shares'], "value2": info['cost']})
    
    new_df = pd.DataFrame(data)
    try:
        conn.update(worksheet="Sheet1", data=new_df)
    except:
        st.sidebar.warning("⚠️ 寫入雲端失敗，請確認試算表權限為『編輯者』")

# --- 2. 帳戶狀態讀取 (只在第一次啟動時執行) ---
if 'cash' not in st.session_state:
    st.session_state.cash, st.session_state.inventory = load_cloud_data()

# --- 3. UI 介面設定 ---
st.set_page_config(page_title="Vincent 1000萬雲端戰情室", layout="wide")
st.sidebar.header("🕹️ 交易控制台")

# 初始化按鈕
if st.sidebar.button("⚠️ 初始化帳戶 (重置雲端資料)", type="primary", use_container_width=True):
    st.session_state.cash, st.session_state.inventory = 10000000.0, {}
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
        # 統一欄位名稱
        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={'max':'high', 'min':'low', 'opening_price':'open', 'closing_price':'close', 'taiex':'close'}, inplace=True)
        return df
    except: return pd.DataFrame()

df = get_stock_data(target_id)

if not df.empty:
    latest_price = df.iloc[-1]['close']
    st.sidebar.divider()
    st.sidebar.write(f"💰 目前現金：**${st.session_state.cash:,.0f}**")
    
    if target_id != "TAIEX":
        qty = st.sidebar.number_input("下單股數", min_value=0, step=1000, value=1000)
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.sidebar.button("🔴 買入", use_container_width=True):
                cost = qty * latest_price
                if st.session_state.cash >= cost:
                    st.session_state.cash -= cost
                    if target_id in st.session_state.inventory:
                        inv = st.session_state.inventory[target_id]
                        inv['cost'] = ((inv['shares'] * inv['cost']) + cost) / (inv['shares'] + qty)
                        inv['shares'] += qty
                    else:
                        st.session_state.inventory[target_id] = {"shares": qty, "cost": latest_price}
                    save_cloud_data(st.session_state.cash, st.session_state.inventory)
                    st.rerun()
        with c2:
            if st.sidebar.button("🟢 賣出", use_container_width=True):
                if target_id in st.session_state.inventory and st.session_state.inventory[target_id]['shares'] >= qty:
                    st.session_state.cash += (qty * latest_price)
                    st.session_state.inventory[target_id]['shares'] -= qty
                    if st.session_state.inventory[target_id]['shares'] == 0: del st.session_state.inventory[target_id]
                    save_cloud_data(st.session_state.cash, st.session_state.inventory)
                    st.rerun()

    # --- 4. 主畫面分析圖表 ---
    st.title("🏛️ 1,000 萬雲端戰情室")
    # 計算總資產
    cur_stock_val = sum([info['shares'] * (latest_price if sid == target_id else info['cost']) for sid, info in st.session_state.inventory.items()])
    total_assets = st.session_state.cash + cur_stock_val
    
    m1, m2, m3 = st.columns(3)
    m1.metric("基金淨值", f"${total_assets:,.0f}", f"${total_assets - 10000000:,.0f}")
    m2.metric("可用現金", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 現價", f"${latest_price:.1f}")

    fig = go.Figure(data=[go.Candlestick(x=df.tail(60)['date'], open=df.tail(60)['open'], high=df.tail(60)['high'], low=df.tail(60)['low'], close=df.tail(60)['close'])])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=10,b=10,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 雲端持倉明細 (已連線)")
    if st.session_state.inventory:
        display_df = pd.DataFrame([{"標的": monitor_list.get(s, s), "股數": i['shares'], "均價": round(i['cost'], 1)} for s, i in st.session_state.inventory.items()])
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("目前無持倉，數據已與雲端同步。")
else:
    st.warning("數據連線中...")
