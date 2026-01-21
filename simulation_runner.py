import shioaji as sj
import pandas as pd
import datetime
import time
import config
import strategy
import json
import os

# --- Configuration ---
SIMULATION_DATE = datetime.datetime.now().strftime('%Y-%m-%d') # Default to today
# SIMULATION_DATE = "2024-01-14" # Manual override if needed

def init_shioaji():
    print("Initializing Shioaji API...")
    try:
        api = sj.Shioaji(simulation=True)
        if "api_key" in config.CONFIG and "secret_key" in config.CONFIG:
            api.login(
                api_key=config.CONFIG["api_key"], 
                secret_key=config.CONFIG["secret_key"]
            )
            print("Login Successful")
            return api
        else:
            print("Missing credentials.")
            return None
    except Exception as e:
        print(f"Login Failed: {e}")
        return None

def run_simulation_for_ui(api, candidates_df, status_callback=None, match_callback=None, progress_bar=None, limit=None):
    """
    Run simulation logic for Streamlit UI
    
    Args:
        api: Shioaji API instance
        candidates_df: DataFrame with stock_code, bias, prev_high
        status_callback: function(msg) to update status text
        match_callback: function(match_dict) to handle new match
        progress_bar: streamlit progress bar object
        limit (int): Max number of stocks to scan
    """
    
    SIMULATION_DATE = datetime.datetime.now().strftime('%Y-%m-%d')
    # SIMULATION_DATE = "2024-01-14" # Manual override if needed
    
    if status_callback: status_callback(f"準備模擬資料中... (日期: {SIMULATION_DATE})")

    # Filter for testing?
    scan_list = candidates_df
    if limit and isinstance(limit, int) and limit > 0:
        scan_list = candidates_df.head(limit)
    
    # scan_list = candidates_df # Full mode
    
    # Prepare Maps
    if 'prev_high' in candidates_df.columns:
        prev_high_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['prev_high']))
    else:
        prev_high_map = {}
    bias_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['bias']))

    # 2. Fetch 1-min Kbars
    if status_callback: status_callback(f"正在下載 {len(scan_list)} 檔股票之 1分K 資料...")
    
    stock_kbars = {}
    codes = scan_list['stock_code'].astype(str).tolist()
    total_codes = len(codes)
    
    for i, code in enumerate(codes):
        # Update progress
        if progress_bar: progress_bar.progress((i / total_codes) * 0.5) # First 50% is downloading
        if i % 10 == 0 and status_callback: 
            status_callback(f"下載進度: {i}/{total_codes} ({code})")
        
        contract = api.Contracts.Stocks.get(code)
        if not contract: continue
        
        try:
            kbars = api.kbars(contract, start=SIMULATION_DATE, end=SIMULATION_DATE)
            df = pd.DataFrame({**kbars})
            if not df.empty:
                df.ts = pd.to_datetime(df.ts)
                stock_kbars[code] = df
        except:
            pass

    if not stock_kbars:
        if status_callback: status_callback("❌ 無法取得任何 K 線資料，請確認今日是否開盤。")
        return

    # 3. Time Machine Loop
    start_time = datetime.datetime.strptime(f"{SIMULATION_DATE} 09:00:00", "%Y-%m-%d %H:%M:%S")
    end_time = datetime.datetime.strptime(f"{SIMULATION_DATE} 13:30:00", "%Y-%m-%d %H:%M:%S")
    
    current_time = start_time
    delta = datetime.timedelta(minutes=1)
    triggered_history = set()
    
    total_steps = (end_time - start_time).seconds // 60
    current_step = 0
    
    if status_callback: status_callback("🚀 開始歷史回放...")
    
    killed = False
    
    while current_time <= end_time:
        if killed: break
        
        current_step += 1
        # Progress from 50% to 100%
        if progress_bar: 
            prog = 0.5 + (current_step / total_steps) * 0.5
            progress_bar.progress(min(prog, 1.0))
            
        time_str = current_time.strftime("%H:%M")
        
        # Lists for this minute
        current_active_data = []
        current_watchlist_data = []
        
        # Check every stock
        for code, df in stock_kbars.items():
            # Optimization: Pre-filter or maintain index pointers would be faster
            mask = df['ts'] <= current_time
            history_slice = df[mask]
            
            if history_slice.empty: continue
            
            # Synthesize Snapshot
            open_price = history_slice.iloc[0]['Open']
            high_price = history_slice['High'].max()
            low_price = history_slice['Low'].min()
            close_price = history_slice.iloc[-1]['Close']
            volume = history_slice['Volume'].sum()
            amount = history_slice['Amount'].sum()
            
            mock_snap = {
                'code': code,
                'name': code, 
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'total_volume': volume,
                'total_amount': amount,
                'prev_close': 0 
            }
            
            prev_high = prev_high_map.get(str(code), 0)
            bias_val = bias_map.get(str(code), 0)
            
            # Check Logic
            is_active, features, p_loc, cond_gap = strategy.check_criteria(mock_snap, prev_high, bias_val)
            
            row_data = {
                "時間": time_str,
                "代碼": code,
                "名稱": code,
                "現價": close_price,
                "跳空%": f"{(open_price/prev_high - 1)*100:.2f}%" if prev_high else "N/A",
                "P-Loc": f"{p_loc:.2f}",
                "乖離率": f"{bias_val:.2%}",
                "量能": f"{volume}張",
                "特徵": " ".join(features)
            }
            
            if is_active:
                current_active_data.append(row_data)
                triggered_history.add(code)
            elif code in triggered_history:
                # Watchlist
                if not features: row_data['特徵'] = "(轉弱觀察)"
                current_watchlist_data.append(row_data)
        
        # Callback update
        if match_callback:
            match_callback(current_active_data, current_watchlist_data)
            
        if status_callback: 
            status_callback(f"模擬時間: {time_str} | 強勢: {len(current_active_data)} | 觀察: {len(current_watchlist_data)}")

        current_time += delta
        # Simulate speed
        time.sleep(0.05) 
        
    if status_callback: status_callback(f"模擬完成！歷史總觸發: {len(triggered_history)} 檔")

if __name__ == "__main__":
    run_simulation()
