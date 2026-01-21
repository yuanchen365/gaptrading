import shioaji as sj
import pandas as pd
import datetime
import json
import os

def test_stock_units(stock_code):
    print(f"\n{'='*20} Testing {stock_code} {'='*20}")
    with open("login.json", 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    api = sj.Shioaji(simulation=True)
    api.login(api_key=config_data["api_key"], secret_key=config_data["secret_key"])
    target_date = "2026-01-21"
    contract = getattr(api.Contracts.Stocks.TSE, f"TSE{stock_code}", None)
    if not contract: contract = getattr(api.Contracts.Stocks.OTC, f"OTC{stock_code}", None)
    if not contract:
        print("Contract not found")
        api.logout()
        return
    kbars = api.kbars(contract=contract, start=target_date, end=target_date)
    if not kbars:
        print("No KBar data")
        api.logout()
        return
    df = pd.DataFrame({**kbars})
    
    # Use the LAST row to check cumulative vs sum
    v_sum = df['Volume'].sum()
    a_sum = df['Amount'].sum()
    v_last = df['Volume'].iloc[-1]
    a_last = df['Amount'].iloc[-1]
    
    # Snapshot for comparison
    snap = api.snapshots([contract])[0]
    
    print(f"Contract Name: {contract.name}")
    print(f"KBar Sum Volume: {v_sum}")
    print(f"KBar Sum Amount: {a_sum}")
    print(f"KBar Last Volume: {v_last}")
    print(f"KBar Last Amount: {a_last}")
    print(f"Snapshot Total Volume (Shares): {snap.total_volume}")
    print(f"Snapshot Total Amount (Yuan): {snap.total_amount}")
    
    # Ratios
    if v_sum > 0:
        print(f"Ratio (Snapshot Vol / KBar Sum Vol): {snap.total_volume / v_sum:.4f}")
    if a_sum > 0:
        print(f"Ratio (Snapshot Amt / KBar Sum Amt): {snap.total_amount / a_sum:.4f}")
    
    api.logout()

if __name__ == "__main__":
    # Test one TSE and one OTC
    test_stock_units("2363") # 矽統 (TSE)
    test_stock_units("1569") # 濱川 (OTC)
