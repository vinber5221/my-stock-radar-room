import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd

# --- 1. 介面設定 ---
st.set_page_config(page_title="Vincent 投資戰情室", layout="wide")

st.sidebar.header("📊 觀測標的")
monitor_list = {"2330": "台積電", "2317": "鴻海", "2454": "聯發科", "0050": "元大台灣50", "TAIEX": "台股大盤"}
selected_label = st.sidebar.selectbox("🚀 選擇代號", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

# --- 2. 數據抓取函式 ---
@st.cache_data(ttl=3600)
def fetch_data(sid):
    dl = DataLoader()
    # 行情數據
    if sid == "TAIEX":
        df = dl.taiwan_stock_index(index_id="TAIEX", start_date="2024-01-01")
    else:
        df = dl.taiwan_stock_daily(stock_id=sid, start_date="2024-01-01")
    
    # 法人買賣超 (大盤無法人資料)
    inst_df = dl.taiwan_stock_institutional_investors(stock_id=sid, start_date="2024-12-01") if sid != "TAIEX" else pd.DataFrame()
    
    # 財務報表 (每季)
    fin_df = dl.taiwan_stock_financial_statement(stock_id=sid, start_date="2023-01-01") if sid != "TAIEX" else pd.DataFrame()
    
    return df, inst_df, fin_df

# --- 3. 畫面邏輯 ---
st.title(f"🏛️ {selected_label} ({target_id}) 深度戰情室")
df, inst_df, fin_df = fetch_data(target_id)

if not df.empty:
    # --- A. 頂部快訊 ---
    latest = df.iloc[-1]
    df.columns = [c.lower() for c in df.columns]
    close_col = 'taiex' if 'taiex' in df.columns else 'close'
    
    m1, m2, m3 = st.columns(3)
    m1.metric("當前股價", f"{latest[close_col]:,.2f}")
    
    # --- B. K線圖 ---
    fig = go.Figure(data=[go.Candlestick(
        x=df.tail(60)['date'], open=df.tail(60)['open'],
        high=df.tail(60)['max' if 'max' in df.columns else 'high'],
        low=df.tail(60)['min' if 'min' in df.columns else 'low'],
        close=df.tail(60)[close_col],
        increasing_line_color='#FF4136', decreasing_line_color='#3D9970'
    )])
    fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- C. 法人與財報分頁 ---
    tab1, tab2 = st.tabs(["👥 法人買賣超", "📑 財報資訊"])
    
    with tab1:
        if not inst_df.empty:
            # 整理法人數據，計算三大法人合計
            inst_pivot = inst_df.pivot_table(index='date', columns='name', values='buy')
            st.subheader("近期三大法人買賣趨勢")
            st.line_chart(inst_pivot.tail(20))
            st.dataframe(inst_df.tail(15), use_container_width=True)
        else:
            st.info("大盤或該標的暫無法人詳細資料")

    with tab2:
        if not fin_df.empty:
            # 挑選關鍵財報欄位
            items = ['Revenue', 'Net_Profit_After_Tax', 'EPS']
            filtered_fin = fin_df[fin_df['type'].isin(items)]
            st.subheader("季度財務指標")
            st.dataframe(filtered_fin.tail(20), use_container_width=True)
        else:
            st.info("暫無財務報表資料")

else:
    st.error("數據加載失敗，請稍後再試。")
