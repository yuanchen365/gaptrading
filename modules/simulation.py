"""
Simulation Module
處理盤後回測邏輯，使用歷史 K 線資料重現盤中走勢
"""
import datetime
import time
import pandas as pd
import streamlit as st
from .monitor_loop import run_monitoring_iteration


def fetch_intraday_kbars(api, stock_codes, contract_info, target_date, progress_callback=None):
    """
    抓取指定日期的 1 分 K 線資料
    
    Args:
        api: Shioaji API 實例
        stock_codes: 股票代碼列表
        contract_info: 合約資訊字典
        target_date: 目標日期 (datetime.date)
        progress_callback: 進度回調函式
    
    Returns:
        Dict[code] -> pd.DataFrame: 每檔股票的 K 線資料
    """
    from shioaji.constant import Exchange
    
    # 設定時間範圍
    start_time = datetime.datetime.combine(target_date, datetime.time(9, 0))
    end_time = datetime.datetime.combine(target_date, datetime.time(13, 30))
    
    kbars_dict = {}
    total = len(stock_codes)
    
    for idx, code in enumerate(stock_codes):
        if progress_callback:
            progress_callback(idx, total, f"正在抓取 {code} 的 K 線資料...")
        
        try:
            # Get contract
            info = contract_info.get(code, {})
            
            # Try TSE first
            symbol = f"TSE{code}"
            contract = getattr(api.Contracts.Stocks.TSE, symbol, None)
            if not contract:
                # Try OTC
                symbol = f"OTC{code}"
                contract = getattr(api.Contracts.Stocks.OTC, symbol, None)
            
            if not contract:
                # 找不到合約 (可能是 ETF 或其他非 TSE/OTC 標的)
                if progress_callback:
                    progress_callback(idx, total, f"⚠️ {code} 跳過: 非 TSE/OTC 標的 (可能為 ETF)")
                continue
            
            # Fetch kbars
            kbars = api.kbars(
                contract=contract,
                start=target_date.strftime('%Y-%m-%d'),  # Use date-only format
                end=target_date.strftime('%Y-%m-%d')
            )
            
            if kbars:
                # Convert to DataFrame
                df = pd.DataFrame({**kbars})
                df['ts'] = pd.to_datetime(df['ts'])
                kbars_dict[code] = df
            else:
                # API 回傳空資料
                if progress_callback:
                    progress_callback(idx, total, f"⚠️ {code} 無 K 線資料 (可能為新上市或當日無交易)")
                
        except Exception as e:
            # API 呼叫錯誤
            error_msg = str(e)
            if 'invalid date format' in error_msg:
                if progress_callback:
                    progress_callback(idx, total, f"⚠️ {code} 抓取失敗: 日期格式錯誤 - {error_msg}")
            else:
                if progress_callback:
                    progress_callback(idx, total, f"⚠️ {code} 抓取失敗: {error_msg}")
            continue
    
    return kbars_dict


def kbars_to_snapshots(kbars_dict, timestamp, contract_info):
    """
    將 K 線資料轉換為 Snapshot 格式
    
    Args:
        kbars_dict: K 線資料字典
        timestamp: 當前時間點
        contract_info: 合約資訊字典
    
    Returns:
        List[MockSnapshot]: 模擬的快照資料
    """
    class MockSnapshot:
        def __init__(self, code, open_, high, low, close, volume, amount, change_price, name, reference):
            self.code = code
            self.open = open_
            self.high = high
            self.low = low
            self.close = close
            self.total_volume = volume
            self.total_amount = amount
            self.change_price = change_price
            self.name = name
            self.reference = reference
    
    snapshots = []
    
    for code, df in kbars_dict.items():
        # Find data at this timestamp
        mask = df['ts'] <= timestamp
        if not mask.any():
            continue
        
        # Get latest data up to this timestamp
        latest_row = df[mask].iloc[-1]
        
        # Get cumulative data up to this timestamp
        cumulative_df = df[mask]
        
        info = contract_info.get(code, {})
        reference = info.get('reference', 0.0)
        name = info.get('name', code)
        
        # Calculate current values
        open_ = cumulative_df.iloc[0]['Open']  # First bar's open
        high = cumulative_df['High'].max()
        low = cumulative_df['Low'].min()
        close = latest_row['Close']
        volume = cumulative_df['Volume'].sum()    # KBar Volume is usually in cent-sheets (0.1張) -> Convert to Sheets
        amount = cumulative_df['Amount'].sum()         # KBar Amount is raw Yuan
        
        change_price = close - reference if reference > 0 else 0
        
        snapshot = MockSnapshot(
            code=code,
            open_=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            amount=amount,
            change_price=change_price,
            name=name,
            reference=reference
        )
        
        snapshots.append(snapshot)
    
    return snapshots


