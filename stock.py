import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd

# --- 1. 介面設定 ---
st.set_page_config(page_title="Vincent 投資分析戰情室", layout="wide")

st.sidebar.header("🔍 觀測標的")
monitor_list = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", 
    "2308": "台達電", "2382": "廣達", "TAIEX": "台股大盤"
}

selected_label = st.sidebar.selectbox("🚀 選擇標的", list(monitor_list.values()))
target_id = [k for k, v in monitor_list.items() if v == selected_label][0]

# --- 2. 數據抓取 ---
@st.cache_data(ttl=3600)
def fetch_all_data(sid):
    dl = DataLoader()
    try:
        # 行情數據
        df = dl.taiwan_stock_daily(stock_id=sid, start_date="2024-01-01") if sid != "TAIEX" else dl.taiwan_stock_index(index_id="TAIEX", start_date="2024-01-01")
        # 統一欄位
        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={'max':'high', 'min':'low', 'opening_price':'open', 'closing_price':'close', 'taiex':'close'}, inplace=True)
        
        # 法人資料
        inst_df = dl.taiwan_stock_institutional_investors(stock_id=sid, start_date="2025-01-01") if sid != "TAIEX" else pd.DataFrame()
        
        # 財報資料 (抓兩年看趨勢)
        fin_df = dl.taiwan_stock_financial_statement(stock_id=sid, start_date="2023-01-01") if sid != "TAIEX" else pd.DataFrame()
        
        return df, inst_df, fin_df
    except: return None, None, None

df, inst_df, fin_df = fetch_all_data(target_id)

# --- 3. 畫面顯示 ---
st.title(f"🏛️ {selected_label} ({target_id}) 深度戰情室")

if df is not None:
    # A. 頂部 K 線圖
    fig_k = go.Figure(data=[go.Candlestick(
        x=df.tail(60)['date'], open=df.tail(60)['open'], high=df.tail(60)['high'], low=df.tail(60)['low'], close=df.tail(60)['close'],
        increasing_line_color='#FF4136', decreasing_line_color='#3D9970'
    )])
    fig_k.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=0,b=0,l=0,r=0))
    st.plotly_chart(fig_k, use_container_width=True)

    # B. 數據分頁 (法人 & 財報)
    tab1, tab2 = st.tabs(["📊 法人買賣動態", "📈 EPS 獲利趨勢"])

    with tab1:
        if not inst_df.empty:
            st.subheader("三大法人每日買賣超 (張)")
            inst_pivot = inst_df.pivot_table(index='date', columns='name', values='buy').tail(20).reset_index()
            # 欄位中文化
            col_map = {'Foreign_Investor': '外資', 'Investment_Trust': '投信', 'Dealers': '自營商'}
            inst_pivot.rename(columns=col_map, inplace=True)
            
            # 使用分組柱狀圖
            fig_inst = px.bar(inst_pivot, x='date', y=[c for c in col_map.values() if c in inst_pivot.columns],
                             barmode='group', color_discrete_sequence=['#FF6384', '#36A2EB', '#FFCE56'])
            fig_inst.update_layout(template="plotly_dark", height=450, xaxis_title=None, yaxis_title="張數")
            st.plotly_chart(fig_inst, use_container_width=True)
        else:
            st.info("此標的暫無法人資料")

    with tab2:
        if not fin_df.empty:
            # 處理財報數據
            eps_data = fin_df[fin_df['type'] == 'EPS'].copy()
            rev_data = fin_df[fin_df['type'] == 'Revenue'].copy()
            
            # 建立雙子圖：營收與 EPS
            fig_fin = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                                    subplot_titles=('季度營收趨勢', '每股盈餘 (EPS) 趨勢'))
            
            # 營收柱狀圖
            fig_fin.add_trace(go.Bar(x=rev_data['date'], y=rev_data['buy'], name='營收', marker_color='#4BC0C0'), row=1, col=1)
            # EPS 柱狀圖 (最重要的趨勢)
            fig_fin.add_trace(go.Bar(x=eps_data['date'], y=eps_data['buy'], name='EPS', marker_color='#FF9F40'), row=2, col=1)
            
            fig_fin.update_layout(template="plotly_dark", height=600, showlegend=False)
            st.plotly_chart(fig_fin, use_container_width=True)
            
            with st.expander("查看原始財報數值"):
                st.dataframe(fin_df.tail(20), use_container_width=True)
        else:
            st.info("此標的暫無財報資料")

else:
    st.error("連線超時或數據格式有誤。")
