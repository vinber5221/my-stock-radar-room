import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import pandas as pd

# --- 1. 介面設定 ---
st.set_page_config(page_title="Vincent 台股行情戰情室", layout="wide")

st.sidebar.header("📊 行情選擇")
monitor_list = {
    "TAIEX": "台股大盤",
    "0050": "元大台灣50",
    "2330": "台積電",
    "2317": "鴻海",
    "2454": "聯發科",
    "2308": "台達電",
    "2382": "廣達"
}

selected_label = st.sidebar.selectbox("🚀 選擇觀測標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

# --- 2. 資料抓取 ---
@st.cache_data(ttl=600)  # 每 10 分鐘自動更新一次數據
def get_stock_data(sid):
    dl = DataLoader()
    try:
        if sid == "TAIEX":
            df = dl.taiwan_stock_index(index_id="TAIEX", start_date="2024-01-01")
        else:
            df = dl.taiwan_stock_daily(stock_id=sid, start_date="2024-01-01")
        
        # 統一欄位格式
        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={
            'max': 'high', 'min': 'low', 
            'opening_price': 'open', 'closing_price': 'close', 
            'taiex': 'close'
        }, inplace=True)
        return df
    except:
        return pd.DataFrame()

# --- 3. 畫面顯示 ---
st.title(f"📈 {selected_label} ({target_id}) 實時監控")

df = get_stock_data(target_id)

if not df.empty:
    # 取得最新一筆資料
    latest = df.iloc[-1]
    prev_close = df.iloc[-2]['close']
    change = latest['close'] - prev_close
    pct_change = (change / prev_close) * 100

    # 頂部儀表板
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("當前價格", f"{latest['close']:,.2f}", f"{change:+.2f} ({pct_change:+.2f}%)")
    m2.metric("今日開盤", f"{latest['open']:,.2f}")
    m3.metric("今日最高", f"{latest['high']:,.2f}")
    m4.metric("今日最低", f"{latest['low']:,.2f}")

    # K 線圖
    st.subheader("📊 近 60 日 K 線圖")
    fig = go.Figure(data=[go.Candlestick(
        x=df.tail(60)['date'],
        open=df.tail(60)['open'],
        high=df.tail(60)['high'],
        low=df.tail(60)['low'],
        close=df.tail(60)['close'],
        increasing_line_color='#FF4136', # 漲用紅色
        decreasing_line_color='#3D9970'  # 跌用綠色
    )])
    
    fig.update_layout(
        height=500,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        margin=dict(t=10, b=10, l=10, r=10)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 歷史數據表格
    with st.expander("查看歷史數據明細"):
        st.dataframe(df.sort_values('date', ascending=False), use_container_width=True)

else:
    st.error("暫時無法取得行情數據，請稍後再試或檢查網路連線。")

st.sidebar.divider()
st.sidebar.info("💡 提示：本工具僅供行情參考，手動紀錄交易更有利於維持盤感。")
