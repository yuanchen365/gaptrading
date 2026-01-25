import config

def check_criteria(snapshot_data, prev_high, bias_val, has_future=False):
    """
    Evaluates if a stock snapshot meets the strategy criteria.
    
    Args:
        snapshot_data (dict or object): Must contain:
            - close, open, high, low, total_volume, total_amount, prev_close
            (Note: if passing an object, enable attribute access)
        prev_high (float): Yesterday's High.
        bias_val (float): Pre-calculated Bias.
        has_future (bool): Whether the stock has futures.
        
    Returns:
        tuple: (is_active, features_list, p_loc)
    """
    
    # Duck typing: support both dict and object (Shioaji Snapshot)
    def get_val(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        else:
            return getattr(obj, key, 0)

    close = get_val(snapshot_data, 'close')
    if close == 0: return False, [], 0
    
    open_ = get_val(snapshot_data, 'open')
    high = get_val(snapshot_data, 'high')
    low = get_val(snapshot_data, 'low')
    vol = get_val(snapshot_data, 'total_volume')
    amt = get_val(snapshot_data, 'total_amount')
    
    # 1. GAP Logic
    # Strict Gap: Low >= PrevHigh AND Open > PrevHigh * 1.01
    cond_gap = (low >= prev_high) and (open_ > prev_high * 1.01)
    
    # 2. P-Loc Logic
    if (high - low) == 0:
        p_loc = 0.0
    else:
        p_loc = (close - low) / (high - low + 0.00001)
        
    cond_ploc = p_loc > config.P_LOC_THRESHOLD
    
    # 3. Volume Logic
    # 這裡直接使用「張」進行比較 (根據測試，本系統傳入的 vol 基準已統一為「張」)
    cond_vol = (vol >= config.MIN_VOLUME_SHEETS) and (amt >= config.MIN_AMOUNT_TWD)
    
    is_active = cond_gap and cond_ploc and cond_vol
    
    # Features Tagging
    features = []
    if has_future:
        features.append("⚡有股期")

    if p_loc >= 0.95:
        features.append("🔥S6_極強勢")
    elif p_loc >= 0.8:
        features.append("S6_區間突破")
        
    # Bias tagging (Optional, purely descriptive)
    # if bias_val < -0.2: features.append("極低基期")
    
    return is_active, features, p_loc, cond_gap
