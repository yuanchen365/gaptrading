import sys
import os
import logging
from modules.tsm_premium import TSMPremiumMonitor
import config

# Setup logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting TSMC Premium Monitor Dry Run...")
    
    # Check Finlab Token
    if not config.CONFIG.get("finlab_token"):
        token = os.environ.get("FINLAB_TOKEN")
        if token:
            config.CONFIG["finlab_token"] = token
            logger.info("Loaded Finlab Token from Env.")
        else:
            logger.warning("No Finlab Token found. Verification might fail if Finlab data is needed.")

    monitor = TSMPremiumMonitor()
    
    # 1. Test Fetch Data
    logger.info("Step 1: Fetching Data...")
    try:
        data = monitor.fetch_data()
        if data:
            logger.info(f"Data Fetched Successfully:")
            logger.info(f"  TSM Price: {data.get('tsm_price')}")
            logger.info(f"  TWD Rate: {data.get('twd_rate')}")
            logger.info(f"  TW Price (2330): {data.get('tw_price')}")
            logger.info(f"  TSM Date: {data.get('tsm_date')}")
            logger.info(f"  TW Date: {data.get('tw_date')}")
        else:
            logger.error("Fetch Data returned None.")
            return
    except Exception as e:
        logger.error(f"Fetch Data Exception: {e}")
        return

    # 2. Test Calculation
    logger.info("Step 2: Calculating Historical Premium...")
    try:
        hist = monitor.calculate_historical_premium(data['tw_series'])
        if hist is not None:
             logger.info("Calculation Successful:")
             logger.info(f"  MA20: {hist['MA20']:.2f}%")
             logger.info(f"  Upper: {hist['Upper']:.2f}%")
             logger.info(f"  Lower: {hist['Lower']:.2f}%")
             
             # Spot Premium Calc for verify
             tsm = data['tsm_price']
             twd = data['twd_rate']
             tw = data['tw_price']
             spot_premium = ((tsm * twd / 5) - tw) / tw * 100
             logger.info(f"  Spot Premium (Calculated): {spot_premium:.2f}%")
        else:
            logger.error("Calculate Historical Premium returned None.")
    except Exception as e:
        logger.error(f"Calculation Exception: {e}")

    logger.info("Dry Run Completed.")

if __name__ == "__main__":
    main()
