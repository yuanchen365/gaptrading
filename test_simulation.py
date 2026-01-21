"""
回測模組測試腳本
用於驗證 simulation.py 的功能
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import datetime
import pandas as pd
import config
from modules.api_manager import init_shioaji
from modules.contract_resolver import resolve_contracts
from modules.simulation import run_simulation


class MockSessionState:
    """模擬 Streamlit session state"""
    def __init__(self):
        self.monitoring_list = []
        self.active_df = pd.DataFrame()
        self.watchlist_df = pd.DataFrame()
        self.gap_df = pd.DataFrame()
        self.retry_counts = {}
        self.triggered_history = set()


def test_simulation():
    print("=" * 60)
    print("🧪 回測模組測試")
    print("=" * 60)
    
    # 1. Initialize API
    print("\n📡 Step 1: 初始化 API...")
    api = init_shioaji()
    if not api:
        print("❌ API 初始化失敗")
        return
    print("✅ API 初始化成功")
    
    # 2. Load candidate list
    print("\n📂 Step 2: 載入候選清單...")
    try:
        candidates_df = pd.read_csv(config.CANDIDATE_LIST_PATH)
        print(f"✅ 載入 {len(candidates_df)} 檔候選股票")
        
        # Use first 3 stocks for testing
        test_codes = candidates_df['stock_code'].astype(str).head(3).tolist()
        print(f"🎯 測試標的: {test_codes}")
        
        bias_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['bias']))
        prev_high_map = dict(zip(candidates_df['stock_code'].astype(str), candidates_df['prev_high']))
        
    except Exception as e:
        print(f"❌ 載入失敗: {e}")
        return
    
    # 3. Resolve contracts
    print("\n📜 Step 3: 取得合約資訊...")
    contracts, contract_info = resolve_contracts(api, test_codes)
    print(f"✅ 成功取得 {len(contracts)} 個合約")
    
    # 4. Run simulation
    print("\n🎬 Step 4: 開始回測...")
    print("-" * 60)
    
    session_state = MockSessionState()
    
    try:
        results = run_simulation(
            api=api,
            monitoring_list=test_codes,
            prev_high_map=prev_high_map,
            bias_map=bias_map,
            contract_info=contract_info,
            target_date=datetime.datetime.now().date(),
            session_state=session_state,
            status_widget=None,
            speed=0.1  # Faster for testing
        )
        
        print("-" * 60)
        print("\n✅ 回測完成！")
        print(f"📊 統計結果:")
        print(f"   - 總時間點: {results['total_minutes']} 分鐘")
        print(f"   - 最高強勢股: {results['max_active']} 檔")
        print(f"   - 最高觀察: {results['max_watchlist']} 檔")
        print(f"   - 最高跳空候選: {results['max_gap']} 檔")
        
        # Show timeline sample
        if results['timeline']:
            print(f"\n📈 時間軸範例 (前 5 筆):")
            for entry in results['timeline'][:5]:
                print(f"   {entry['time'].strftime('%H:%M')} - 強勢:{entry['active']} 觀察:{entry['watchlist']} 跳空:{entry['gap']}")
        
    except Exception as e:
        print(f"❌ 回測失敗: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("🏁 測試結束")
    print("=" * 60)


if __name__ == "__main__":
    test_simulation()
