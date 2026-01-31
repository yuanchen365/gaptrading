import yfinance as yf
import pandas as pd
import datetime
import logging
import sys
from pathlib import Path

# Ensure root directory is in path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

import config
try:
    from line_notifier import notifier
except ImportError:
    notifier = None

try:
    import finlab
    from finlab import data
    finlab.login(config.CONFIG.get("finlab_token"))
except ImportError:
    finlab = None

logger = logging.getLogger(__name__)

class TSMPremiumMonitor:
    def __init__(self):
        self.tsm_ticker = "TSM"
        self.twd_ticker = "TWD=X"
        self.tw_stock_id = "2330"

    def fetch_data(self):
        """Fetch data from yfinance and finlab."""
        try:
            # 1. Fetch US Data (TSM, TWD=X)
            # Fetch extra days for safety
            us_data = yf.download([self.tsm_ticker, self.twd_ticker], period="1mo", progress=False)
            
            # yfinance returns MultiIndex columns if multiple tickers. 
            # Structure: ('Close', 'TSM'), ('Close', 'TWD=X')
            # Extract Close prices
            if isinstance(us_data.columns, pd.MultiIndex):
               close_df = us_data['Close']
            else:
                # Fallback if structure is different
                close_df = us_data
            
            # Get latest available US Close (Yesterday's close from perspective of TW Open)
            # If running at 08:30 TW Time (UTC+8), US market (UTC-4/5) just closed.
            # We want the last valid data point.
            last_tsm = close_df[self.tsm_ticker].dropna().iloc[-1]
            last_twd = close_df[self.twd_ticker].dropna().iloc[-1]
            last_date_us = close_df[self.tsm_ticker].dropna().index[-1]
            
            # 2. Fetch TW Data (2330)
            if finlab:
                # Fetch meaningful history for BB calculation (Need at least 20 days)
                # However, for the premium HISTORY calculate, we need aligned data.
                # Let's fetch 60 days to be safe.
                tw_close = data.get('price:收盤價')
                tw_2330 = tw_close['2330'].dropna()
                last_2330 = tw_2330.iloc[-1]
                last_date_tw = tw_2330.index[-1]
            else:
                logger.error("Finlab not available.")
                return None

            return {
                "tsm_price": last_tsm,
                "twd_rate": last_twd,
                "tw_price": last_2330,
                "tsm_date": last_date_us,
                "tw_date": last_date_tw,
                "tw_series": tw_2330
            }

        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return None
    
    def calculate_historical_premium(self, tw_series):
        """
        Calculate historical premium for BB.
        This is tricky because we need historical TSM and TWD data aligned with TW data.
        For simplicity in this V1, let's fetch historical TSM/TWD from yfinance 
        and align via Date Index.
        """
        try:
            # Fetch 3 months of history
            history = yf.download([self.tsm_ticker, self.twd_ticker], period="3mo", progress=False)['Close']
            
            # Convert YF index (TimeZone aware) to TimeZone naive to match Finlab usually
            history.index = history.index.tz_localize(None)
            
            # Align TSM, TWD, and 2330
            df = pd.DataFrame({
                'TSM': history[self.tsm_ticker],
                'TWD': history[self.twd_ticker],
                '2330': tw_series
            }).dropna()
            
            # Premium Formula: ((TSM * TWD / 5) - 2330) / 2330 * 100
            df['Premium'] = ((df['TSM'] * df['TWD'] / 5) - df['2330']) / df['2330'] * 100
            
            # Calculate BB
            df['MA20'] = df['Premium'].rolling(window=20).mean()
            df['STD20'] = df['Premium'].rolling(window=20).std()
            df['Upper'] = df['MA20'] + 1 * df['STD20']
            df['Lower'] = df['MA20'] - 1 * df['STD20']
            
            return df.iloc[-1] # Return latest calc (which effectively is "Yesterday's" premium context)
            
        except Exception as e:
            logger.error(f"Error calculating historical premium: {e}")
            return None

    def run(self):
        logger.info("Running TSMC ADR Premium Monitor...")
        data_latest = self.fetch_data()
        if not data_latest:
            logger.error("Failed to fetch latest data.")
            return

        # Calculate Spot Premium (Today's Pre-open snapshot)
        # TSM (US Close yesterday) vs 2330 (TW Close yesterday)
        # Note: Ideally we want to compare TSM (Overnight) vs 2330 (Yesterday Close) 
        # to guide Today's Open.
        
        tsm = data_latest['tsm_price']
        twd = data_latest['twd_rate']
        tw = data_latest['tw_price']
        
        spot_premium = ((tsm * twd / 5) - tw) / tw * 100
        
        # Get Historical Context (BB)
        # We use the dataset up to yesterday to define the Bands
        hist_metrics = self.calculate_historical_premium(data_latest['tw_series'])
        
        if hist_metrics is None:
            logger.error("Failed to calculate historical metrics.")
            return

        ma20 = hist_metrics['MA20']
        upper = hist_metrics['Upper']
        lower = hist_metrics['Lower']
        std = hist_metrics['STD20']
        
        # Determine Signal
        if spot_premium > upper:
            signal = "LONG"
            advice = "多頭修正訊號 (Long)"
            desc = "建議買進台股大盤/2330。捕捉溢價回歸動能，目標持有至 T+10。"
        elif spot_premium < lower:
            signal = "SHORT"
            advice = "空頭避險訊號 (Short)"
            desc = "建議放空台股大盤/期貨。屬極短線避險，目標 T+3 必須回補。"
        else:
            signal = "NEUTRAL"
            advice = "中性觀望 (Neutral)"
            desc = "目前無統計優勢。建議維持現有部位，不進行加碼。"

        # Generate Message
        self.send_notification(spot_premium, hist_metrics, signal, advice, desc, data_latest)
        
    def send_notification(self, current_premium, hist, signal, advice, desc, raw_data):
        if not notifier:
            logger.warning("Notification skipped (notifier not available).")
            return

        # Colors
        color_map = {
            "LONG": "#d32f2f", # Red
            "SHORT": "#388e3c", # Green
            "NEUTRAL": "#fbc02d" # Yellow/Amber
        }
        theme_color = color_map.get(signal, "#000000")
        
        # Construct Flex Message
        contents = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "TSMC ADR 溢價監控",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1DB446"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    # Section 1: Data
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                             {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "TSM Close", "size": "sm", "color": "#555555", "flex": 1},
                                    {"type": "text", "text": f"{raw_data['tsm_price']:.2f}", "size": "sm", "weight": "bold", "align": "end", "flex": 1}
                                ]
                             },
                             {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "USD/TWD", "size": "sm", "color": "#555555", "flex": 1},
                                    {"type": "text", "text": f"{raw_data['twd_rate']:.2f}", "size": "sm", "weight": "bold", "align": "end", "flex": 1}
                                ]
                             },
                             {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "2330 Close", "size": "sm", "color": "#555555", "flex": 1},
                                    {"type": "text", "text": f"{raw_data['tw_price']:.0f}", "size": "sm", "weight": "bold", "align": "end", "flex": 1}
                                ]
                             }
                        ]
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    # Section 2: Premium & Channel
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"溢價率: {current_premium:.2f}%",
                                "size": "xl",
                                "weight": "bold",
                                "align": "center",
                                "color": theme_color
                            },
                             {
                                "type": "text",
                                "text": f"MA20: {hist['MA20']:.2f}% | Upper: {hist['Upper']:.2f}% | Lower: {hist['Lower']:.2f}%",
                                "size": "xxs",
                                "color": "#aaaaaa",
                                "align": "center",
                                "margin": "sm"
                            }
                        ]
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    # Section 3: Advice
                     {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": advice,
                                "weight": "bold",
                                "size": "md",
                                "color": theme_color,
                                "wrap": True
                            },
                            {
                                "type": "text",
                                "text": desc,
                                "size": "sm",
                                "color": "#666666",
                                "wrap": True,
                                "margin": "sm"
                            }
                        ]
                    },
                     # Section 4: Risk
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "backgroundColor": "#FFEBEE",
                        "cornerRadius": "md",
                        "paddingAll": "md",
                        "contents": [
                             {
                                "type": "text",
                                "text": "風險預警",
                                "weight": "bold",
                                "size": "xs",
                                "color": "#D32F2F"
                            },
                             {
                                "type": "text",
                                "text": "停損參考 (MDD): 多 -2.02% / 空 -2.75%",
                                "size": "xxs",
                                "color": "#D32F2F",
                                "wrap": True
                            }
                        ]
                    }
                ]
            }
        }
        
        notifier.send_flex_message(f"TSMC ADR 溢價: {current_premium:.2f}% - {advice}", contents)

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    monitor = TSMPremiumMonitor()
    monitor.run()
