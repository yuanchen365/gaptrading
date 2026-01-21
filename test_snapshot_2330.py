import shioaji as sj
import json
import os

def test_snapshot_units(stock_code="2330"):
    print(f"\n{'='*20} Testing Snapshot Units: {stock_code} {'='*20}")
    
    login_path = "login.json"
    with open(login_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
        
    api = sj.Shioaji(simulation=True)
    api.login(api_key=config_data["api_key"], secret_key=config_data["secret_key"])
    
    contract = getattr(api.Contracts.Stocks.TSE, f"TSE{stock_code}", None)
    if not contract:
        contract = getattr(api.Contracts.Stocks.OTC, f"OTC{stock_code}", None)
        
    if not contract:
        print(f"Error: Could not find contract for {stock_code}")
        api.logout()
        return
        
    snapshots = api.snapshots([contract])
    if not snapshots:
        print("Error: No snapshot data")
        api.logout()
        return
        
    snap = snapshots[0]
    print(f"Found Contract: {contract.name} ({contract.code})")
    print(f"  Total Volume (Raw): {snap.total_volume}")
    print(f"  Total Amount (Raw): {snap.total_amount:,.0f}")
    
    avg_price = snap.total_amount / snap.total_volume if snap.total_volume > 0 else 0
    print(f"  Calculated Avg Price (Amt/Vol): {avg_price:,.2f}")
    
    if avg_price > 2000: # 價格異常高，表示 Vol 單位可能是「張」
        print("  => Interpretation: Volume is likely in SHEETS (張)")
    else:
        print("  => Interpretation: Volume is likely in SHARES (股)")
        
    api.logout()

if __name__ == "__main__":
    test_snapshot_units("2330")
    test_snapshot_units("1569")
