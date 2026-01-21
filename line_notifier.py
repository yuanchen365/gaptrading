import requests
import datetime
import config
import json

class LineNotifier:
    def __init__(self):
        # Messaging API uses Channel Access Token
        self.token = config.CONFIG.get("line_channel_access_token")
        # Target User ID to push message to (since Push API requires a target)
        self.user_id = config.CONFIG.get("line_user_id") 
        
        self.sent_today = set()
        self.last_reset = datetime.date.today()

    def _reset_cache_if_new_day(self):
        today = datetime.date.today()
        if today > self.last_reset:
            self.sent_today.clear()
            self.last_reset = today

    def send_message(self, message):
        if not self.token or not self.user_id:
            print("Warning: Missing LINE Channel Access Token or User ID.")
            return

        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json"
        }
        
        payload = {
            "to": self.user_id,
            "messages": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }
        
        try:
            # Messaging API Push Endpoint
            r = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload)
            
            if r.status_code == 200:
                print("LINE Message sent.")
            else:
                print(f"Failed to send LINE: {r.status_code} {r.text}")
        except Exception as e:
            print(f"Error sending LINE: {e}")

    def notify_signal(self, stock_code, name, price, gap, p_loc, volume, amount):
        self._reset_cache_if_new_day()
        
        if stock_code in self.sent_today:
            print(f"Skipping duplicate notification for {stock_code}")
            return

        amt_亿 = round(amount / 100_000_000, 2)
        gap_pct = round(gap * 100, 2)
        
        msg = (
            f"🚨 強勢標的觸發\n"
            f"股票：{stock_code} {name}\n"
            f"現價：{price} (跳空 +{gap_pct}%)\n"
            f"P-Loc：{p_loc:.2f}\n"
            f"量能：{volume}張 / {amt_亿}億\n"
            f"狀態：符合 60MA 低基期排名"
        )
        
        self.send_message(msg)
        self.sent_today.add(stock_code)

notifier = LineNotifier()
