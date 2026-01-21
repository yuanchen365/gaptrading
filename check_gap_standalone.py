import pandas as pd
import config
import shioaji as sj

def check_gap_standalone():
    print("🚀 啟動獨立跳空檢查模組...")
    
    # 1. Load Candidates
    try:
        df = pd.read_csv(config.CANDIDATE_LIST_PATH)
        df['stock_code'] = df['stock_code'].astype(str).str.strip()
        print(f"📂 讀取監控清單成功，共 {len(df)} 筆")
    except Exception as e:
        print(f"❌ 讀取 CSV 失敗: {e}")
        return

    # 2. Initialize Shioaji for Snapshot (Minimal Init)
    api = sj.Shioaji(simulation=True)
    if not api.login(api_key=config.CONFIG["api_key"], secret_key=config.CONFIG["secret_key"]):
        print("❌ API 登入失敗")
        return

    # 3. Check Contracts
    print("🔄 檢查合約庫...")
    # Force single check to ensure ready
    try:
        api.Contracts.Stocks["2330"]
    except:
        print("⚠️ 合約庫未就緒，嘗試下載...")
        api.fetch_contracts(contract_download=True)
        import time
        time.sleep(10)

    # 4. Fetch Snapshots & Filter
    print("☁️ 抓取即時行情 (Snapshots)...")
    
    contracts = []
    valid_codes = []
    contract_info = {} # code -> {name, reference}
    
    for code in df['stock_code'].tolist():
        try:
            # Try TSE first (上市)
            symbol = f"TSE{code}"
            c = getattr(api.Contracts.Stocks.TSE, symbol, None)
            if not c:
                # Try OTC (上櫃)
                symbol = f"OTC{code}"
                c = getattr(api.Contracts.Stocks.OTC, symbol, None)
            
            if c:
                contracts.append(c)
                valid_codes.append(code)
                contract_info[code] = {
                    "name": c.name,
                    "reference": float(c.reference) if c.reference else 0.0
                }
        except (KeyError, AttributeError) as e:
            continue
            
    if not contracts:
        print("❌ 找不到任何有效合約")
        return

    chunks = [contracts[i:i+300] for i in range(0, len(contracts), 300)]
    gap_candidates = []

    for i, chunk in enumerate(chunks):
        print(f"   -> 處理第 {i+1} 批 ({len(chunk)} 檔)...")
        snapshots = api.snapshots(chunk)
        
        for snap in snapshots:
            code = snap.code
            info = contract_info.get(code, {})
            name = info.get("name", code)
            ref_price = info.get("reference", 0.0)
            
            # Logic: (Open - Ref) / Ref > 1%
            if ref_price > 0 and snap.open > 0:
                pct = (snap.open - ref_price) / ref_price
                if pct >= 0.01:
                    print(f"   🔥 發現跳空股: {code} ({name}) | 漲幅: {pct*100:.2f}%")
                    gap_candidates.append({
                        "code": code,
                        "name": name,
                        "gap_pct": pct
                    })
    
    print(f"\n✅ 篩選完成! 共發現 {len(gap_candidates)} 檔跳空股")
    
    # Save or Return (This part is flexible, currently just printing)
    if gap_candidates:
        result_df = pd.DataFrame(gap_candidates)
        # result_df.to_csv("gap_results.csv", index=False)
        print(result_df)
    else:
        print("⚠️ 今日無符合條件個股")

if __name__ == "__main__":
    check_gap_standalone()
