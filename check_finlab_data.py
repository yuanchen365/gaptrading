
import finlab
from finlab import data
import config
import pandas as pd

def check_finlab_2457():
    print("--- Checking FinLab Data for 2457 ---")
    
    if "finlab_token" in config.CONFIG:
        finlab.login(config.CONFIG["finlab_token"])
    
    print("Fetching 'price:最高價'...")
    high = data.get('price:最高價')
    
    # Check 2457
    if '2457' in high.columns:
        s_high = high['2457'].dropna().tail(5)
        print("\nLast 5 days of High Price for 2457:")
        print(s_high)
        
        print("\nNote: 'iloc[-1]' usage in pre_process.py would take:")
        print(f"Date: {s_high.index[-1]}, Value: {s_high.iloc[-1]}")
    else:
        print("Stock 2457 not found in FinLab dataset.")

if __name__ == "__main__":
    check_finlab_2457()
