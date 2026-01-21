import shioaji as sj
import json
import os

def test_snapshot_units(stock_code="1569"):
    print(f"\n{'='*20} Testing Snapshot Units: {stock_code} {'='*20}")
    
    # Load login info
    login_path = "login.json"
    if not os.path.exists(login_path):
        print("Error: login.json not found")
        return
        
    with open(login_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
        
    api = sj.Shioaji(simulation=True)
    api.login(api_key=config_data["api_key"], secret_key=config_data["secret_key"])
    
    # Get contract
    contract = None
    # Try OTC first as 1569 is likely OTC
    contract = getattr(api.Contracts.Stocks.OTC, f"OTC{stock_code}", None)
    if not contract:
        contract = getattr(api.Contracts.Stocks.TSE, f"TSE{stock_code}", None)
        
    if not contract:
        print(f"Error: Could not find contract for {stock_code}")
        api.logout()
        return
        
    print(f"Found Contract: {contract.name} ({contract.code})")
    print(f"Reference Price: {contract.reference}")
    
    # Fetch Snapshot
    snapshots = api.snapshots([contract])
    if not snapshots:
        print("Error: No snapshot data returned from API")
        api.logout()
        return
        
    snap = snapshots[0]
    
    print("\n--- Raw Snapshot Data ---")
    print(f"  Code: {snap.code}")
    print(f"  Close: {snap.close}")
    print(f"  Total Volume (Raw): {snap.total_volume}")
    print(f"  Total Amount (Raw): {snap.total_amount}")
    
    print("\n--- Unit Analysis (for Taiwan Stocks) ---")
    sheets = snap.total_volume / 1000
    avg_price = snap.total_amount / snap.total_volume if snap.total_volume > 0 else 0
    
    print(f"  Volume in Sheets (/1000): {sheets:,.2f} 張")
    print(f"  Total Amount: {snap.total_amount:,.0f} 元")
    print(f"  Amount in 億 (Approx): {snap.total_amount / 100_000_000:.4f} 億")
    print(f"  Calculated Avg Price: {avg_price:.2f}")
    
    # Logout
    api.logout()
    print("\n=== Test Finished ===")

if __name__ == "__main__":
    test_snapshot_units("1569")
