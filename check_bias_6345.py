
import finlab
from finlab import data
import pandas as pd
import config
import datetime

def check_specific_bias(target_code):
    print(f"Checking Bias for: {target_code}")
    
    if "finlab_token" in config.CONFIG:
        finlab.login(config.CONFIG["finlab_token"])
        
    # Re-run the logic partially
    close = data.get('price:收盤價')
    ma60 = close.rolling(config.BIAS_WINDOW).mean()
    bias = (close - ma60) / ma60
    
    latest_bias = bias.iloc[-1].dropna()
    
    if target_code not in latest_bias.index:
        print(f"❌ {target_code} has no bias data.")
        return

    val = latest_bias[target_code]
    rank = latest_bias.rank(pct=True)[target_code]
    
    print(f"Stock: {target_code}")
    print(f"Bias: {val:.4f}")
    print(f"Percentile Rank: {rank:.2%}")
    print(f"Threshold: {config.BIAS_PERCENTILE:.0%}")
    
    if rank <= config.BIAS_PERCENTILE:
        print("✅ Should be selected (Passed Bias check)")
    else:
        print("❌ Failed Bias check (Not low enough)")

if __name__ == "__main__":
    check_specific_bias("6345")