def run_simulation(api, monitoring_list, prev_high_map, bias_map, 
                   contract_info, target_date, session_state, 
                   status_widget=None, speed=0.3):
    """
    執行回測主流程
    
    Args:
        api: Shioaji API 實例
        monitoring_list: 回測標的列表
        prev_high_map: 昨日最高價字典
        bias_map: 乖離率字典
        contract_info: 合約資訊字典
        target_date: 回測日期
        session_state: Streamlit session state
        status_widget: Streamlit status widget
        speed: 回放速度（秒/分鐘）
    
    Returns:
        Dict: 回測結果統計
    """
    def write_status(msg):
        if status_widget:
            status_widget.write(msg)
    
    # Step 1: Fetch K-bars
    write_status("📊 Step 1: 正在抓取歷史 K 線資料...")
    
    progress_bar = st.progress(0) if not status_widget else None
    progress_text = st.empty() if not status_widget else None
    
    def progress_callback(current, total, message):
        if progress_bar:
            progress_bar.progress(current / total)
        if progress_text:
            progress_text.text(message)
        if status_widget:
            status_widget.write(f"[{current}/{total}] {message}")
    
    kbars_dict = fetch_intraday_kbars(
        api, 
        monitoring_list, 
        contract_info, 
        target_date,
        progress_callback=progress_callback
    )
    
    if progress_bar:
        progress_bar.empty()
    if progress_text:
        progress_text.empty()
    
    write_status(f"✅ Step 1 完成: 成功抓取 {len(kbars_dict)} 檔股票的 K 線資料")
    
    if not kbars_dict:
        write_status("❌ 無法取得任何 K 線資料，回測終止")
        return {"status": "failed", "reason": "no_data"}
    
    # Step 2: Generate time series
    write_status("⏰ Step 2: 建立時間序列...")
    
    # Get all unique timestamps
    all_timestamps = set()
    for df in kbars_dict.values():
        all_timestamps.update(df['ts'].tolist())
    
    time_series = sorted(list(all_timestamps))
    write_status(f"✅ Step 2 完成: 共 {len(time_series)} 個時間點")
    
    # Step 3: Playback
    write_status("🎬 Step 3: 開始時間序列回放...")
    
    simulation_progress = st.progress(0)
    simulation_text = st.empty()
    
    results = {
        "total_minutes": len(time_series),
        "max_active": 0,
        "max_watchlist": 0,
        "max_gap": 0,
        "timeline": []
    }
    
    for idx, timestamp in enumerate(time_series):
        # Update progress
        progress = (idx + 1) / len(time_series)
        simulation_progress.progress(progress)
        simulation_text.text(f"⏰ 回放進度: {timestamp.strftime('%H:%M')} ({idx+1}/{len(time_series)})")
        
        # Convert kbars to snapshots at this timestamp
        snapshots = kbars_to_snapshots(kbars_dict, timestamp, contract_info)
        
        if not snapshots:
            continue
        
        # Run monitoring logic
        active_df, watchlist_df, gap_df = run_monitoring_iteration(
            api,
            monitoring_list,
            prev_high_map,
            bias_map,
            contract_info,
            snapshots,
            session_state
        )
        
        # Update session state
        session_state.active_df = active_df
        session_state.watchlist_df = watchlist_df
        session_state.gap_df = gap_df
        
        # Record statistics
        results['max_active'] = max(results['max_active'], len(active_df))
        results['max_watchlist'] = max(results['max_watchlist'], len(watchlist_df))
        results['max_gap'] = max(results['max_gap'], len(gap_df))
        
        results['timeline'].append({
            'time': timestamp,
            'active': len(active_df),
            'watchlist': len(watchlist_df),
            'gap': len(gap_df)
        })
        
        # Pause for visualization
        time.sleep(speed)
    
    simulation_progress.empty()
    simulation_text.empty()
    
    write_status(f"✅ Step 3 完成: 回測結束")
    write_status(f"📊 統計結果: 最高強勢股 {results['max_active']} 檔 | 最高觀察 {results['max_watchlist']} 檔")
    
    return results
