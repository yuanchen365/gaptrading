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
    
    # --- Strategy 1: Bias Selection ---
    # Calculate MA60
    ma60 = close.rolling(config.BIAS_WINDOW).mean()
    
    # Calculate Bias (乖離率)
    bias = (close - ma60) / ma60
    
    # Get the latest bias values properties
    latest_bias = bias.iloc[-1].dropna()
    
    # 確保 high 的索引與 latest_bias 一致 (Yesterday's High)
    # 這裡直接取最後一天的 High (作為這策略判斷的基準日)
    latest_high = high.iloc[-1]

    print(f"Total stocks with valid bias: {len(latest_bias)}")
    
    # Rank stocks by Bias (ascending)
    ranked_bias = latest_bias.sort_values()
    
    # Select bottom 60%
    n_candidates_bias = int(len(ranked_bias) * config.BIAS_PERCENTILE)
    candidates_bias = ranked_bias.head(n_candidates_bias).index.tolist()
    print(f"Selected {len(candidates_bias)} candidates from Bias Strategy (Bottom {config.BIAS_PERCENTILE:.0%}).")

    # --- Strategy 2: MA Convergence ---
    ma5 = close.rolling(5).mean().iloc[-1]
    ma10 = close.rolling(10).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    
    # Concat MAs to calculate convergence
    # We want stocks where (Max(MA) - Min(MA)) / Min(MA) <= Threshold
    ma_df = pd.concat([ma5, ma10, ma20], axis=1)
    ma_df.columns = ['MA5', 'MA10', 'MA20']
    ma_df = ma_df.dropna()
    
    max_ma = ma_df.max(axis=1)
    min_ma = ma_df.min(axis=1)
    convergence_rate = (max_ma - min_ma) / min_ma
    
    threshold = getattr(config, 'MA_CONVERGENCE_THRESHOLD', 0.05)
    candidates_ma_conv = convergence_rate[convergence_rate <= threshold].index.tolist()
    print(f"Selected {len(candidates_ma_conv)} candidates from MA Convergence Strategy (Threshold {threshold:.0%}).")
    
    # --- Merge Candidates ---
    all_candidates = list(set(candidates_bias + candidates_ma_conv))
    print(f"Total unique candidates after merging: {len(all_candidates)}")
    
    # Extract Data for Output
    # We need to make sure we have data for all selected candidates
    # Use latest_bias and latest_high for values. 
    # Note: Some MA candidates might not be in latest_bias if data is missing, so we use reindex carefully.
    
    final_bias = latest_bias.reindex(all_candidates)
    final_high = latest_high.reindex(all_candidates)
    
    # Fill NaN if necessary (though they should exist if they passed the filter)
    # However, MA strategy filters based on MA presence, Bias on MA60 presence. 
    # If a stock is new (<60 days), it might have MA20 but not MA60. 
    # For now, we keep NaN in bias if it's missing, or fill with 0 to safely export.
    final_bias = final_bias.fillna(0)
    final_high = final_high.reindex(all_candidates).fillna(0) 

    # Determine Strategy Tags
    strategy_tags = []
    set_bias = set(candidates_bias)
    set_ma = set(candidates_ma_conv)
    
    for code in all_candidates:
        tags = []
        if code in set_bias:
            tags.append("bias")
        if code in set_ma:
            tags.append("ma_conv")
        strategy_tags.append("|".join(tags))

    # Get date from latest data available
    data_date = bias.index[-1].strftime('%Y-%m-%d')
    print(f"Data Date: {data_date}")

    # Output to CSV
    output_df = pd.DataFrame({
        'stock_code': all_candidates,
        'bias': final_bias.values,
        'prev_high': final_high.values,
        'strategy_tag': strategy_tags,
        'data_date': data_date
    })
    
    # Ensure data directory exists
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    output_df.to_csv(config.CANDIDATE_LIST_PATH, index=False)
    print(f"Saved candidate list to {config.CANDIDATE_LIST_PATH}")
    
    return all_candidates

if __name__ == "__main__":
    try:
        get_candidates()
    except Exception as e:
        print(f"Error in pre_process: {e}")
