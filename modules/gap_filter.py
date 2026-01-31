"""
Gap Filter Module
處理開盤跳空篩選邏輯
"""
import pandas as pd
import streamlit as st
import datetime
from .contract_resolver import resolve_contracts
from .api_manager import fetch_snapshots_parallel


def run_gap_filter(api, candidate_list_path, status_widget=None):
    """
    執行開盤跳空篩選流程
    
    Args:
        api: Shioaji API 實例
        candidate_list_path: 候選清單 CSV 路徑
        status_widget: Streamlit status widget (可選)
    
    Returns:
        (gap_list, gap_df): 符合條件的代碼列表與 DataFrame
    """
    def write_status(msg):
        if status_widget:
            status_widget.write(msg)
        else:
            print(msg)
    
    # Step 1: Load Candidates
    write_status("📂 讀取監控清單...")
    candidates_df = pd.read_csv(candidate_list_path)
    all_codes = candidates_df['stock_code'].astype(str).str.strip().tolist()
    write_status(f"✅ 載入 {len(all_codes)} 檔候選股票")
    
    # Step 2: Resolve Contracts
    write_status(f"📜 轉換合約物件 (共 {len(all_codes)} 檔)...")
    contracts, contract_info = resolve_contracts(api, all_codes, show_warnings=True)
    
    if not contracts:
        write_status("❌ 找不到任何合約 (請檢查 API 初始化)")
        return [], pd.DataFrame()
    
    write_status(f"✅ 成功取得 {len(contracts)} 個合約")
    
    # Step 3: Fetch Snapshots
    write_status(f"☁️ 正在抓取個股報價 (Snapshots，共 {len(contracts)} 檔)...")
    snapshots = fetch_snapshots_parallel(api, contracts, chunk_size=300, max_workers=2)
    
    if not snapshots:
        write_status("⚠️ 取得 0 筆行情，可能是非盤中時間")
        return [], pd.DataFrame()
    
    write_status(f"✅ 成功取得 {len(snapshots)} 筆行情資料")
    
    # Step 4: Filter Logic
    write_status("⚡ 執行跳空邏輯運算...")
    
    # 防呆機制 1: 時間檢查
    now = datetime.datetime.now()
    if now.time() < datetime.time(9, 0, 0):
        write_status(f"⚠️ 注意: 目前時間 {now.strftime('%H:%M')} 尚未開盤 (09:00)，過濾器將嚴格檢查資料日期")

    gap_list = []
    gap_data = []
    stale_count = 0
    today_str = now.strftime('%Y-%m-%d')
    
    # Create lookup map for strategy tags
    strategy_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['strategy_tag']))

    for snap in snapshots:
        # 防呆機制 2: 資料日期核對 (Data Freshness Check)
        # Snapshot ts is in nanoseconds
        ts_date = datetime.datetime.fromtimestamp(snap.ts / 1_000_000_000).strftime('%Y-%m-%d')
        
        # 只有在非模擬模式下，才強制過濾過期資料
        if not api.simulation and ts_date != today_str:
            stale_count += 1
            continue

        code = snap.code
        open_ = snap.open
        
        # Use Static Reference from Contract
        info = contract_info.get(code, {})
        ref_price = info.get("reference", 0.0)
        name = info.get("name", code)
        
        if ref_price > 0 and open_ > 0:
            pct = (open_ - ref_price) / ref_price
            if pct >= 0.01:
                gap_list.append(code)
                
                # Get strategy tag and format it
                raw_tag = strategy_map.get(code, "")
                tag_display = raw_tag.replace("bias", "低基期").replace("ma_conv", "均線糾結").replace("|", " + ")

                gap_data.append({
                    "代碼": code,
                    "名稱": name,
                    "策略": tag_display,
                    "開盤": open_,
                    "昨收": ref_price,
                    "漲幅%": f"{pct*100:.2f}%",
                    "資料時間": str(datetime.datetime.fromtimestamp(snap.ts / 1_000_000_000).time())
                })
    
    if stale_count > 0:
        write_status(f"🛡️ 已自動過濾 {stale_count} 筆非今日 ({today_str}) 之過期資料")
    
    gap_df = pd.DataFrame(gap_data)
    
    if gap_df.empty and stale_count > 0:
         write_status(f"✅ 篩選完成! (過濾掉所有舊資料，目前無今日跳空標的)")
    else:
         write_status(f"✅ 篩選完成! 符合: {len(gap_list)} 檔")
    
    return gap_list, gap_df
