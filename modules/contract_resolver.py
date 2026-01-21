"""
Contract Resolver Module
處理 Shioaji 合約查詢邏輯，支援 TSE/OTC 自動切換
"""
from typing import List, Dict, Tuple, Any


def resolve_contracts(api, stock_codes: List[str], show_warnings: bool = False) -> Tuple[List, Dict]:
    """
    將股票代碼轉換為 Shioaji Contract 物件
    
    Args:
        api: Shioaji API 實例
        stock_codes: 股票代碼列表 (純數字，如 ['2330', '8069'])
        show_warnings: 是否顯示警告訊息（用於 Streamlit UI）
    
    Returns:
        (contracts, contract_info)
        - contracts: Contract 物件列表
        - contract_info: Dict[code] -> {name, reference}
    """
    contracts = []
    contract_info = {}
    failed_codes = []
    
    for code in stock_codes:
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
                contract_info[code] = {
                    "name": c.name,
                    "reference": float(c.reference) if c.reference else 0.0
                }
            else:
                failed_codes.append(code)
                
        except (KeyError, AttributeError) as e:
            failed_codes.append(code)
            if show_warnings:
                print(f"⚠️ 查詢 {code} 時發生錯誤: {e}")
            continue
    
    # Summary
    if show_warnings and failed_codes:
        print(f"⚠️ 以下 {len(failed_codes)} 檔無法取得合約: {', '.join(failed_codes[:10])}")
        if len(failed_codes) > 10:
            print(f"   ... 及其他 {len(failed_codes) - 10} 檔")
    
    return contracts, contract_info
