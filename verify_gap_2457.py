
import shioaji as sj
import pandas as pd
import config
import sys

def verify_gap():
    print("--- Verifying Gap Logic for Stock 2457 ---")
    
    # 1. Get PrevHigh from CSV
    try:
        df = pd.read_csv(config.CANDIDATE_LIST_PATH)
        row = df[df['stock_code'].astype(str) == '2457']
        if row.empty:
            print("Stock 2457 not found in candidate list!")
            return
        prev_high = float(row['prev_high'].iloc[0])
        print(f"1. Historical Data (from CSV):")
        print(f"   Stock: 2457")
        print(f"   PrevHigh (Yesterday's High): {prev_high}")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # 2. Login to Shioaji
    api = sj.Shioaji(simulation=True)
    if "api_key" in config.CONFIG and "secret_key" in config.CONFIG:
        api.login(
            api_key=config.CONFIG["api_key"], 
            secret_key=config.CONFIG["secret_key"]
        )
        print("   Login Successful")
    else:
        print("   Login Failed: Missing keys in config")
        return

    # 3. Get Real-time Snapshot
    contract = api.Contracts.Stocks.get('2457')
    if not contract:
        print("   Contract not found!")
        return
        
    print("2. Fetching Real-time Data...")
    snapshots = api.snapshots([contract])
    if not snapshots:
        print("   No snapshot data returned.")
        return
        
    snap = snapshots[0]
    date = snap.ts 
    # Open and Low
    open_price = snap.open
    low_price = snap.low
    close_price = snap.close
    
    print(f"   Current Price: {close_price}")
    print(f"   Today's Open: {open_price}")
    print(f"   Today's Low:  {low_price}")
    
    # 4. Strict Gap Logic
    # Strict Gap: (Low > PrevHigh) & (Open > PrevHigh * 1.01)
    
    print("\n3. Verifying Logic:")
    print(f"   Rule 1: Low ({low_price}) > PrevHigh ({prev_high}) ?")
    cond_low = low_price > prev_high
    print(f"     -> {'PASS' if cond_low else 'FAIL'}")
    
    print(f"   Rule 2: Open ({open_price}) > PrevHigh * 1.01 ({prev_high * 1.01:.2f}) ?")
    cond_open = open_price > (prev_high * 1.01)
    print(f"     -> {'PASS' if cond_open else 'FAIL'}")
    
    is_gap = cond_low and cond_open
    print(f"\n   RESULT: Strict Gap Condition is {'MET' if is_gap else 'NOT MET'}")

if __name__ == "__main__":
    verify_gap()
