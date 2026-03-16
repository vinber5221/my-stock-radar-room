import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 🎯 直接寫死網址，跳過 Secrets ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/16J4r7jpddd7pXUdJTtf474qwILQOUE2Z-agqxgOodCo"

# 建立連線
conn = st.connection("gsheets", type=GSheetsConnection, spreadsheet=SHEET_URL)

def load_cloud_data():
    try:
        # 強制讀取主分頁
        df = conn.read(ttl=0).dropna(subset=['type'])
        
        # 讀取現金
        cash_row = df[df['type'].astype(str).str.contains('cash', case=False)]
        cash = float(cash_row['value1'].values[0]) if not cash_row.empty else 10000000.0
            
        # 讀取持倉
        inventory = {}
        stock_df = df[df['type'].astype(str).str.contains('stock', case=False)]
        for _, row in stock_df.iterrows():
            inventory[str(row['id'])] = {"shares": int(row['value1']), "cost": float(row['value2'])}
            
        st.toast("✅ 雲端連線成功！")
        return cash, inventory
    except Exception as e:
        st.error(f"📡 連線失敗：{e}")
        return 10000000.0, {}

def save_cloud_data(cash, inventory):
    data = [{"type": "cash", "id": "balance", "value1": cash, "value2": 0}]
    for sid, info in inventory.items():
        data.append({"type": "stock", "id": sid, "value1": info['shares'], "value2": info['cost']})
    try:
        new_df = pd.DataFrame(data)
        conn.update(data=new_df)
        st.toast("💾 數據已回寫雲端")
    except:
        st.sidebar.error("❌ 存檔失敗，請確認試算表權限")

# --- 2. 帳戶初始化 ---
if 'cash' not in st.session_state:
    st.session_state.cash, st.session_state.inventory = load_cloud_data()

# --- 3. UI 介面 ---
st.set_page_config(page_title="Vincent 雲端戰情室", layout="wide")
st.sidebar.header("🕹️ 控制台")

if st.sidebar.button("🔄 強制刷新雲端"):
    st.session_state.clear()
    st.rerun()

monitor_list = {"TAIEX": "台股大盤", "0050": "0050", "2330": "台積電", "2317": "鴻海", "2454": "聯發科"}
selected_label = st.sidebar.selectbox("🚀 選擇標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

@st.cache_data(ttl=3600)
def get_stock_data(sid):
    dl = DataLoader()
    try:
        df = dl.taiwan_stock_daily(stock_id=sid, start_date="2024-01-01") if sid != "TAIEX" else dl.taiwan_stock_index(index_id="TAIEX", start_date="2024-01-01")
        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={'max':'high','min':'low','opening_price':'open','closing_price':'close','taiex':'close'}, inplace=True)
        return df
    except: return pd.DataFrame()

df = get_stock_data(target_id)

if not df.empty:
    latest_price = df.iloc[-1]['close']
    st.sidebar.write(f"💰 現金：**${st.session_state.cash:,.0f}**")
    
    if target_id != "TAIEX":
        qty = st.sidebar.number_input("股數", min_value=0, step=1000, value=1000)
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.sidebar.button("買入", use_container_width=True):
                if st.session_state.cash >= (qty * latest_price):
                    st.session_state.cash -= (qty * latest_price)
                    if target_id in st.session_state.inventory:
                        st.session_state.inventory[target_id]['shares'] += qty
                    else: st.session_state.inventory[target_id] = {"shares": qty, "cost": latest_price}
                    save_cloud_data(st.session_state.cash, st.session_state.inventory)
                    st.rerun()
        with c2:
            if st.sidebar.button("賣出", use_container_width=True):
                if target_id in st.session_state.inventory and st.session_state.inventory[target_id]['shares'] >= qty:
                    st.session_state.cash += (qty * latest_price)
                    st.session_state.inventory[target_id]['shares'] -= qty
                    if st.session_state.inventory[target_id]['shares'] == 0: del st.session_state.inventory[target_id]
                    save_cloud_data(st.session_state.cash, st.session_state.inventory)
                    st.rerun()

    st.title("🏛️ 1,000 萬雲端實戰監控")
    stock_val = sum([info['shares'] * (latest_price if sid == target_id else info['cost']) for sid, info in st.session_state.inventory.items()])
    m1, m2, m3 = st.columns(3)
    m1.metric("基金淨值", f"${st.session_state.cash + stock_val:,.0f}")
    m2.metric("可用現金", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 現價", f"${latest_price:.1f}")

    fig = go.Figure(data=[go.Candlestick(x=df.tail(60)['date'], open=df.tail(60)['open'], high=df.tail(60)['high'], low=df.tail(60)['low'], close=df.tail(60)['close'])])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=0,b=0,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    if st.session_state.inventory:
        st.subheader("📋 持倉明細")
        st.dataframe(pd.DataFrame([{"標的": monitor_list.get(s, s), "股數": i['shares'], "均價": i['cost']} for s, i in st.session_state.inventory.items()]), use_container_width=True, hide_index=True)
else:
    st.warning("數據載入中...")
