"""一時利用スクリプト: LINE公式アカウントの友だち一覧からuserIdを取得する。

broadcast配信（友だち全員に届く）からpush配信（指定ユーザーだけに届く）へ
切り替えるため、運用者自身のuserIdを1回だけ特定する目的で使う。
役目を終えたら削除してよい。
"""

import os

import requests

token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
resp = requests.get(
    "https://api.line.me/v2/bot/followers/ids?limit=300",
    headers={"Authorization": f"Bearer {token}"},
    timeout=15,
)
resp.raise_for_status()
data = resp.json()
user_ids = data.get("userIds", [])
print(f"friends count: {len(user_ids)}")
for uid in user_ids:
    print(uid)
