
import shioaji as sj
import pandas as pd
import config
import strategy
import sys
import json

def debug_stock(target_code):
    print(f"Debugging Stock: {target_code}")
    
    # 1. Load Candidate List
    try:
        df = pd.read_csv(config.CANDIDATE_LIST_PATH)
        # Force string match
        df['stock_code'] = df['stock_code'].astype(str)
        target_row = df[df['stock_code'] == target_code]
        
        if target_row.empty:
            print(f"❌ Stock {target_code} NOT found in candidate_list.csv")
            return
            
        print(f"✅ Found in candidate list.")
        prev_high = float(target_row.iloc[0]['prev_high'])
        bias_val = float(target_row.iloc[0]['bias'])
        print(f"   PrevHigh: {prev_high}")
        print(f"   Bias: {bias_val}")
        
    except Exception as e:
        print(f"Error reading csv: {e}")
        return

    # 2. Login Shioaji
    api = sj.Shioaji(simulation=True)
    if "api_key" in config.CONFIG:
        api.login(config.CONFIG["api_key"], config.CONFIG["secret_key"])
    else:
        print("No API Key")
        return

    # 3. Get Snapshot
    contract = api.Contracts.Stocks.get(target_code)
    if not contract:
        print("❌ Contract not found")
        return
        
    print("Fetching snapshot...")
    snapshot = api.snapshots([contract])[0]
    
    # 4. Check Criteria
    print("-" * 30)
    print("SNAPSHOT DATA:")
    print(f"Code: {snapshot.code}")
    print(f"Open: {snapshot.open}")
    print(f"High: {snapshot.high}")
    print(f"Low: {snapshot.low}")
    print(f"Close: {snapshot.close}")
    print(f"Volume: {snapshot.total_volume}")
    print(f"Amount: {snapshot.total_amount}")
    
    # Gap Check
    gap_price = prev_high * 1.01
    print("-" * 30)
    print("LOGIC CHECK:")
    print(f"1. Gap Check (Open > {gap_price:.2f}?): {snapshot.open > gap_price} (Open={snapshot.open})")
    print(f"   Low Check (Low > {prev_high}?): {snapshot.low > prev_high} (Low={snapshot.low})")
    
    # P-Loc
    if (snapshot.high - snapshot.low) == 0:
        p_loc = 0
    else:
        p_loc = (snapshot.close - snapshot.low) / (snapshot.high - snapshot.low)
    print(f"2. P-Loc Check (>{config.P_LOC_THRESHOLD}): {p_loc:.2f}")
    
    # Volume
    print(f"3. Volume Check (>={config.MIN_VOLUME_SHEETS}): {snapshot.total_volume}")
    print(f"   Amount Check (>={config.MIN_AMOUNT_TWD}): {snapshot.total_amount}")
    
    is_active, features, p_loc_cal, cond_gap = strategy.check_criteria(snapshot, prev_high, bias_val)
    print("-" * 30)
    print(f"FINAL RESULT:")
    print(f"Is Active: {is_active}")
    print(f"Cond Gap: {cond_gap}")
    print(f"Features: {features}")

if __name__ == "__main__":
    debug_stock("3645")
