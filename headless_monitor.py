import time
import datetime
import pandas as pd
import sys
import logging
import os
import shioaji as sj
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.append(str(Path(__file__).resolve().parent))

try:
    import config
    import pre_process
    from modules.contract_resolver import resolve_contracts
    from modules.api_manager import fetch_snapshots_parallel
    from modules.monitor_loop import run_monitoring_iteration
    from modules.tsm_premium import TSMPremiumMonitor
except ImportError as e:
    logger.error(f"Import failed: {e}")
    sys.exit(1)

# Mock Streamlit session state
class MockSessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

# Inject Env Vars into Config
if "line_channel_access_token" not in config.CONFIG and os.environ.get("LINE_TOKEN"):
    config.CONFIG["line_channel_access_token"] = os.environ.get("LINE_TOKEN")
if "line_user_id" not in config.CONFIG and os.environ.get("LINE_USER_ID"):
    config.CONFIG["line_user_id"] = os.environ.get("LINE_USER_ID")
if "finlab_token" not in config.CONFIG and os.environ.get("FINLAB_TOKEN"):
    config.CONFIG["finlab_token"] = os.environ.get("FINLAB_TOKEN")


def init_shioaji_headless():
    """Initialize Shioaji API in headless mode with robust contract fetching"""
    logger.info("Initializing Shioaji API...")
    
    api_key = os.environ.get("SHIOAJI_API_KEY") or config.CONFIG.get("api_key")
    secret_key = os.environ.get("SHIOAJI_SECRET_KEY") or config.CONFIG.get("secret_key")

    if not api_key or not secret_key:
        logger.error("Missing API Key or Secret Key (Check env vars or config.py)")
        return None

    try:
        api = sj.Shioaji(simulation=False)
        api.login(api_key=api_key, secret_key=secret_key)
        logger.info("Login successful.")

        # Check contracts
        has_contracts = False
        if hasattr(api, 'Contracts'):
            try:
                if api.Contracts.Stocks["2330"]:
                    has_contracts = True
            except:
                pass
        
        if not has_contracts:
            logger.info("Contracts not ready, downloading...")
            api.fetch_contracts(contract_download=True)
            
            # Wait for contracts (max 60s)
            for i in range(60):
                time.sleep(1)
                try:
                    if api.Contracts.Stocks["2330"]:
                        logger.info("Contracts loaded.")
                        has_contracts = True
                        break
                except:
                    pass
            
            if not has_contracts:
                logger.error("Failed to download contracts within 60s.")
                return None
                
        return api
    except Exception as e:
        logger.error(f"API Initialization failed: {e}")
        return None

