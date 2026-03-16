import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd

# --- 1. 虛擬帳戶初始化 (這部分會儲存在你的瀏覽器 session) ---
if 'cash' not in st.session_state:
    st.session_state.cash = 10000000.0
if 'inventory' not in st.session_state:
    st.session_state.inventory = {}  # 儲存結構: {"2330": {"shares": 1000, "cost": 1020.0}}

# --- 2. 數據獲取 ---
@st.cache_data(ttl=3600)
def get_all_prices(stock_list):
    """一次抓取所有持倉的最新價格，用於計算總市值"""
    dl = DataLoader()
    prices = {}
    for sid in stock_list:
        try:
            df = dl.taiwan_stock_daily(stock_id=sid, start_date="2026-03-01")
            if not df.empty:
                prices[sid] = df.iloc[-1]['close']
        except: prices[sid] = 0
    return prices

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

# --- 3. UI 佈局 ---
st.set_page_config(page_title="Vincent 1000萬實戰模擬", layout="wide")
st.title("🏛️ 1,000 萬虛擬基金實戰模擬器")

monitor_list = {"TAIEX": "台股大盤", "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達", "0050": "元大台灣50"}
selected_label = st.sidebar.selectbox("🚀 觀測/交易標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

# --- 4. 資產計算核心 (關鍵：加總所有持倉) ---
current_df = get_main_data(target_id)
if not current_df.empty:
    latest_price = current_df.iloc[-1]['close']
    
    # 計算所有持倉的總市值
    inventory_ids = list(st.session_state.inventory.keys())
    all_latest_prices = get_all_prices(inventory_ids)
    
    total_stock_value = 0
    for sid, info in st.session_state.inventory.items():
        # 如果是正在看的這一檔，用最新價；其他的用備份價
        price = latest_price if sid == target_id else all_latest_prices.get(sid, info['cost'])
        total_stock_value += info['shares'] * price
    
    total_assets = st.session_state.cash + total_stock_value
    profit_total = total_assets - 10000000.0

    # 頂部儀表板
    m1, m2, m3 = st.columns(3)
    m1.metric("基金總資產 (含持倉市值)", f"${total_assets:,.0f}", f"${profit_total:,.0f}")
    m2.metric("剩餘可用現金", f"${st.session_state.cash:,.0f}")
    m3.metric(f"{selected_label} 即時價", f"${latest_price:.2f}")

    # --- 交易面板 ---
    st.divider()
    if target_id == "TAIEX":
        st.info("💡 大盤指數僅供觀測趨勢，不可直接買賣。請切換至個股進行模擬交易。")
    else:
        tc1, tc2, tc3 = st.columns([1, 1, 2])
        with tc1:
            trade_qty = st.number_input("預計交易股數", min_value=0, step=1000, value=1000)
        with tc2:
            st.write(" ")
            if st.button("🔴 確認買入", use_container_width=True):
                total_cost = trade_qty * latest_price
                if st.session_state.cash >= total_cost:
                    st.session_state.cash -= total_cost
                    if target_id in st.session_state.inventory:
                        inv = st.session_state.inventory[target_id]
                        new_shares = inv['shares'] + trade_qty
                        inv['cost'] = ((inv['shares'] * inv['cost']) + total_cost) / new_shares
                        inv['shares'] = new_shares
                    else:
                        st.session_state.inventory[target_id] = {"shares": trade_qty, "cost": latest_price}
                    st.success(f"已買入 {trade_qty} 股，現金剩餘 ${st.session_state.cash:,.0f}")
                    st.rerun()
                else: st.error("資金不足！")
        with tc3:
            st.write(" ")
            if st.button("🟢 確認賣出", use_container_width=True):
                if target_id in st.session_state.inventory and st.session_state.inventory[target_id]['shares'] >= trade_qty:
                    st.session_state.cash += trade_qty * latest_price
                    st.session_state.inventory[target_id]['shares'] -= trade_qty
                    if st.session_state.inventory[target_id]['shares'] == 0:
                        del st.session_state.inventory[target_id]
                    st.success(f"已賣出 {trade_qty} 股，現金增加至 ${st.session_state.cash:,.0f}")
                    st.rerun()
                else: st.error("持股餘額不足！")

    # K線圖
    fig = go.Figure(data=[go.Candlestick(x=current_df.tail(100)['date'], open=current_df.tail(100)['open'], 
                                        high=current_df.tail(100)['high'], low=current_df.tail(100)['low'], 
                                        close=current_df.tail(100)['close'])])
    fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=0,b=0,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- 持倉明細表格 ---
    st.subheader("📋 基金持倉明細與即時損益")
    if st.session_state.inventory:
        inv_data = []
        for sid, info in st.session_state.inventory.items():
            name = monitor_list.get(sid, sid)
            p = latest_price if sid == target_id else all_latest_prices.get(sid, info['cost'])
            current_mkt_val = info['shares'] * p
            profit = current_mkt_val - (info['shares'] * info['cost'])
            weight = (current_mkt_val / total_assets) * 100
            inv_data.append([name, info['shares'], f"{info['cost']:.1f}", f"{p:.1f}", f"{current_mkt_val:,.0f}", f"{profit:,.0f}", f"{weight:.1f}%"])
        
        display_df =
