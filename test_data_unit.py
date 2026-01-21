import shioaji as sj
import pandas as pd
import datetime
import json
import os

def test_stock_units(stock_code="2363"):
    print(f"\n{'='*20} Testing {stock_code} {'='*20}")
    
    login_path = "login.json"
    with open(login_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
        
    api = sj.Shioaji(simulation=True)
    api.login(api_key=config_data["api_key"], secret_key=config_data["secret_key"])
    
    target_date = "2026-01-21" # Use a fixed date to be sure
    
    # Try TSE/OTC
    contract = None
    for ex in [api.Contracts.Stocks.TSE, api.Contracts.Stocks.OTC]:
        contract = getattr(ex, f"{stock_code}", None)
        if contract: break
        # Try with prefix
        contract = getattr(ex, f"TSE{stock_code}", None)
        if contract: break
        contract = getattr(ex, f"OTC{stock_code}", None)
        if contract: break

    if not contract:
        print(f"Error: Contract {stock_code} not found")
        api.logout()
        return
        
    kbars = api.kbars(contract=contract, start=target_date, end=target_date)
    if not kbars:
        print("Error: No KBar data")
        api.logout()
        return
        
    df = pd.DataFrame({**kbars})
    
    # Take one sample bar
    sample = df.iloc[0]
    p = sample['Close']
    v = sample['Volume']
    a = sample['Amount']
    
    print(f"Sample Bar (09:01):")
    print(f"  Price: {p}")
    print(f"  Volume (Raw): {v}")
    print(f"  Amount (Raw): {a}")
    
    calc_val = p * v
    print(f"  Price * Volume = {calc_val}")
    print(f"  Ratio (Amount / (Price*Volume)): {a/calc_val if calc_val != 0 else 0:.4f}")
    
    total_v = df['Volume'].sum()
    total_a = df['Amount'].sum()
    print(f"\nWhole Day Totals:")
    print(f"  Total Volume (Raw): {total_v}")
    print(f"  Total Amount (Raw): {total_a}")
    
    api.logout()

if __name__ == "__main__":
    test_stock_units("2363")
    test_stock_units("1569")
