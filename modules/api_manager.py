"""
API Manager Module
管理 Shioaji API 的初始化、健康檢查與快照抓取
"""
import streamlit as st
import shioaji as sj
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import config


@st.cache_resource(ttl=3600*4)  # Cache for 4 hours
def init_shioaji():
    """
    初始化 Shioaji API 並確保合約已下載
    """
    try:
        api = sj.Shioaji(simulation=False)
        
        # Login
        if "api_key" in config.CONFIG and "secret_key" in config.CONFIG:
            api.login(
                api_key=config.CONFIG["api_key"],
                secret_key=config.CONFIG["secret_key"]
            )
        
        # Validate Contracts (Blocking Wait)
        has_contracts = False
        if hasattr(api, 'Contracts'):
            try:
                if api.Contracts.Stocks["2330"]:
                    has_contracts = True
            except:
                pass
        
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
    """
    取得 API 實例並確保健康狀態
    如果偵測到快取失效，會自動重新初始化
    """
    api = init_shioaji()
    if not api:
        return None
    
    # Strict Health Check
    is_healthy = False
    try:
        if api.Contracts.Stocks["2330"]:
            is_healthy = True
    except:
        pass
    
    if not is_healthy:
        st.warning("⚠️ 偵測到 API 快照失效 (合約庫遺失)，正在重置連線...")
        st.cache_resource.clear()
        time.sleep(1)
        return init_shioaji()
    
    return api


def fetch_snapshots_parallel(api, contracts, chunk_size=300, max_workers=2):
    """
    使用多執行緒並行抓取快照資料
    
    Args:
        api: Shioaji API 實例
        contracts: Contract 物件列表
        chunk_size: 每批次大小
        max_workers: 最大執行緒數
    
    Returns:
        List[Snapshot]: 快照資料列表
    """
    # Split contracts into chunks
    chunks = [contracts[i:i+chunk_size] for i in range(0, len(contracts), chunk_size)]
    
    snapshots = []
    
    def fetch_chunk_with_retry(api, chunk, chunk_id):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                res = api.snapshots(chunk)
                if res:
                    return res
            except Exception:
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
