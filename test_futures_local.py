
import unittest
from unittest.mock import MagicMock
import sys
from pathlib import Path
import pandas as pd

# Setup path
sys.path.append(str(Path(__file__).resolve().parent))

from modules.contract_resolver import resolve_contracts

class TestFuturesLocal(unittest.TestCase):
    def test_local_csv_loading(self):
        print("\nTesting local CSV loading for Futures check...")
        
        # known stocks with futures (from our previous look at CSV): 2330(TSMC), 2603(Evergreen), 2317(HonHai)
        # known stocks WITHOUT futures: 8069(E Ink - Row 169 has ●? Wait. Let's check CSV content again if unsure. 
        # Actually 8069 has ● in col 2. So it HAS future.)
        # Let's pick one that likely doesn't. 
        # Looking at CSV: 1102(Asia Cement) has ●.
        # Let's try 9999 (Not in list)
        
        target_codes = ['2330', '2603', '9999'] 
        
        # Mock API
        mock_api = MagicMock()
        # Mock Contracts Structure
        # 2330 -> TSE
        mock_2330 = MagicMock()
        mock_2330.name = "台積電"
        mock_2330.reference = 1000.0
        
        mock_2603 = MagicMock()
        mock_2603.name = "長榮"
        mock_2603.reference = 200.0
        
        mock_9999 = MagicMock()
        mock_9999.name = "未知股"
        mock_9999.reference = 50.0

        # Assign to api structure
        mock_api.Contracts.Stocks.TSE.TSE2330 = mock_2330
        mock_api.Contracts.Stocks.TSE.TSE2603 = mock_2603
        mock_api.Contracts.Stocks.TSE.TSE9999 = mock_9999 # Fake stock that exists but no future
        
        # Run Resolver
        contracts, info = resolve_contracts(mock_api, target_codes, show_warnings=True)
        
        print("Results:")
        for code in target_codes:
            has_fut = info[code]['has_future']
            print(f"Stock {code}: Has Future = {has_fut}")
            
            if code == '2330':
                self.assertTrue(has_fut, "2330 should have future")
            elif code == '2603':
                self.assertTrue(has_fut, "2603 should have future")
            elif code == '9999':
                self.assertFalse(has_fut, "9999 should NOT have future")

    def test_csv_existence(self):
        csv_path = Path("data/stock_futures_list.csv")
        self.assertTrue(csv_path.exists(), "CSV file must exist")
        print(f"CSV file found at {csv_path.absolute()}")

if __name__ == '__main__':
    unittest.main()
