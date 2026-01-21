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
    kbars = api.kbars(contract=contract, start=target_date, end=target_date)
    df = pd.DataFrame({**kbars})
    print("First 3 rows Volume:")
    print(df['Volume'].head(3).tolist())
    print("Last 3 rows Volume:")
    print(df['Volume'].tail(3).tolist())
    api.logout()

if __name__ == "__main__":
    test_stock_units("1569")
    test_stock_units("2363")
