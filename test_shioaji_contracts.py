import shioaji as sj
import config
import time

def on_contract_download(status):
    print(f"Callback 狀態: {status}")

def test_contracts():
    print("🚀 初始化 Shioaji API (模擬模式)...")
    api = sj.Shioaji(simulation=True)
    
    print("🔑 嘗試登入...")
    api.login(
        api_key=config.CONFIG["api_key"], 
        secret_key=config.CONFIG["secret_key"]
    )
    print("✅ 登入指令已發送")

    # Set callback
    api.set_context(on_contract_download)

    print("⬇️ 執行 fetch_contracts(contract_download=True)...")
    api.fetch_contracts(contract_download=True)
    
    print("⏳ 等待 30 秒讓合約下載與索引建立...")
    for i in range(30):
        if i % 5 == 0: print(f"   ...已等待 {i} 秒")
        time.sleep(1)
        
    print("\n📊 檢查合約庫狀態:")
    
    # 1. Check Stocks Length
    try:
        # Note: Shioaji StreamStockContracts might not support len() directly depending on version,
        # but iterating or converting to list usually works for debug.
        stock_count = 0
        for _ in api.Contracts.Stocks:
            stock_count += 1
        print(f"   [API.Contracts.Stocks] 總數量 (Iterator): {stock_count}")
        
    except Exception as e:
        print(f"   [Error] 無法計算 Stocks 數量: {e}")

    # 2. Check Specific Targets
    targets = {
        "2330 (上市台積電)": "2330",
        "2881 (上市富邦金)": "2881",
        "8069 (上櫃元太)": "8069",
        "6547 (上櫃高端疫苗)": "6547",
        "6418 (上櫃詠昇)": "6418"
    }
    
    print("\n🎯 個股查詢測試:")
    for name, code in targets.items():
        try:
            c = api.Contracts.Stocks[code]
            print(f"   ✅ 成功找到 {name}: {c}")
        except Exception:
            print(f"   ❌ 找不到 {name}")

    # 3. Check Futures just in case
    try:
        fut_count = 0
        for _ in api.Contracts.Futures:
            fut_count += 1
        print(f"\n   [API.Contracts.Futures] 總數量: {fut_count}")
    except: pass

    # 4. Check OTC explicitly if it exists (some versions)
    if hasattr(api.Contracts, 'OTC'):
        print("\n   [Info] 發現 api.Contracts.OTC 屬性!")
        try:
             otc_c = api.Contracts.OTC["8069"]
             print(f"   ✅ 從 OTC 屬性找到元太: {otc_c}")
        except:
             print("   ❌ 從 OTC 屬性也找不到元太")
    else:
        print("\n   [Info] 此版本 API 無 api.Contracts.OTC 屬性")

if __name__ == "__main__":
    test_contracts()
