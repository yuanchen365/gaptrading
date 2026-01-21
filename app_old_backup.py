import streamlit as st
import pandas as pd
import shioaji as sj
import time
import datetime
from pathlib import Path
import sys

# Ensure current directory is in python path for imports
sys.path.append(str(Path(__file__).resolve().parent))

import config
import strategy
from line_notifier import notifier

# Page Configuration
st.set_page_config(page_title="台股即時強勢跳空篩選", layout="wide")

# Helper Functions
@st.cache_resource(ttl=3600*4) # Cache for 4 hours, but validate logic will clear it if stale
def init_shioaji():
    try:
        api = sj.Shioaji(simulation=True) 
        # Attempt login
        if "api_key" in config.CONFIG and "secret_key" in config.CONFIG:
            api.login(
                api_key=config.CONFIG["api_key"], 
                secret_key=config.CONFIG["secret_key"]
            )
            
            
        # Validate Contracts (The Blocking Wait)
        has_contracts = False
        if hasattr(api, 'Contracts'):
             try:
                 if api.Contracts.Stocks["2330"]: has_contracts = True
             except: pass
             
        if not has_contracts:
            st.warning("⚠️ 偵測到合約庫尚未就緒，正在下載最新合約... (請勿關閉)")
            try:
                api.fetch_contracts(contract_download=True)
                
                # Wait loop (Max 60s)
                progress_text = "等待合約下載中..."
                my_bar = st.progress(0, text=progress_text)
                
                for i in range(60):
                    time.sleep(1)
                    try:
                        if api.Contracts.Stocks["2330"]:
                            st.success("✅ 合約下載與載入完成!")
                            my_bar.empty()
                            has_contracts = True
                            break
                    except:
                        pass
                    my_bar.progress(int((i/60)*100), text=f"{progress_text} ({i}s)")
                
                if not has_contracts:
                    st.error("❌ 合約下載超時 (60s)，部分功能可能無法使用。請檢查網際網路連線。")
                    
            except Exception as e:
                st.error(f"合約下載指令失敗: {e}")

        return api
    except Exception as e:
        st.error(f"Shioaji Login Failed: {e}")
        return None

def get_valid_api():
    """Wrapper to get API and ensure it's actually alive and has contracts"""
    api = init_shioaji()
    if not api: return None
    
    # Strict Health Check: Must have Contracts loaded
    # Only checking '2330' as a proxy for "Contracts Loaded"
    is_healthy = False
    try:
        if api.Contracts.Stocks["2330"]: is_healthy = True
    except: pass
    
    if not is_healthy:
        st.warning("⚠️ 偵測到 API 快照失效 (合約庫遺失)，正在重置連線...")
        st.cache_resource.clear() # Clear the corrupted cache
        time.sleep(1)
        return init_shioaji() # Create fresh instance
        
    return api


def run_pre_process():
    import pre_process
    with st.spinner('執行盤前篩選中 (FinLab)...'):
        stock_list = pre_process.get_candidates()
    st.success(f"篩選完成！共 {len(stock_list)} 檔低基期股票。")
    return stock_list

