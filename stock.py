import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- 1. 初始化交易大腦 (Session State) ---
if 'cash' not in st.session_state:
    st.session_state.cash = 10000000.0  # 初始一千萬
if 'inventory' not in st.session_state:
    st.session_state.inventory = {}  # 格式: {"2330": {"shares": 2000, "cost": 1050.0}}

# --- 2. 數據核心 ---
@st.cache_data(ttl=3600)
def get_stock_data(stock_id):
    dl = DataLoader()
    try:
        if stock_id == "TAIEX":
            df = dl.taiwan_stock_index(index_id="TAIEX", start_date="2024-01-01")
        else:
            df = dl.taiwan_stock_daily(stock_id=stock_id, start_date="2024-01-01")
        
        # 統一欄位名稱
        for col in df.columns:
            if col.upper() in ['TAIEX', 'VALUE']:
                df.rename(columns={col: 'close'}, inplace=True)
        df.rename(columns={'max': 'high', 'min': 'low'}, inplace=True)
        return df
    except: return pd.DataFrame()

# --- 3. UI 設定 ---
st.set_page_config(page_title="Vincent 1000萬模擬交易中心", layout="wide")
st.title("🏛️ 1,000 萬虛擬基金實戰模擬器")

# 側邊欄：觀測標的
monitor_list = {"2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達", "0050": "元大台灣50"}
selected_label = st.sidebar.selectbox("🚀 選擇下單標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

# 抓取即時數據
df = get_stock_data(target_id)
if not df.empty:
    current_price = df.iloc[-1]['close']
    
    # --- 頂部資產戰報 ---
    stock_value = 0
    for sid, data in st.session_state.inventory.items():
        # 這裡簡化處理，實際應用可再抓取各股現價
        stock_value += data['shares'] * current_price if sid == target_id else data['shares'] * data['cost']
    
    total_assets = st.session_state.cash + stock_value
    
    m1, m2, m3 = st.columns(3)
    m1.metric("總資產淨值", f"${total_assets:,.0f}", f"{(total_assets-10000000)/100000:.2f}%")
    m2.metric("剩餘可用現金", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 現價", f"${current_price}")

    # --- 交易操作區 ---
    st.divider()
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        trade_shares = st.number_input("交易股數 (1張=1000股)", min_value=0, step=1000, value=1000)
    with c2:
        st.write(" ") # 對齊用
        if st.button("🔴 執行買入", use_container_width=True):
            cost = trade_shares * current_price
            if st.session_state.cash >= cost:
                st.session_state.cash -= cost
                # 更新持倉
                if target_id in st.session_state.inventory:
                    old_data = st.session_state.inventory[target_id]
                    new_shares = old_data['shares'] + trade_shares
                    new_cost = ((old_data['shares'] * old_data['cost']) + cost) / new_shares
                    st.session_state.inventory[target_id] = {"shares": new_shares, "cost": new_cost}
                else:
                    st.session_state.inventory[target_id] = {"shares": trade_shares, "cost": current_price}
                st.success(f"成功買入 {selected_label} {trade_shares} 股！")
            else:
                st.error("現金不足！")
                
        if st.button("🟢 執行賣出", use_container_width=True):
            if target_id in st.session_state.inventory and st.session_state.inventory[target_id]['shares'] >= trade_shares:
                st.session_state.cash += trade_shares * current_price
                st.session_state.inventory[target_id]['shares'] -= trade_shares
                if st.session_state.inventory[target_id]['shares'] == 0:
                    del st.session_state.inventory[target_id]
                st.success(f"成功賣出 {selected_label} {trade_shares} 股！")
            else:
                st.error("持股不足，無法賣出！")

    # --- K線圖 ---
    fig = go.Figure(data=[go.Candlestick(x=df['date'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
    fig.update_layout(height=400, template="plotly_dark", margin=dict(t=0, b=0, l=0, r=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 4. 底部：我的持倉清單 ---
    st.subheader("📋 目前基金持倉明細")
    if st.session_state.inventory:
        inv_data = []
        for sid, info in st.session_state.inventory.items():
            name = monitor_list.get(sid, sid)
            current_val = info['shares'] * current_price if sid == target_id else "需切換查看"
            profit = (current_price - info['cost']) * info['shares'] if sid == target_id else "-"
            inv_data.append([name, info['shares'], f"{info['cost']:.2f}", current_val, profit])
        
        inv_df = pd.DataFrame(inv_data, columns=["股票名稱", "持有股數", "平均成本", "當前市值", "預估損益"])
        st.table(inv_df)
    else:
        st.info("目前尚無持倉，請從上方選擇標的並買入。")

    if st.button("🔄 重設帳戶 (回歸一千萬)"):
        st.session_state.cash = 10000000.0
        st.session_state.inventory = {}
        st.rerun()

else:
    st.warning("數據載入中...")
