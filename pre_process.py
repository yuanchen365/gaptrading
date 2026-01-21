import pandas as pd
import finlab
from finlab import data
import config
from pathlib import Path

def get_candidates():
    print("Connecting to FinLab...")
    # Try to log in if API token is in config, otherwise rely on environment
    if "finlab_token" in config.CONFIG:
        finlab.login(config.CONFIG["finlab_token"])

    print("Fetching data...")
    # Get Close Price and High Price
    close = data.get('price:收盤價')
    high = data.get('price:最高價')
    
    # Calculate MA60
    ma60 = close.rolling(config.BIAS_WINDOW).mean()
    
    # Calculate Bias (乖離率)
    bias = (close - ma60) / ma60
    
    # Get the latest bias values properties
    latest_bias = bias.iloc[-1].dropna()
    
    # Get latest High (Yesterday's High)
    # Align high with latest_bias index
    latest_high = high.iloc[-1].reindex(latest_bias.index)
    
    print(f"Total stocks with valid bias: {len(latest_bias)}")
    
    # Rank stocks by Bias (ascending)
    ranked_bias = latest_bias.sort_values()
    
    # Select bottom 60%
    n_candidates = int(len(ranked_bias) * config.BIAS_PERCENTILE)
    candidates = ranked_bias.head(n_candidates)
    
    # Filter corresponding Highs
    candidate_highs = latest_high.loc[candidates.index]
    
    print(f"Selected {len(candidates)} candidates (Bottom {config.BIAS_PERCENTILE:.0%}).")

    # Get date
    data_date = latest_bias.name.strftime('%Y-%m-%d')
    print(f"Data Date: {data_date}")

    # Output to CSV
    output_df = pd.DataFrame({
        'stock_code': candidates.index,
        'bias': candidates.values,
        'prev_high': candidate_highs.values,
        'data_date': data_date
    })
    
    # Ensure data directory exists
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    output_df.to_csv(config.CANDIDATE_LIST_PATH, index=False)
    print(f"Saved candidate list to {config.CANDIDATE_LIST_PATH}")
    
    return candidates.index.tolist()

if __name__ == "__main__":
    try:
        get_candidates()
    except Exception as e:
        print(f"Error in pre_process: {e}")
