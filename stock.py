import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd

# --- 1. 虛擬帳戶初始化 ---
if 'cash' not in st.session_state:
    st.session_state.cash = 10000000.0
if 'inventory' not in st.session_state:
    st.session_state.inventory = {}  # {"2330": {"shares": 1000, "cost": 1020.0}}

# --- 2. 數據核心 ---
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

# --- 3. UI 佈局 ---
st.set_page_config(page_title="Vincent 1000萬實戰模擬", layout="wide")
st.title("🏛️ 1,000 萬虛擬基金實戰模擬器")

monitor_list = {"TAIEX": "台股大盤", "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達", "0050": "元大台灣50"}
selected_label = st.sidebar.selectbox("🚀 觀測/交易標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

# --- 4. 資產計算與顯示 ---
df = get_main_data(target_id)
if not df.empty:
    latest_price = df.iloc[-1]['close']
    
    # 計算總市值 (簡化版：非當前標的以買入成本計，當前標的以現價計)
    total_stock_value = 0
    for sid, info in st.session_state.inventory.items():
        price = latest_price if sid == target_id else info['cost']
        total_stock_value += info['shares'] * price
    
    total_assets = st.session_state.cash + total_stock_value
    profit_total = total_assets - 10000000.0

    m1, m2, m3 = st.columns(3)
    m1.metric("基金總資產 (淨值)", f"${total_assets:,.0f}", f"${profit_total:,.0f}")
    m2.metric("可用現金餘額", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 即時價", f"${latest_price:.2f}")

    # --- 交易面板 ---
    st.divider()
    if target_id == "TAIEX":
        st.info("💡 大盤指數僅供觀測。請切換至個股進行買賣模擬。")
    else:
        tc1, tc2, tc3 = st.columns([1, 1, 2])
        with tc1:
            trade_qty = st.number_input("交易股數", min_value=0, step=1000, value=1000)
        with tc2:
            st.write(" ")
            if st.button("🔴 確認買入", use_container_width=True):
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
                    st.success("買入成功！")
                    st.rerun()
                else: st.error("資金不足")
        with tc3:
            st.write(" ")
            if st.button("🟢 確認賣出", use_container_width=True):
                if target_id in st.session_state.inventory and st.session_state.inventory[target_id]['shares'] >= trade_qty:
                    st.session_state.cash += trade_qty * latest_price
                    st.session_state.inventory[target_id]['shares'] -= trade_qty
                    if st.session_state.inventory[target_id]['shares'] == 0:
                        del st.session_state.inventory[target_id]
                    st.success("賣出成功！")
                    st.rerun()
                else: st.error("持股不足")

    # K線圖
    fig = go.Figure(data=[go.Candlestick(x=df.tail(100)['date'], open=df.tail(100)['open'], high=df.tail(100)['high'], low=df.tail(100)['low'], close=df.tail(100)['close'])])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=0,b=0,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- 持倉清單 ---
    st.subheader("📋 基金持倉明細")
    if st.session_state.inventory:
        inv_data = []
        for sid, info in st.session_state.inventory.items():
            name = monitor_list.get(sid, sid)
            p = latest_price if sid == target_id else info['cost']
            mkt_val = info['shares'] * p
            inv_data.append([name, info['shares'], f"{info['cost']:.1f}", f"{mkt_val:,.0f}"])
        
        display_df = pd.DataFrame(inv_data, columns=["標的名稱", "持有股數", "平均成本價", "當前市值估計"])
        st.table(display_df)
    else:
        st.info("目前無持倉。")

    # 深度財務診斷
    if target_id != "TAIEX":
        st.divider()
        st.subheader(f"📊 {selected_label} 深度財務診斷")
        f_all = get_comprehensive_finance(target_id)
        if f_all:
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                st.write("**EPS (每股盈餘)**")
                try: st.table(f_all['state'][f_all['state']['type']=='EPSTaxAfter'].tail(4)[['date','value']])
                except: st.write("無資料")
            with fc2:
                st.write("**毛利率 (%)**")
                try: st.table(f_all['analysis'][f_all['analysis']['type']=='GrossProfitMargin'].tail(4)[['date','value']])
                except: st.write("無資料")
            with fc3:
                st.write("**ROE (%)**")
                try: st.table(f_all['analysis'][f_all['analysis']['type']=='ReturnOnEquityAftax'].tail(4)[['date','value']])
                except: st.write("無資料")

    if st.sidebar.button("🔄 重設基金帳戶"):
        st.session_state.cash = 10000000.0
        st.session_state.inventory = {}
        st.rerun()
else:
    st.warning("數據連線中...")
