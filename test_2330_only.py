import shioaji as sj
import json
import os

def test_single(stock_code):
    print(f"\n--- {stock_code} ---")
    with open("login.json", 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    api = sj.Shioaji(simulation=True)
    api.login(api_key=config_data["api_key"], secret_key=config_data["secret_key"])
    
    contract = getattr(api.Contracts.Stocks.TSE, f"TSE{stock_code}", None)
    if not contract:
        contract = getattr(api.Contracts.Stocks.OTC, f"OTC{stock_code}", None)
    
    snap = api.snapshots([contract])[0]
    print(f"Name: {contract.name}")
    print(f"Price: {snap.close}")
    print(f"Vol (Raw): {snap.total_volume}")
    print(f"Amt (Raw): {snap.total_amount}")
    if snap.total_volume > 0:
        print(f"Avg Price: {snap.total_amount / snap.total_volume:.2f}")
    api.logout()

if __name__ == "__main__":
    test_single("2330")
