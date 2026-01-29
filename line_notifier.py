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

    def send_flex_message(self, alt_text, contents):
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
                    "type": "flex",
                    "altText": alt_text,
                    "contents": contents
                }
            ]
        }
        
        try:
            r = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload)
            if r.status_code == 200:
                print("LINE Flex Message sent.")
            else:
                print(f"Failed to send LINE: {r.status_code} {r.text}")
        except Exception as e:
            print(f"Error sending LINE: {e}")

    def notify_signal(self, stock_code, name, price, gap, p_loc, volume, amount, has_future=False):
        self._reset_cache_if_new_day()
        
        if stock_code in self.sent_today:
            print(f"Skipping duplicate notification for {stock_code}")
            return

        amt_e = round(amount / 100_000_000, 2)
        gap_pct = round(gap * 100, 2)
        
        # Color Logic
        header_color = "#D32F2F" if gap_pct >= 3 else "#F57C00" # High urgency Red if >3%, else Orange
        p_loc_color = "#2E7D32" if p_loc > 0.8 else "#1976D2" # Green for strong, Blue for normal
        
        # Badges
        badges = []
        if has_future:
             # Text component does not support backgroundColor directly in checking structure sometimes, use box wrapper or simplified style. 
             # Actually "text" component doesn't have backgroundColor property. "span" does not either.
             # We must use a Box to wrap the Text if we want background color, OR use a linear gradient background for bubble but that's for whole container.
             # Correct approach for badge: Box (layout: baseline/horizontal) -> Text.
             # BUT simpler approach for badges in a horizontal row: 
             # Using a Box with backgroundColor and cornerRadius, containing the Text.
             badges.append({
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "期", "color": "#FFFFFF", "size": "xs", "weight": "bold", "align": "center"}
                ],
                "backgroundColor": "#E65100",
                "cornerRadius": "2px",
                "paddingAll": "2px",
                "width": "20px",
                "height": "20px",
                "justifyContent": "center",
                "alignItems": "center",
                "margin": "sm"
             })
        
        # Determine Strategy Source
        badges.append({
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "多方", "color": "#FFFFFF", "size": "xs", "weight": "bold", "align": "center"}
            ],
            "backgroundColor": "#C62828",
            "cornerRadius": "2px",
            "paddingAll": "2px",
            "width": "35px",
            "height": "20px",
            "justifyContent": "center",
            "alignItems": "center",
            "margin": "sm"
        })

        flex_contents = {
          "type": "bubble",
          "size": "giga",
          "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
              {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                  {
                    "type": "text",
                    "text": "🚨 訊號觸發",
                    "color": "#ffffff",
                    "weight": "bold",
                    "size": "lg"
                  },
                  {
                    "type": "text",
                    "text": datetime.datetime.now().strftime("%H:%M:%S"),
                    "color": "#ffffff",
                    "size": "sm",
                    "align": "end",
                    "gravity": "center"
                  }
                ]
              }
            ],
            "backgroundColor": header_color,
            "paddingAll": "12px"
          },
          "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
              {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                  {
                    "type": "text",
                    "text": f"{stock_code} {name}",
                    "weight": "bold",
                    "size": "xl", # Reduced from xl to lg to fit better? Keep xl for emphasis
                    "flex": 1,
                    "color": "#000000"
                  }
                ],
                "alignItems": "center"
              },
              {
                 "type": "box",
                 "layout": "horizontal",
                 "contents": badges,
                 "margin": "sm"
              },
              {
                "type": "separator",
                "margin": "md",
                "color": "#BDBDBD"
              },
              {
                "type": "box",
                "layout": "vertical",
                "margin": "md",
                "spacing": "sm",
                "contents": [
                  {
                    "type": "box",
                    "layout": "baseline",
                    "contents": [
                      {"type": "text", "text": "現價", "color": "#757575", "size": "sm", "flex": 2},
                      {"type": "text", "text": f"{price}", "weight": "bold", "size": "lg", "flex": 4, "color": "#D32F2F"},
                      {"type": "text", "text": f"(+{gap_pct}%)", "size": "sm", "color": "#D32F2F", "flex": 3, "align": "end"}
                    ]
                  },
                  {
                    "type": "box",
                    "layout": "baseline",
                    "contents": [
                      {"type": "text", "text": "P-Loc", "color": "#757575", "size": "sm", "flex": 2},
                      {"type": "text", "text": f"{p_loc:.2f}", "weight": "bold", "size": "md", "flex": 4, "color": p_loc_color}
                    ]
                  },
                  {
                    "type": "box",
                    "layout": "baseline",
                    "contents": [
                      {"type": "text", "text": "量能", "color": "#757575", "size": "sm", "flex": 2},
                      {"type": "text", "text": f"{int(volume):,}張", "size": "sm", "flex": 4, "color": "#424242"},
                      {"type": "text", "text": f"({amt_e}億)", "size": "sm", "flex": 3, "align": "end", "color": "#616161"}
                    ]
                  }
                ]
              }
            ]
          },
          "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
              {
                "type": "button",
                "action": {
                  "type": "uri",
                  "label": "查看 K 線圖 (Trend)",
                  "uri": f"https://www.cnyes.com/twstock/{stock_code}/charts/technical-history"
                },
                "style": "secondary",
                "height": "sm",
                "color": "#E0E0E0"
              }
            ],
            "paddingAll": "10px"
          },
          "styles": {
             "footer": {
                "separator": False
             }
          }
        }
        
        alt_msg = f"觸發: {stock_code} {name} 現價:{price} (+{gap_pct}%)"
        self.send_flex_message(alt_msg, flex_contents)
        self.sent_today.add(stock_code)

notifier = LineNotifier()
