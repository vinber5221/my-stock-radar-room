import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- 1. 介面設定 ---
st.set_page_config(page_title="Vincent 深度數據戰情室", layout="wide")

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
        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={'max':'high', 'min':'low', 'opening_price':'open', 'closing_price':'close', 'taiex':'close'}, inplace=True)
        
        # 法人資料 (近 30 日)
        inst_df = dl.taiwan_stock_institutional_investors(stock_id=sid, start_date="2025-01-01") if sid != "TAIEX" else pd.DataFrame()
        
        # 財報資料
        fin_df = dl.taiwan_stock_financial_statement(stock_id=sid, start_date="2023-01-01") if sid != "TAIEX" else pd.DataFrame()
        
        return df, inst_df, fin_df
    except: return None, None, None

df, inst_df, fin_df = fetch_all_data(target_id)

# --- 3. 畫面顯示 ---
st.title(f"🏛️ {selected_label} ({target_id}) 深度數據戰情室")

if df is not None:
    # A. 頂部 K 線圖
    fig_k = go.Figure(data=[go.Candlestick(
        x=df.tail(60)['date'], open=df.tail(60)['open'], 
        high=df.tail(60)['high'], low=df.tail(60)['low'], close=df.tail(60)['close'], 
        increasing_line_color='#FF4136', decreasing_line_color='#3D9970'
    )])
    fig_k.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=0,b=0,l=0,r=0))
    st.plotly_chart(fig_k, use_container_width=True)

    # B. 數據分頁
    tab1, tab2 = st.tabs(["📊 法人買賣動態", "📈 EPS 獲利趨勢"])

    with tab1:
        if not inst_df.empty:
            st.subheader("三大法人每日買賣超 (張)")
            # 整理資料
            inst_pivot = inst_df.pivot_table(index='date', columns='name', values='buy').tail(20).reset_index()
            col_map = {'Foreign_Investor': '外資', 'Investment_Trust': '投信', 'Dealers': '自營商'}
            inst_pivot.rename(columns=col_map, inplace=True)

            # 建立圖表
            fig_inst = go.Figure()
            
            for col in [c for c in col_map.values() if c in inst_pivot.columns]:
                # 設定顏色：正值紅色，負值綠色
                colors = ['#FF4136' if val >= 0 else '#3D9970' for val in inst_pivot[col]]
                
                fig_inst.add_trace(go.Bar(
                    x=inst_pivot['date'],
                    y=inst_pivot[col],
                    name=col,
                    marker_color=colors,
                    hovertemplate='<b>%{x}</b><br>' + col + ': %{y:,.0f} 張<extra></extra>'
                ))

            fig_inst.update_layout(
                template="plotly_dark", height=500,
                barmode='group', # 分組柱狀圖
                xaxis_title=None, yaxis_title="張數 (買超 > 0, 賣超 < 0)",
                showlegend=True
            )
            # 強制加上 0 軸線
            fig_inst.add_hline(y=0, line_width=1, line_color="white")
            st.plotly_chart(fig_inst, use_container_width=True)
        else:
            st.info("此標的暫無法人資料")

    with tab2:
        if not fin_df.empty:
            st.subheader("季度獲利趨勢")
            eps_data = fin_df[fin_df['type'] == 'EPS'].copy()
            rev_data = fin_df[fin_df['type'] == 'Revenue'].copy()
            
            fig_fin = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=('季度營收趨勢', '每股盈餘 (EPS) 趨勢'))
            
            # 營收與 EPS 都用柱狀圖
            fig_fin.add_trace(go.Bar(x=rev_data['date'], y=rev_data['buy'], name='營收', marker_color='#4BC0C0'), row=1, col=1)
            fig_fin.add_trace(go.Bar(x=eps_data['date'], y=eps_data['buy'], name='EPS', marker_color='#FF9F40'), row=2, col=1)
            
            fig_fin.update_layout(template="plotly_dark", height=600, showlegend=False)
            st.plotly_chart(fig_fin, use_container_width=True)
        else:
            st.info("此標的暫無財報資料")

else:
    st.error("連線超時或數據格式有誤。")
