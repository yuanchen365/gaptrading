"""
Monitor Loop Module
處理主監控回圈邏輯
"""
import datetime
import pandas as pd
import strategy
from line_notifier import notifier


def run_monitoring_iteration(api, monitoring_list, prev_high_map, bias_map, contract_info, snapshots, session_state):
    """
    執行一次監控掃描迭代
    
    Args:
        api: Shioaji API 實例
        monitoring_list: 監控中的股票代碼列表 (固定樣本)
        prev_high_map: Dict[code] -> prev_high
        bias_map: Dict[code] -> bias
        contract_info: Dict[code] -> {name, reference}
        snapshots: 快照資料列表
        session_state: Streamlit session state
    
    Returns:
        (active_df, watchlist_df, gap_df)
    """
    active_data = []
    watchlist_data = []
    gap_candidates_data = []
    
    # Initialize triggered_history if not exists
    if 'triggered_history' not in session_state:
        session_state.triggered_history = set()
    
    for snap in snapshots:
        code = snap.code
        
        # Get contract info
        info = contract_info.get(code, {})
        ref_price = info.get("reference", 0.0)
        name = info.get("name", code)
        
        close = snap.close
        open_ = snap.open
        high = snap.high
        low = snap.low
        vol = snap.total_volume
        amt = snap.total_amount
        
        if close == 0:
            # No data yet, but still show in gap list
            row = {
                "時間": datetime.datetime.now().strftime("%H:%M:%S"),
                "代碼": code, "名稱": name, "現價": 0, "跳空%": "0.00%", "P-Loc": "0.00", "乖離率": "0.00%", "量能": "0張", "特徵": "等待開盤"
            }
            gap_candidates_data.append(row)
            continue
        
        
        # Get prev_close and prev_high
        prev_close = ref_price if ref_price > 0 else (close - (snap.change_price or 0))
        prev_high = prev_high_map.get(code, prev_close)
        bias_val = bias_map.get(code, 0)
        has_future = info.get("has_future", False)
        
        # Check criteria using strategy module
        is_active, features, p_loc, cond_gap = strategy.check_criteria(snap, prev_high, bias_val, has_future)
        
        row = {
            "時間": datetime.datetime.now().strftime("%H:%M:%S"),
            "代碼": code,
            "名稱": name,
            "現價": close,
            "跳空%": f"{((open_ - prev_close)/prev_close)*100:.2f}%",
            "P-Loc": f"{p_loc:.2f}",
            "乖離率": f"{bias_val:.2%}",
            "量能": f"{int(vol)}張",
            "特徵": " ".join(features)
        }
        
        # 1. 永遠加入符合跳空區 (固定觀察池)
        gap_candidates_data.append(row)
        
        # 2. 強勢區邏輯 (目前的狀態)
        if is_active:
            # 觸發 LINE 通知
            gap_val = (open_ - prev_close) / prev_close if prev_close != 0 else 0
            notifier.notify_signal(code, name, close, gap_val, p_loc, vol, amt, has_future)
            
            active_data.append(row)
            session_state.triggered_history.add(code)
        
        # 3. 轉弱區邏輯 (曾經符合但目前不符合)
        elif code in session_state.triggered_history:
            if not features:
                row['特徵'] = "(轉弱觀察)"
            watchlist_data.append(row)
    
    # Create DataFrames
    columns = ["時間", "代碼", "名稱", "現價", "跳空%", "P-Loc", "乖離率", "量能", "特徵"]
    active_df = pd.DataFrame(active_data) if active_data else pd.DataFrame(columns=columns)
    watchlist_df = pd.DataFrame(watchlist_data) if watchlist_data else pd.DataFrame(columns=columns)
    gap_df = pd.DataFrame(gap_candidates_data) if gap_candidates_data else pd.DataFrame(columns=columns)
    
    return active_df, watchlist_df, gap_df

