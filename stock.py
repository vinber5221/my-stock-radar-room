@st.cache_data(ttl=3600)
def get_processed_data(stock_id, period="日線"):
    dl = DataLoader()
    df = pd.DataFrame()
    start_dt = "2020-01-01"
    
    # 強制執行邏輯
    try:
        if stock_id == "TAIEX":
            # 1. 先抓大盤
            df = dl.taiwan_stock_index(index_id="TAIEX", start_date=start_dt)
            # 2. 如果大盤是空的，立刻改抓 0050
            if df is None or df.empty:
                df = dl.taiwan_stock_daily(stock_id="0050", start_date=start_dt)
        else:
            df = dl.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
    except Exception as e:
        # 如果發生任何錯誤，最後的保命符：直接抓 0050
        if stock_id == "TAIEX":
            df = dl.taiwan_stock_daily(stock_id="0050", start_date=start_dt)
        else:
            return pd.DataFrame()

    if df is None or df.empty: return pd.DataFrame()

    # 欄位標準化 (確保備援的 0050 也能被正確讀取)
    if 'stock_id' in df.columns and df['stock_id'].iloc[0] == '0050':
        # 這裡不需要改名，因為 0050 本身就有 close
        pass
    else:
        for col in df.columns:
            if col.upper() in ['TAIEX', 'VALUE']:
                df.rename(columns={col: 'close'}, inplace=True)
                break
                
    df.rename(columns={'max': 'high', 'min': 'low'}, inplace=True)
    for c in ['open', 'high', 'low', 'close']:
        if c not in df.columns: df[c] = df.get('close', 0)
    
    # ... (後面週期重組與 MACD 計算代碼保持不變)