def main():
    logger.info("=== Starting GapTrading Automation ===")
    
    # 1. Run Pre-process (FinLab)
    logger.info("[Step 1] Running FinLab Pre-process...")
    try:
        # Check env var for token if not in config
        if not config.CONFIG.get("finlab_token") and os.environ.get("FINLAB_TOKEN"):
             config.CONFIG["finlab_token"] = os.environ.get("FINLAB_TOKEN")

        pre_process.get_candidates()
        logger.info("Pre-process completed.")
    except Exception as e:
        logger.error(f"Pre-process failed: {e}")
        # We might want to continue if the file already exists, but for now let's exit
        sys.exit(1)

    # 2. Check Time & Wait for Open (Optional)
    # Cloud Run Job should be scheduled at ~08:55.
    
    # 1.5 Run TSM Premium Monitor (if before 09:00)
    now = datetime.datetime.now()
    if now.time() < datetime.time(9, 0):
        logger.info("[Step 1.5] Running TSMC Premium Monitor...")
        try:
            TSMPremiumMonitor().run()
        except Exception as e:
            logger.error(f"TSM Premium Monitor failed: {e}")

    # 3. Initialize API
    logger.info("[Step 2] Connecting to Shioaji...")
    api = init_shioaji_headless()
    if not api:
        logger.error("Exiting due to API failure.")
        sys.exit(1)

    # 4. Gap Filter Logic
    logger.info("[Step 3] Running Gap Filter...")
    
    # Retry loop for Gap Filter (Wait for 09:00 data)
    gap_list = []
    
    # Wait until 09:01:00 to ensure market opening volatility settles and data is ready
    now = datetime.datetime.now()
    open_time = now.replace(hour=9, minute=1, second=0, microsecond=0)
    if now < open_time:
        wait_sec = (open_time - now).total_seconds()
        logger.info(f"Waiting {wait_sec:.0f}s for market open (09:01)...")
        time.sleep(wait_sec)

    # Load Candidates
    candidates_df = pd.read_csv(config.CANDIDATE_LIST_PATH)
    all_codes = candidates_df['stock_code'].astype(str).str.strip().tolist()
    
    target_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Resolve Contracts
    contracts, contract_info = resolve_contracts(api, all_codes)
    if not contracts:
        logger.error("No contracts resolved.")
        sys.exit(1)

    # Fetch Snapshots with Retry
    max_retries = 3
    snapshots = []
    
    for attempt in range(max_retries):
        logger.info(f"Fetching snapshots attempt {attempt+1}/{max_retries}...")
        snapshots = fetch_snapshots_parallel(api, contracts, chunk_size=300)
        
        # Check if we got valid data for today
        valid_count = sum(1 for s in snapshots if datetime.datetime.fromtimestamp(s.ts / 1_000_000_000).strftime('%Y-%m-%d') == target_date_str)
        
        if valid_count > 0:
            logger.info(f"Got {valid_count} valid snapshots.")
            break
        
        logger.warning(f"No valid data yet. Waiting 30s...")
        time.sleep(30)
    
    # Filter for Gaps
    for snap in snapshots:
        # Check date freshness
        ts_date = datetime.datetime.fromtimestamp(snap.ts / 1_000_000_000).strftime('%Y-%m-%d')
        if ts_date != target_date_str:
            continue
            
        code = snap.code
        open_ = snap.open
        info = contract_info.get(code, {})
        ref_price = info.get("reference", 0.0)
        
        if ref_price > 0 and open_ > 0:
            pct = (open_ - ref_price) / ref_price
            if pct >= 0.01:
                gap_list.append(code)
    
    # Prepare Data Maps
    bias_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['bias']))
    strategy_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['strategy_tag']))
    
    if 'prev_high' in candidates_df.columns:
        prev_high_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['prev_high']))
    else:
        prev_high_map = {}
        
    # Log Gap Results with Strategy Tags
    logger.info(f"Gap Filter Result: {len(gap_list)} stocks found with Gap > 1%")
    for code in gap_list:
        tag = strategy_map.get(str(code), "unknown")
        tag_display = tag.replace("bias", "低基期").replace("ma_conv", "均線糾結").replace("|", "+")
        logger.info(f"  - [{code}] {tag_display}")

    # Initialize Session State
    session_state = MockSessionState()
    session_state.triggered_history = set()

    # Re-resolve contracts only for gap list (optimization)
    monitor_contracts, monitor_contract_info = resolve_contracts(api, gap_list)

    # Loop until 13:30
    while True:
        now = datetime.datetime.now()
        if now.time() > datetime.time(13, 35):
            logger.info("Market closed. Daily run completed.")
            break
            
        try:
            # Fetch snapshots for monitoring list
            snapshots = fetch_snapshots_parallel(api, monitor_contracts, chunk_size=300)
            
            # Run Logic
            active_df, watchlist_df, gap_df = run_monitoring_iteration(
                api,
                gap_list,
                prev_high_map,
                bias_map,
                monitor_contract_info,
                snapshots,
                session_state
            )
            
            # Log progress
            logger.info(f"Monitor Tick: Active={len(active_df)}, Watchlist={len(watchlist_df)}")
            
            # Sleep 60s
            time.sleep(60)
            
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            time.sleep(10)
            # Try to reconnect if API seems dead?
            # For now simple retry

if __name__ == "__main__":
    main()