def fetch_snapshots_parallel(api, contracts, chunk_size=15, max_workers=2):
    """
    Fetches snapshots for a list of contracts using parallel threads.
    Handles chunking and retries automatically.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Split contracts into chunks
    chunks = [contracts[i:i+chunk_size] for i in range(0, len(contracts), chunk_size)]
    
    snapshots = []
    
    def fetch_chunk_with_retry(api, chunk, chunk_id):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Shioaji api calls should be thread-safe for simple reads
                res = api.snapshots(chunk)
                if res: return res
            except Exception:
                # Silently retry or log if needed
                pass
        return []

    # Execute in Parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_chunk_with_retry, api, c, i): i for i, c in enumerate(chunks)}
        
        for future in as_completed(futures):
            res = future.result()
            if res:
                snapshots.extend(res)
                
    return snapshots

# --- Main Logic with State ---
if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False
if 'log' not in st.session_state:
    st.session_state.log = []
if 'active_df' not in st.session_state:
    st.session_state.active_df = pd.DataFrame(columns=["代碼", "名稱", "現價", "跳空%", "P-Loc", "乖離率", "量能", "特徵"])
if 'watchlist_df' not in st.session_state:
    st.session_state.watchlist_df = pd.DataFrame(columns=["代碼", "名稱", "現價", "跳空%", "P-Loc", "乖離率", "量能", "特徵"])
if 'gap_df' not in st.session_state:
    st.session_state.gap_df = pd.DataFrame(columns=["代碼", "名稱", "現價", "跳空%", "P-Loc", "乖離率", "量能", "特徵"])
if 'monitoring_list' not in st.session_state:
    st.session_state.monitoring_list = []
if 'discarded_count' not in st.session_state:
    st.session_state.discarded_count = 0
if 'retry_counts' not in st.session_state:
    st.session_state.retry_counts = {}  # Map: stock_code -> failure_count

st.title("🚀 台股即時強勢跳空篩選器")

# Sidebar
with st.sidebar:
    with st.expander("📖 專案交易流程說明"):
        st.markdown("""
        ### 1. 盤前準備 (Pre-Market)
        *   **目標**：篩選出「低基期」的潛力股。
        *   **執行**：若無名單，UI 提示執行「盤前運算」。
        *   **邏輯**：取乖離率 (Bias) 最低之後 30%。
        *   **關鍵**：記錄昨日最高價 (PrevHigh) 作為跳空基準。

        ### 2. 盤中監控 (Intra-Day)
        *   **執行**：點擊「開始監控 (Start)」。
        *   **核心邏輯** (每 60 秒掃描)：
            1.  **嚴格跳空**：(Low >= PrevHigh) & (Open > PrevHigh * 1.01)
            2.  **股價位階**：P-Loc > 0.5 (維持中高檔)
            3.  **量能**：量 > 500 張 & 金額 > 1000 萬
        *   **LINE 通知**：首次進入強勢區時發送。

        ### 3. 盤後回測 (Post-Market)
        *   **執行**：收盤後 (13:30) 點擊「歷史回放」。
        *   **邏輯**：使用當日 1 分 K 線重現盤中走勢。
        """)
        
    st.header("控制台")
    
    # Debug: Manual Cache Clear
    if st.button("🔧 清除 API 快取 (Debug)"):
        st.cache_resource.clear()
        st.success("✅ 快取已清除，請重新執行篩選或監控")
        st.rerun()
    
    # 1. Credentials Check
    if "line_channel_access_token" not in config.CONFIG or config.CONFIG["line_channel_access_token"] == "YOUR_CHANNEL_ACCESS_TOKEN":
        st.warning("⚠️ 請先設定 LINE Messaging API Token")
    
    # 2. Data Check
    if not config.CANDIDATE_LIST_PATH.exists():
        st.warning("⚠️ 尚未建立監控清單")
        if st.button("執行盤前運算 (FinLab)"):
            run_pre_process()
            st.rerun()
    else:
        st.success("✅ 監控清單已就緒")
        # Load list to show count
        try:
            df = pd.read_csv(config.CANDIDATE_LIST_PATH)
            msg = f"監控檔數: {len(df)}"
            
            if 'data_date' in df.columns:
                d_date = str(df['data_date'].iloc[0])
                msg += f" | 資料日期: {d_date}"
                
                # Check freshness (simple check vs system today)
                # Note: System time might be different from Taiwan Market time, but usually matches in this context.
                today_str = datetime.datetime.now().strftime('%Y-%m-%d')
                if d_date != today_str:
                    st.warning(f"⚠️ 資料日期 ({d_date}) 非今日 ({today_str})，請確認是否需要重新執行盤前運算。")
                    if st.button("重新執行盤前運算 (FinLab)", key="rerun_pre_process_warning"):
                        run_pre_process()
                        st.rerun()
                else:
                    st.success(f"✅ 資料日期: {d_date} (最新)")
                    # Optional: Allow force re-run even if up to date
                    # if st.button("強制重新執行盤前運算"):
                    #    run_pre_process()
                    #    st.rerun()
            
            st.info(msg)
        except Exception as e:
            st.error(f"讀取清單失敗: {e}")
            pass

    st.divider()
    
    # 3. Gap Filter (New Workflow)
    if st.button("🔍 執行開盤跳空篩選 (Gap > 1%)"):
        st.session_state.monitoring = False # Stop monitoring first
        
        # Force clear cache to ensure fresh API
        st.cache_resource.clear()
        
        status = st.status("🚀 啟動篩選流程...", expanded=True)
        try:
            # Step 1: Init API (Fresh instance)
            status.write("🔄 正在初始化 API 與確認合約...")
            api = init_shioaji()
            
            if not api:
                status.update(label="❌ API 連線失敗", state="error")
            else:
                # Step 2: Load Candidates
                status.write("📂 讀取監控清單...")
                candidates_df = pd.read_csv(config.CANDIDATE_LIST_PATH)
                all_codes = candidates_df['stock_code'].astype(str).str.strip().tolist()
                
                # Convert to Contracts
                status.write(f"📜 轉換合約物件 (共 {len(all_codes)} 檔)...")
                contracts = []
                contract_info = {} # Map: code -> {name, reference}
                for code in all_codes:
                    try:
                        # Try TSE first (上市)
                        symbol = f"TSE{code}"
                        c = getattr(api.Contracts.Stocks.TSE, symbol, None)
                        if not c:
                            # Try OTC (上櫃)
                            symbol = f"OTC{code}"
                            c = getattr(api.Contracts.Stocks.OTC, symbol, None)
                        
                        if c:
                            contracts.append(c)
                            contract_info[code] = {
                                "name": c.name,
                                "reference": float(c.reference) if c.reference else 0.0
                            }
                        else:
                            status.write(f"⚠️ 找不到 {code} 的合約 (TSE/OTC 都查無)")
                    except (KeyError, AttributeError) as e:
                        status.write(f"⚠️ 查詢 {code} 時發生錯誤: {e}")
                        continue
                
                if not contracts:
                    status.update(label="❌ 找不到任何合約 (請檢查 API 初始化)", state="error")
                else:
                    # Step 3: Fetch Snapshots
                    status.write(f"☁️ 正在抓取個股報價 (Snapshots，共 {len(contracts)} 檔)...")
                    snapshots = fetch_snapshots_parallel(api, contracts, chunk_size=300, max_workers=2)
                    
                    if not snapshots:
                        status.update(label="⚠️ 取得 0 筆行情，可能是非盤中時間", state="error")
                    else:
                        status.write(f"✅ 成功取得 {len(snapshots)} 筆行情資料")
                        # Step 4: Filter Logic
                        status.write("⚡ 執行跳空邏輯運算...")
                        gap_list = []
                        gap_data = []
                        
                        for snap in snapshots:
                            code = snap.code
                            open_ = snap.open
                            
                            # Expert Optimization: Use Static Reference instead of calculated one
                            info = contract_info.get(code, {})
                            ref_price = info.get("reference", 0.0)
                            name = info.get("name", code)
                            
                            if ref_price > 0 and open_ > 0:
                                pct = (open_ - ref_price) / ref_price
                                if pct >= 0.01:
                                    gap_list.append(code)
                                    gap_data.append({
                                        "代碼": code,
                                        "名稱": name,
                                        "開盤": open_,
                                        "昨收": ref_price,
                                        "漲幅%": f"{pct*100:.2f}%"
                                    })
                        
                        # Step 5: Update
                        st.session_state.monitoring_list = gap_list
                        st.session_state.gap_df = pd.DataFrame(gap_data)
                        
                        status.update(label=f"✅ 篩選完成! 符合: {len(gap_list)} 檔", state="complete")
                        
                        if gap_list:
                            st.success(f"已更新監控名單，共 {len(gap_list)} 檔符合開盤跳空 > 1%")
                            st.write(st.session_state.gap_df)
                        else:
                            st.warning("沒有股票符合開盤跳空 > 1% 條件")

        except Exception as e:
             status.update(label=f"❌ 發生錯誤: {e}", state="error")

    st.divider()
    
    # 4. Monitor Control
    if not st.session_state.monitoring:
        if st.button("開始監控 (Start)", type="primary"):
            st.session_state.monitoring = True
            st.rerun()
    else:
        if st.button("停止監控 (Stop)"):
            st.session_state.monitoring = False
            st.rerun()
            
    st.divider()
    st.write("目前狀態:", "🟢 監控中" if st.session_state.monitoring else "🔴 已停止")
    
    st.divider()
    
    # 4. Simulation (After Market)
    st.header("歷史回放模組")
    now_time = datetime.datetime.now().time()
    close_time = datetime.time(13, 30)
    
    if now_time >= close_time:
        sim_limit = st.number_input("測試檔數限制 (0=全部)", min_value=0, value=10, step=10)
        
        # Start/Stop Logic
        if st.session_state.get('sim_state', 'IDLE') == 'IDLE':
            if st.button("啟動回放測試 (Start)"):
                st.session_state.sim_state = 'RUNNING'
                st.session_state.simulation_limit = sim_limit
                st.session_state.monitoring = False
                st.rerun()
        else:
            if st.button("⚠️ 結束回放 (Exit Simulation)", type="primary"):
                st.session_state.sim_state = 'IDLE'
                st.rerun()
    else:
        st.caption("⚠️ 須於收盤後 (13:30) 開放")

# Main Area
if st.session_state.monitoring:
    # --- NON-BLOCKING LOOP SIMULATION ---
    # We run ONE iteration then use st.rerun() after sleep?
    # No, that refreshes the whole page.
    # Better: A while loop inside a st.empty container?
    
    placeholder = st.empty()
    log_placeholder = st.empty()
    
    # Initialize API with Health Check
    api = get_valid_api()
    
    if not api:
        st.error("API 初始化失敗，請檢查 login.json")
        st.session_state.monitoring = False
    else:
        st.write("🔄 Step 1: 開始新一輪監控掃描...")
        # Load Candidates
        # To strictly implement "Low > PrevHigh", we need PrevHigh data.
        # I'll update Pre-process logic later. For now, logic:
        # Load candidate list
        try:
            candidates_df = pd.read_csv(config.CANDIDATE_LIST_PATH)
            stock_codes = candidates_df['stock_code'].astype(str).str.strip().tolist()
            
            # Map bias and prev_high
            # candidates_df columns: stock_code, bias, prev_high
            bias_map_val = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['bias']))
            
            if 'prev_high' in candidates_df.columns:
                prev_high_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['prev_high']))
            else:
                st.warning("⚠️ 監控清單缺少 'prev_high' 欄位，請重新執行盤前運算。目前暫用昨收代替。")
                prev_high_map = {}

            # --- FETCH SNAPSHOT (MOCKING REAL DATA FOR NOW IF MARKET CLOSED) ---
            # If simulation=True, api.snapshots might return mock or nothing depending on time.
            
            # Load candidate list if monitoring list is not set (First Run)
            if not st.session_state.monitoring_list or len(st.session_state.monitoring_list) == 0:
                st.session_state.monitoring_list = stock_codes 
            
            # Ensure current_monitor_codes is defined every run
            current_monitor_codes = st.session_state.monitoring_list
            st.write(f"✅ Step 1 完成: 載入監控名單共 {len(current_monitor_codes)} 檔")

            contracts = []
            pending_removal = []

            # Reset discarded count if clean start
            if 'discarded_count' not in st.session_state:
                st.session_state.discarded_count = 0
            if 'retry_counts' not in st.session_state:
                st.session_state.retry_counts = {}
                
            # Filter out those already discarded or invalid contracts (though list is codes)
            
            # Dynamic Batching of REMAINING targets

                
                # Build Contracts Object List
                contract_info = {} # Map: code -> {name, reference}
                for code in current_monitor_codes:
                     try:
                         # Try TSE first (上市)
                         symbol = f"TSE{code}"
                         c = getattr(api.Contracts.Stocks.TSE, symbol, None)
                         if not c:
                             # Try OTC (上櫃)
                             symbol = f"OTC{code}"
                             c = getattr(api.Contracts.Stocks.OTC, symbol, None)
                         
                         if c:
                             contracts.append(c)
                             contract_info[code] = {
                                 "name": c.name,
                                 "reference": float(c.reference) if c.reference else 0.0
                             }
                     except (KeyError, AttributeError) as e:
                         continue
                
            st.write(f"✅ Step 2 完成: 成功取得 Contract 物件共 {len(contracts)} 筆")
            
            # DEBUG: Check if we have contracts
            if len(contracts) == 0:
                 st.error(f"❌ 嚴重錯誤: 找不到任何 Contract 物件! (監控清單: {len(current_monitor_codes)} 筆)")
                 
                 # Detailed Diagnostics
                 st.write("--- 診斷資訊 ---")
                 try:
                     st.write(f"API Connected: {api.list_accounts()}")
                     tse_check = api.Contracts.Stocks['2330']
                     st.write(f"TSE Check (2330): {'✅ Found' if tse_check else '❌ Not Found'}")
                     otc_check = api.Contracts.Stocks['8069']
                     st.write(f"OTC Check (8069): {'✅ Found' if otc_check else '❌ Not Found'}")
                     
                     st.write(f"Total Stocks in API: {len([x for x in api.Contracts.Stocks])}")
                 except Exception as e:
                     st.write(f"Diagnostics Failed: {e}")
                 
                 st.info("💡 請嘗試重新整理網頁 (F5) 以重新觸發 init_shioaji 合約下載流程。")
            
            # Use new parallel fetch helper (High Performance Mode)
            st.write("🔄 Step 3: 正在向 API 請求行情 (Snapshots)...")
            snapshots = fetch_snapshots_parallel(api, contracts, chunk_size=300, max_workers=2)
            st.write(f"✅ Step 3 完成: API 回傳 {len(snapshots)} 筆行情資料")

                
            # --- PROCESS & FILTER ---
            kept_codes = []
            
            if len(snapshots) == 0:
                st.warning(f"⚠️ 警告: 取得 0 筆行情資料 (預期: {len(contracts)} 筆)")
            else:
                # DEBUG: Show first returned item data
                chk = snapshots[0]
                st.info(f"🔎 DEBUG Data Validation: Code={chk.code} | Open={chk.open} | Close={chk.close} | Vol={chk.total_volume} | Time={datetime.datetime.now().strftime('%H:%M:%S')}")

                for snap in snapshots:
                     code = snap.code
                     
                     # Expert Optimization: Use Static Reference instead of calculated one
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
                         # No data yet? Keep it safe.
                         kept_codes.append(code)
                         continue

                     # Expert Advice: Use Static Reference when available
                     # Using prev_high from candidate list as the primary threshold
                     # But we'll also keep prev_close as a secondary reference
                     prev_close = ref_price if ref_price > 0 else (close - (snap.change_price or 0))
                     prev_high = prev_high_map.get(code, prev_close)
                     bias_val = bias_map_val.get(code, 0)
                     
                     # --- FILTERING LOGIC (Open-Gap) ---
                     # Rule: IF Volume > 0 (Opened), MUST meet Gap Condition.
                     # Gap Cond: Open > PrevHigh * 1.01 (User said "Gap")
                     # Actually user requirement: "base_gap = (low > prev_high) & (open_ > prev_high * 1.01)"
                     # Wait, Low isn't set at very first tick usually or equal to Open.
                     # Let's use strict GAP check on OPEN price first.
                     
                     # DEBUG TRACE specific stock
                     if code == '8048':
                         print(f"DEBUG[8048]: Open={open_}, PrevHigh={prev_high}, Threshold={prev_high*1.01}, Vol={vol}")

                     
                     if vol > 0:
                         # Has opened
                         is_gap = (open_ > prev_high * 1.01)
                         
                         if not is_gap:
                             # Sanity Check: Ensure valid Open price
                             if open_ <= 0:
                                 # Bad data (0), treat as not opened yet or error, do not increment retry
                                 kept_codes.append(code)
                                 continue

                             # Retry Mechanism (Double Confirmation)
                             # If gap condition fails, increment failure count. Only discard after N failures.
                             fail_count = st.session_state.retry_counts.get(code, 0) + 1
                             st.session_state.retry_counts[code] = fail_count
                             
                             if fail_count >= 3:
                                 # 3 strikes, you're out
                                 pending_removal.append(code)
                                 # Cleanup retry dict to save mem? Optional.
                             else:
                                 # Give another chance
                                 kept_codes.append(code)
                             
                             continue # Skip further processing for this tick
                         else:
                             # Keep
                             kept_codes.append(code)
                     else:
                         # Not opened yet, keep waiting
                         kept_codes.append(code)
                         continue # No price to analyze yet
                     
                     # If we are here, it is a GAP stock (or pre-open check passed?)
                     # Proceed to 'Active' Check
                     
                     # Call Shared Logic
                     is_active, features, p_loc, cond_gap = strategy.check_criteria(snap, prev_high, bias_val)
                     
                     row = {
                        "時間": datetime.datetime.now().strftime("%H:%M:%S"),
                        "代碼": code,
                        "名稱": name,
                        "現價": close,
                        "跳空%": f"{((open_ - prev_close)/prev_close)*100:.2f}%",
                        "P-Loc": f"{p_loc:.2f}",
                        "乖離率": f"{bias_val:.2%}",
                        "量能": f"{vol}張",
                        "特徵": " ".join(features)
                     }
                     
                     if is_active:
                         active_data.append(row)
                         notifier.notify_signal(code, name, close, (open_ - prev_close)/prev_close, p_loc, vol, amt)
                         if 'triggered_history' not in st.session_state:
                             st.session_state.triggered_history = set()
                         st.session_state.triggered_history.add(code)
                         
                     elif 'triggered_history' in st.session_state and code in st.session_state.triggered_history:
                         if not features: row['特徵'] = "(轉弱觀察)"
                         watchlist_data.append(row)
                     
                     if cond_gap:
                         gap_candidates_data.append(row)

                # UPDATE STATE LIST
                # Actually we constructed 'kept_codes' but we iterate snapshots which might be partial if error?
                # Safer: Remove 'pending_removal' from session_state list
                if pending_removal:
                    st.session_state.discarded_count += len(pending_removal)
                    st.session_state.monitoring_list = [c for c in st.session_state.monitoring_list if c not in pending_removal]
                    # st.toast(f"已剔除 {len(pending_removal)} 檔無跳空個股")

                # Update Display Frames
                if active_data:
                    st.session_state.active_df = pd.DataFrame(active_data)
                else:
                    st.session_state.active_df = pd.DataFrame(columns=["代碼", "名稱", "現價", "跳空%", "P-Loc", "乖離率", "量能", "特徵"])
                    
                if watchlist_data:
                    st.session_state.watchlist_df = pd.DataFrame(watchlist_data)
                else:
                    st.session_state.watchlist_df = pd.DataFrame(columns=["代碼", "名稱", "現價", "跳空%", "P-Loc", "乖離率", "量能", "特徵"])
                
                if gap_candidates_data:
                     st.session_state.gap_df = pd.DataFrame(gap_candidates_data)
                else:
                     st.session_state.gap_df = pd.DataFrame(columns=["代碼", "名稱", "現價", "跳空%", "P-Loc", "乖離率", "量能", "特徵"])
            
            # Display
            # Split View
            placeholder.empty() # Clear previous
            with placeholder.container():
                # Status Banner
                st.info(f"📊 監控狀態: 剩餘 {len(st.session_state.monitoring_list)} 檔 | 已過濾剔除 {st.session_state.discarded_count} 檔")
                
                st.subheader("🔥 目前強勢區 (Active Matches)")
                st.dataframe(st.session_state.active_df, use_container_width=True)
                
                st.divider()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("👀 轉弱觀察區 (Watchlist)")
                    st.caption("曾經符合條件，目前暫時轉弱之標的")
                    st.dataframe(st.session_state.watchlist_df, use_container_width=True)
                
                with col2:
                    st.subheader("🪜 符合跳空 (Gap Candidates)")
                    st.caption("開盤跳空 > 1% (可能因量能/位階未入選)")
                    st.dataframe(st.session_state.gap_df, use_container_width=True)
                
            st.success(f"最近一次更新: {datetime.datetime.now().strftime('%H:%M:%S')}")
            
            # Loop delay
            time.sleep(60) 
            st.rerun()

        except Exception as e:
            st.error(f"監控執行錯誤: {e}")
            st.session_state.monitoring = False

else:
    st.info("請點擊左側「開始監控」按鈕")
    if 'active_df' in st.session_state and not st.session_state.active_df.empty:
        st.write("📝 活躍中 (Active):")
        st.dataframe(st.session_state.active_df)
    if 'watchlist_df' in st.session_state and not st.session_state.watchlist_df.empty:
        st.write("👀 觀察中 (Watchlist):")
        st.dataframe(st.session_state.watchlist_df)
    if 'gap_df' in st.session_state and not st.session_state.gap_df.empty:
        st.write("🪜 符合跳空 (Gap Candidates):")
        st.dataframe(st.session_state.gap_df)

# --- Simulation Logic ---
# State Machine: IDLE -> RUNNING -> FINISHED -> IDLE

if 'sim_state' not in st.session_state:
    st.session_state.sim_state = 'IDLE'

# Check Sidebar Start (Update logic up there or handle purely by state)
# We need to rely on the sidebar button setting the state to RUNNING.

if st.session_state.sim_state == 'RUNNING':
    st.info("🔵 正在執行歷史回放模式...")
    
    # Containers
    status_text = st.empty()
    progress_bar = st.progress(0)
    sim_table = st.empty()
    
    # Init API
    api = init_shioaji()
    
    try:
        candidates_df = pd.read_csv(config.CANDIDATE_LIST_PATH)
        
        # Containers for Split View
        st.subheader("🔥 模擬-目前強勢區")
        active_table = st.empty()
        
        st.divider()
        
        st.subheader("👀 模擬-轉弱觀察區")
        watchlist_table = st.empty()
        
        def on_status_update(msg):
            status_text.write(msg)
            
        def on_match_found(active_list, watchlist_list):
            # Update Tables
            if active_list:
                active_table.dataframe(pd.DataFrame(active_list))
            else:
                active_table.dataframe(pd.DataFrame(columns=["時間", "代碼", "名稱", "現價", "跳空%", "P-Loc", "乖離率", "量能", "特徵"]))
                
            if watchlist_list:
                watchlist_table.dataframe(pd.DataFrame(watchlist_list))
            else:
                watchlist_table.dataframe(pd.DataFrame(columns=["時間", "代碼", "名稱", "現價", "跳空%", "P-Loc", "乖離率", "量能", "特徵"]))
            
        import simulation_runner
        
        limit_val = st.session_state.get('simulation_limit', 10)
        
        simulation_runner.run_simulation_for_ui(
            api, 
            candidates_df, 
            status_callback=on_status_update,
            match_callback=on_match_found,
            progress_bar=progress_bar,
            limit=limit_val
        )
        
        # Transition to finished (keep last state)
        st.session_state.sim_state = 'FINISHED'
        # We don't save full snapshot history to state for simplicity, just IDLE logic
        # OR we could save the last frame if we want to show it in FINISHED state.
        # But 'FINISHED' state just shows "Sim Complete". 
        # Actually user wants to see the FINAL state.
        st.rerun()
        
    except Exception as e:
        st.error(f"模擬失敗: {e}")
        if st.button("返回"):
            st.session_state.sim_state = 'IDLE'
            st.rerun()

elif st.session_state.sim_state == 'FINISHED':
    st.success("模擬執行完畢！(請看上方最後狀態)")
    
    if st.button("退出模擬模式 (Exit)"):
        st.session_state.sim_state = 'IDLE'
        st.session_state.monitoring = False 
        st.rerun()
