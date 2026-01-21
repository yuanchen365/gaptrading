import yfinance as yf
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal

@dataclass
class MockSnapshot:
    code: str
    open: float
    close: float
    high: float
    low: float
    change_price: float
    total_volume: int
    name: str = ""

def get_yfinance_data(stock_codes: List[str]) -> List[MockSnapshot]:
    """
    獲取 Yahoo Finance 資料並模擬成 Shioaji Snapshot 格式。
    台灣上市代號後綴 .TW, 上櫃 .TWO
    """
    if not stock_codes:
        return []

    # 1. 格式化代碼 (yfinance 需要後綴)
    # 簡單判斷：通常 4 碼且開頭非 00 的可能是上市或上櫃
    # 這裡採簡單邏輯：我們先嘗試判斷，或者併用 .TW / .TWO
    # 實務上我們可以用一個清單判斷，或是嘗試抓取。
    
    formatted_codes = []
    symbol_to_original = {}
    
    for code in stock_codes:
        # 去除可能的前後空格
        code = str(code).strip()
        
        # 判斷邏輯：
        # 長度 4 碼通常是個股，長度超過 4 碼可能是 ETF 或權證
        # 這裡為了準確度，我們可能需要一個對照表。
        # 但如果是「備援」，我們可以用一個較通用的方式：
        # 嘗試先用 .TW (上市)，如果不對再考慮 .TWO
        # 這裡簡化處理：假設用戶知道或我們預設加上後綴
        # 更好的做法是在讀取 candidate_list 時就有標註
        
        # 暫時邏輯：先全部嘗試 .TW，如果失敗再補抓 (此處為示意，優化後改為併行)
        # 為了效能，一次抓取全部
        t_code = f"{code}.TW"
        formatted_codes.append(t_code)
        symbol_to_original[t_code] = code
        
        # 上櫃備選
        o_code = f"{code}.TWO"
        formatted_codes.append(o_code)
        symbol_to_original[o_code] = code

    print(f"🌐 [Fallback] 正在從 Yahoo Finance 抓取 {len(stock_codes)} 檔資料...")
    
    try:
        # 下載最新 1 天資料，間隔 1 分鐘獲取最新現價
        data = yf.download(formatted_codes, period="1d", interval="1m", group_by='ticker', progress=False)
        
        snapshots = []
        
        for ticker in formatted_codes:
            if ticker not in data.columns.levels[0]:
                continue
                
            df = data[ticker]
            if df.empty:
                continue
                
            last_row = df.iloc[-1]
            first_row = df.iloc[0] # 取今日第一根 1m K當作開盤價參考
            
            # yfinance 欄位: Open, High, Low, Close, Adj Close, Volume
            # 計算 change_price (現價 - 昨收)
            # 注意: yfinance 的 'Open' 在 1m interval 是該分鐘開盤
            # 若要真正的今日開盤，需取當日第一筆
            
            # 昨收在 yfinance 比較難直接取得，我們可以用 Adj Close 或者從 API 拿
            # fallback 暫時用 Close - (當日漲跌) 
            # 簡化: yfinance 本身有 info 屬性可以看到昨收，但效能較慢
            
            # 我們嘗試抓取今日開盤 (第一筆 1m K 的 Open)
            day_open = df['Open'].iloc[0]
            current_price = last_row['Close']
            
            # Mocking Snapshot
            orig_code = symbol_to_original[ticker]
            
            # 避免重複 (因為我們同時抓了 .TW 和 .TWO)
            # 如果已經有該代碼的資料且有效，就跳過
            if any(s.code == orig_code for s in snapshots):
                continue
            
            if pd.isna(current_price) or current_price == 0:
                continue

            snap = MockSnapshot(
                code=orig_code,
                open=float(day_open),
                close=float(current_price),
                high=float(df['High'].max()),
                low=float(df['Low'].min()),
                change_price=0.0, # 暫時不提供準確漲跌值，僅供跳空運算
                total_volume=int(df['Volume'].sum()),
                name=orig_code
            )
            snapshots.append(snap)
            
        print(f"✅ [Fallback] 成功抓取 {len(snapshots)} 筆資料")
        return snapshots
        
    except Exception as e:
        print(f"❌ [Fallback] Yahoo Finance 抓取失敗: {e}")
        return []

if __name__ == "__main__":
    # 測試
    res = get_yfinance_data(["2330", "8069", "2454"])
    for r in res:
        print(r)
