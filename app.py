import streamlit as st
import pandas as pd
import time
import datetime
from pathlib import Path
import sys

# Ensure current directory is in python path
sys.path.append(str(Path(__file__).resolve().parent))

import config
import strategy
from line_notifier import notifier
from modules.api_manager import init_shioaji, get_valid_api, fetch_snapshots_parallel
from modules.gap_filter import run_gap_filter
from modules.contract_resolver import resolve_contracts
from modules.monitor_loop import run_monitoring_iteration

from modules.ui_components import apply_custom_styles, render_header

# Page Configuration
st.set_page_config(page_title="台股即時強勢跳空篩選", layout="wide")

# Apply Custom CSS Theme
apply_custom_styles()

# Helper Functions
def run_pre_process():
    import pre_process
    with st.spinner('執行盤前篩選中 (FinLab)...'):
        stock_list = pre_process.get_candidates()
    st.success(f"篩選完成！共 {len(stock_list)} 檔候選股票 (包含低基期與均線糾結)。")
    return stock_list

# --- Session State Initialization ---
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
    st.session_state.retry_counts = {}

# Custom Header
render_header()

# ===== SIDEBAR =====
with st.sidebar:
    st.title("� 控制台")
    
    # ========== SECTION 1: 系統管理 ==========
    with st.expander("⚙️ 系統管理", expanded=False):
        st.caption("API 連線與快取管理")
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🔧 清除快取", use_container_width=True, help="清除記憶體快取，修復合約遺失問題"):
                st.cache_resource.clear()
                st.success("✅ 快取已清除")
                st.rerun()
        
        with col_btn2:
            if st.button("🚪 登出 API", use_container_width=True, type="secondary", help="正確關閉 API 連線，避免連線數過多"):
                try:
                    api = init_shioaji()
                    if api:
                        api.logout()
                        st.success("✅ API 已登出")
                    
                    st.cache_resource.clear()
                    st.session_state.monitoring = False
                    
                    st.info("💡 已釋放 API 連線")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.warning(f"登出時發生錯誤: {e}")
                    st.cache_resource.clear()
                    st.rerun()
        
        # LINE Token Check
        if "line_channel_access_token" not in config.CONFIG or config.CONFIG["line_channel_access_token"] == "YOUR_CHANNEL_ACCESS_TOKEN":
            st.warning("⚠️ 請先設定 LINE Messaging API Token")
    
    st.divider()
    
    # ========== SECTION 2: 盤前準備 ==========
    st.subheader("📋 Step 1: 盤前準備")
    
    if not config.CANDIDATE_LIST_PATH.exists():
        st.warning("⚠️ 尚未建立監控清單")
        if st.button("▶️ 執行盤前運算 (FinLab)", use_container_width=True, type="primary"):
            run_pre_process()
            st.rerun()
    else:
        st.success("✅ 監控清單已就緒")
        try:
            df = pd.read_csv(config.CANDIDATE_LIST_PATH)
            
            # Data freshness check
            if 'data_date' in df.columns:
                d_date = str(df['data_date'].iloc[0])
                today_str = datetime.datetime.now().strftime('%Y-%m-%d')
                
                if d_date != today_str:
                    st.warning(f"⚠️ 資料日期 ({d_date}) 非今日 ({today_str})")
                    if st.button("🔄 重新執行盤前運算", use_container_width=True):
                        run_pre_process()
                        st.rerun()
                else:
                    st.success(f"✅ 資料日期: {d_date} (最新)")
            
            st.info(f"📊 監控檔數: {len(df)} 檔")
            
        except Exception as e:
            st.error(f"讀取清單失敗: {e}")
    
    st.divider()
    
    # ========== SECTION 3: 盤中監控 ==========
    st.subheader("📈 Step 2: 盤中監控")
    
    # Gap Filter
    if st.button("🔍 執行開盤跳空篩選 (Gap > 1%)", use_container_width=True, type="primary"):
        st.session_state.monitoring = False
        st.cache_resource.clear()
        
        status = st.status("🚀 啟動篩選流程...", expanded=True)
        try:
            status.write("🔄 正在初始化 API 與確認合約...")
            api = init_shioaji()
            
            if not api:
                status.update(label="❌ API 連線失敗", state="error")
            else:
                gap_list, gap_df = run_gap_filter(api, config.CANDIDATE_LIST_PATH, status_widget=status)
                
                st.session_state.monitoring_list = gap_list
                st.session_state.gap_df = gap_df
                
                status.update(label=f"✅ 篩選完成! 符合: {len(gap_list)} 檔", state="complete")
                
                if gap_list:
                    st.success(f"已更新監控名單，共 {len(gap_list)} 檔符合開盤跳空 > 1%")
                    st.write(gap_df)
                else:
                    st.warning("沒有股票符合開盤跳空 > 1% 條件")
                    
        except Exception as e:
            status.update(label=f"❌ 發生錯誤: {e}", state="error")
    
    st.caption("💡 先篩選出跳空股票，再啟動監控")
    
    # Monitor Control
    if not st.session_state.monitoring:
        if st.button("▶️ 開始監控 (Start)", use_container_width=True, type="primary"):
            st.session_state.monitoring = True
            st.rerun()
    else:
        if st.button("⏸️ 停止監控 (Stop)", use_container_width=True):
            st.session_state.monitoring = False
            st.rerun()
    
    # Status Indicator
    if st.session_state.monitoring:
        st.success("🟢 監控中 (每 60 秒更新)")
    else:
        st.info("🔴 已停止")
    

    
    # ========== SECTION 5: 說明文件 ==========
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


        """)


# ===== MAIN AREA =====
# Display Tables First (Always visible)
st.header("📊 即時監控面板")

# Row 1: Active Area (Full Width - Most Important)
st.subheader("🔥 目前強勢區 (Active Matches)")
st.dataframe(st.session_state.active_df, use_container_width=True, height=300)

st.divider()

# Row 2: Watchlist and Gap Candidates (Side by Side)
col1, col2 = st.columns(2)

with col1:
    st.subheader("👀 轉弱觀察區 (Watchlist)")
    st.caption("曾經符合條件，目前暫時觀察之標的")
    st.dataframe(st.session_state.watchlist_df, use_container_width=True, height=300)

with col2:
    st.subheader("📈 跳空監控池 (Gap Monitoring Pool)")
    st.caption("今日觀察的樣本總數 - 固定不變")
    st.dataframe(st.session_state.gap_df, use_container_width=True, height=300)

st.caption(f"監控樣本: {len(st.session_state.monitoring_list)} 檔 (固定) | 最近一次更新: {datetime.datetime.now().strftime('%H:%M:%S')}")

st.divider()

# Monitoring Loop (System Messages in Expander)
if st.session_state.monitoring:
    with st.expander("🔧 系統執行訊息 (System Logs)", expanded=False):
        log_container = st.container()
    
    # Initialize API
    api = get_valid_api()
    
    if not api:
        st.error("API 初始化失敗，請檢查 login.json")
        st.session_state.monitoring = False
    else:
        with log_container:
            st.write("🔄 Step 1: 開始新一輪監控掃描...")
        
        # Load candidate list
        try:
            candidates_df = pd.read_csv(config.CANDIDATE_LIST_PATH)
            stock_codes = candidates_df['stock_code'].astype(str).str.strip().tolist()
            
            # Map bias and prev_high
            bias_map_val = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['bias']))
            
            if 'prev_high' in candidates_df.columns:
                prev_high_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['prev_high']))
            else:
                with log_container:
                    st.warning("⚠️ 監控清單缺少 'prev_high' 欄位，請重新執行盤前運算。目前暫用昨收代替。")
                prev_high_map = {}

            # Load monitoring list
            if not st.session_state.monitoring_list or len(st.session_state.monitoring_list) == 0:
                st.session_state.monitoring_list = stock_codes
            
            current_monitor_codes = st.session_state.monitoring_list
            with log_container:
                st.write(f"✅ Step 1 完成: 載入監控名單共 {len(current_monitor_codes)} 檔")

            # Build Contracts
            with log_container:
                st.write("🔄 Step 2: 正在轉換合約物件...")
            contracts, contract_info = resolve_contracts(api, current_monitor_codes)
            with log_container:
                st.write(f"✅ Step 2 完成: 成功取得 Contract 物件共 {len(contracts)} 筆")
            
            if len(contracts) == 0:
                with log_container:
                    st.error(f"❌ 嚴重錯誤: 找不到任何 Contract 物件! (監控清單: {len(current_monitor_codes)} 筆)")
                    st.info("💡 請嘗試重新整理網頁 (F5) 以重新觸發 init_shioaji 合約下載流程。")
            
            # Fetch Snapshots
            with log_container:
                st.write("🔄 Step 3: 正在向 API 請求行情 (Snapshots)...")
            snapshots = fetch_snapshots_parallel(api, contracts, chunk_size=300, max_workers=2)
            with log_container:
                st.write(f"✅ Step 3 完成: API 回傳 {len(snapshots)} 筆行情資料")

            # Process & Filter
            if len(snapshots) == 0:
                with log_container:
                    st.warning(f"⚠️ 警告: 取得 0 筆行情資料 (預期: {len(contracts)} 筆)")
            else:
                # Show first item for validation
                chk = snapshots[0]
                with log_container:
                    st.info(f"🔎 DEBUG Data Validation: Code={chk.code} | Open={chk.open} | Close={chk.close} | Vol={chk.total_volume} | Time={datetime.datetime.now().strftime('%H:%M:%S')}")

                with log_container:
                    st.write("🔄 Step 4: 執行篩選邏輯...")
                
                # Run monitoring iteration
                active_df, watchlist_df, gap_df = run_monitoring_iteration(
                    api,
                    current_monitor_codes,
                    prev_high_map,
                    bias_map_val,
                    contract_info,
                    snapshots,
                    st.session_state
                )
                
                # Update display DataFrames
                st.session_state.active_df = active_df
                st.session_state.watchlist_df = watchlist_df
                st.session_state.gap_df = gap_df
                
                with log_container:
                    st.success(f"✅ Step 4 完成: 強勢股 {len(active_df)} 檔 | 觀察 {len(watchlist_df)} 檔 | 跳空候選 {len(gap_df)} 檔")
                
                # Auto-refresh after 60 seconds
                time.sleep(60)
                st.rerun()

        except Exception as e:
            with log_container:
                st.error(f"監控過程發生錯誤: {e}")
            st.session_state.monitoring = False
else:
    # When not monitoring, show placeholder
    st.info("💡 點擊側邊欄的「開始監控 (Start)」按鈕以啟動即時監控")

