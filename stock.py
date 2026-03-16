import streamlit as st
from FinMind.data import DataLoader
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import requests

# --- 1. 系統通訊設定 ---
LINE_TOKEN = "hBmawO0uysekx/UhIGUNysagEuHJX7kvgXMkAQHSoOWPjvcVh/4j6oQBLDDuV2s+7iRV4q6cDIh2uy1tHenUb5jk3/GYmmBL32wipEOk5NHPzHNZLnKAU+ogwTsujwSMcpbFeq0bO7XkrjoGM//5TgdB04t89/1O/w1cDnyilFU="
MY_USER_ID = "Ubc4a3750cdea1cb6f51e00a534fd6e1a"

def send_line_notification(message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"to": MY_USER_ID, "messages": [{"type": "text", "text": message}]}
    try:
        requests.post(url, json=payload, headers=headers)
        return True
    except: return False

# --- 2. 數據抓取與計算核心 (強化備援邏輯) ---
@st.cache_data(ttl=3600)
def get_processed_data(stock_id, period="日線"):
    dl = DataLoader()
    df = pd.DataFrame()
    start_dt = "2020-01-01"
    
    try:
        if stock_id == "TAIEX":
            # 優先嘗試抓大盤
            df = dl.taiwan_stock_index(index_id="TAIEX", start_date=start_dt)
            # 如果大盤沒資料，立刻自動切換到 0050 備援
            if df is None or df.empty:
                df = dl.taiwan_stock_daily(stock_id="0050", start_date=start_dt)
                st.info("💡 目前大盤連線較慢，已自動載入 0050 指標供您參考。")
        else:
            df = dl.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
    except Exception as e:
        # 萬一連線完全斷開，最後的強制備援
        if stock_id == "TAIEX":
            df = dl.taiwan_stock_daily(stock_id="0050", start_date=start_dt)
        else:
            return pd.DataFrame()

    if df is None or df.empty: return pd.DataFrame()

    # 欄位標準化與 OHLC 補齊
    # 檢查是否為 0050 格式或是指數格式
    if 'stock_id' in df.columns and '0050' in df['stock_id'].values:
        pass # 0050 本身就有標準 OHLC 欄位
    else:
        for col in df.columns:
            if col.upper() in ['TAIEX', 'VALUE']:
                df.rename(columns={col: 'close'}, inplace=True)
                break
    
    # 確保所有 K 線欄位都存在 (防止 KeyError)
    df.rename(columns={'max': 'high', 'min': 'low'}, inplace=True)
    for c in ['open', 'high', 'low', 'close']:
        if c not in df.columns:
            df[c] = df.get('close', 0)

    # 週期重組 (Resampling)
    if period != "日線":
        rule_map = {"週線": "W", "月線": "M", "年線": "Y"}
        df['date'] = pd.to_datetime(df
