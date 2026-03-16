import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 1. 雲端連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_cloud_data():
    try:
        # 強制讀取 Sheet1
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        if df.empty:
            st.error("⚠️ 雲端讀取結果為空！請檢查試算表內是否有資料。")
            return 10000000.0, {}
            
        # 顯示讀取狀態 (除錯用，成功後可刪除)
        st.toast(f"✅ 雲端連線成功，讀取到 {len(df)} 筆資料")
        
        df = df.dropna(subset=['type'])
        cash_row = df[df['type'] == 'cash']
        cash = float(cash_row['value1'].values[0]) if not cash_row.empty else 10000000.0
            
        inventory = {}
        stock_df = df[df['type'] == 'stock']
        for _, row in stock_df.iterrows():
            inventory[str(row['id'])] = {"shares": int(row['value1']), "cost": float(row['value2'])}
        return cash, inventory
    except Exception as e:
        st.error(f"📡 雲端連線失敗！錯誤訊息：{e}")
        return 10000000.0, {}

def save_cloud_data(cash, inventory):
    data = [{"type": "cash", "id": "balance", "value1": cash, "value2": 0}]
    for sid, info in inventory.items():
        data.append({"type": "stock", "id": sid, "value1": info['shares'], "value2": info['cost']})
    try:
        conn.update(worksheet="Sheet1", data=pd.DataFrame(data))
        st.toast("💾 數據已同步至雲端試算表")
    except Exception as e:
        st.sidebar.error(f"❌ 存檔失敗: {e}")

# --- 2. 帳戶初始化 ---
if 'cash' not in st.session_state:
    st.session_state.cash, st.session_state.inventory = load_cloud_data()

# --- 3. UI 介面 ---
st.set_page_config(page_title="Vincent 1000萬永久戰情室", layout="wide")
st.sidebar.header("🕹️ 控制台")

if st.sidebar.button("⚠️ 初始化雲端帳戶", type="primary", use_container_width=True):
    st.session_state.cash, st.session_state.inventory = 10000000.0, {}
    save_cloud_data(10000000.0, {})
    st.rerun()

monitor_list = {"TAIEX": "台股大盤", "0050": "元大台灣50", "2330": "台積電", "2317": "鴻海", "2454": "聯發科"}
selected_label = st.sidebar.selectbox("🚀 選擇標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

@st.cache_data(ttl=3600)
def get_stock_data(sid):
    dl = DataLoader()
    try:
        df = dl.taiwan_stock_daily(stock_id=sid, start_date="2024-01-01") if sid != "TAIEX" else dl.taiwan_stock_index(index_id="TAIEX", start_date="2024-01-01")
        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={'max': 'high', 'min': 'low', 'opening_price': 'open', 'closing_price': 'close', 'taiex': 'close'}, inplace=True)
        return df
    except: return pd.DataFrame()

df = get_stock_data(target_id)

if not df.empty:
    latest_price = df.iloc[-1]['close']
    st.sidebar.divider()
    st.sidebar.write(f"💰 目前雲端現金：**${st.session_state.cash:,.0f}**")
    
    if target_id != "TAIEX":
        qty = st.sidebar.number_input("交易股數", min_value=0, step=1000, value=1000)
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.sidebar.button("🔴 買入", use_container_width=True):
                if st.session_state.cash >= (qty * latest_price):
                    st.session_state.cash -= (qty * latest_price)
                    if target_id in st.session_state.inventory:
                        st.session_state.inventory[target_id]['shares'] += qty
                    else: st.session_state.inventory[target_id] = {"shares": qty, "cost": latest_price}
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

    # --- 4. 主畫面 ---
    st.title("🏛️ 1,000 萬雲端實戰監控")
    stock_val = sum([info['shares'] * (latest_price if sid == target_id else info['cost']) for sid, info in st.session_state.inventory.items()])
    total_assets = st.session_state.cash + stock_val
    m1, m2, m3 = st.columns(3)
    m1.metric("基金淨值", f"${total_assets:,.0f}", f"${total_assets - 10000000:,.0f}")
    m2.metric("可用現金", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 現價", f"${latest_price:.1f}")

    fig = go.Figure(data=[go.Candlestick(x=df.tail(60)['date'], open=df.tail(60)['open'], high=df.tail(60)['high'], low=df.tail(60)['low'], close=df.tail(60)['close'])])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=10,b=10,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 雲端持倉明細")
    if st.session_state.inventory:
        inv_df = pd.DataFrame([{"標的": monitor_list.get(s, s), "股數": i['shares'], "均價": round(i['cost'], 1)} for s, i in st.session_state.inventory.items()])
        st.dataframe(inv_df, use_container_width=True, hide_index=True)
    else: st.info("目前無持倉。")
else:
    st.warning("數據載入中...")
