"""APIキーなしで動かせるテスト（Gemini・楽天は偽物）。実行: python test_offline.py"""
import sys, types, os
from datetime import datetime, timedelta, timezone
REPO = os.path.dirname(os.path.abspath(__file__))
# --- google.genai の偽物 ---
class APIError(Exception):
    def __init__(self, code, msg): super().__init__(msg); self.code = code
class ClientError(APIError): pass
class ServerError(APIError): pass
script = []   # 呼ばれるたびに先頭を取り出す: ("ok", text) / ("err", exc)
calls = []
class Models:
    def generate_content(self, model, contents, config):
        calls.append(model); kind, v = script.pop(0)
        if kind == "err": raise v
        return types.SimpleNamespace(text=v)
class Client:
    def __init__(self, api_key): self.models = Models()
genai = types.ModuleType("google.genai"); genai.Client = Client
errors = types.ModuleType("google.genai.errors"); errors.ClientError = ClientError; errors.ServerError = ServerError
tmod = types.ModuleType("google.genai.types"); tmod.GenerateContentConfig = lambda **k: k
genai.errors, genai.types = errors, tmod
google = types.ModuleType("google"); google.genai = genai
sys.modules.update({"google": google, "google.genai": genai, "google.genai.errors": errors, "google.genai.types": tmod})
os.environ["K"] = "x"; os.environ["GEMINI_API_KEY"] = "x"
sys.path.insert(0, REPO)
import gemini_util as G
G.WAIT_SECONDS = 0
def run(seq):
    script[:] = seq; calls.clear(); return G.generate_json("K", "sys", "hi")
assert run([("err", ServerError(503, "overloaded")), ("ok", '{"a":1}')]) == {"a": 1} and calls == ["gemini-3.6-flash"] * 2
assert run([("err", ClientError(429, "RESOURCE_EXHAUSTED GenerateRequestsPerMinute")), ("ok", '{"a":2}')]) == {"a": 2}
assert run([("err", ClientError(429, "quota GenerateRequestsPerDayPerProjectPerModel")), ("ok", '{"a":3}')]) == {"a": 3} and calls == ["gemini-3.6-flash", "gemini-2.5-flash"]
assert run([("ok", ""), ("ok", '{"a":4')]+[("ok", '{"a":5}')]) == {"a": 5}          # 空の返事・壊れたJSON → 再試行
assert run([("err", ClientError(404, "model not found")), ("ok", '{"b":1}')]) == {"b": 1} and calls[1] == "gemini-2.5-flash"
try:
    run([("err", ClientError(429, "PerDay"))] * 3); raise AssertionError("止まるはず")
except G.GeminiFailed as e:
    assert "PerDay" in str(e) and calls == G.MODELS
print("gemini_util ok")
# --- 楽天ROOM の選び方 ---
sys.path.insert(0, os.path.join(REPO, "rakuten_room"))
import product_research as P
kws = P.KEYWORDS
seen = set()
for r in range(0, 10):
    seen |= set(P.rotated_keywords(r * 8 * 3600))
assert seen == set(kws), "回していくと全部のキーワードを使う"
assert P.rotated_keywords(0) != P.rotated_keywords(8 * 3600)
JST = timezone(timedelta(hours=9)); now = datetime.now(JST)
it = lambda code, kw, shop, rc, price=1000: {"itemCode": code, "keyword": kw, "shopName": shop, "reviewCount": rc, "reviewAverage": 4.0, "itemPrice": price, "availability": 1}
items = [it("a", "k1", "S1", 900), it("b", "k1", "S2", 100), it("c", "k2", "S1", 800), it("d", "k2", "S3", 50),
         it("e", "k3", "S4", 999), it("f", "k3", "S5", 10), it("g", "k4", "S6", 5, price=99999)]
hist = [{"itemCode": "e", "suggested_at": (now - timedelta(days=30)).isoformat()},
        {"itemCode": "zz", "shopName": "S5", "suggested_at": (now - timedelta(days=2)).isoformat()}]
got = [i["itemCode"] for i in P.pick(items, hist, ["k1", "k2", "k3", "k4"], 8000, 3)]
# k1→a(S1)、k2→S1は使ったので d(S3)、k3→eは60日以内に出した・fのS5は7日以内 → なし、k4→価格オーバー → なし
assert got == ["a", "d"], got
print("product_research ok", got)
# --- 紹介文の {AFFILIATE_LINK} を消す ---
import write_captions as W
W.generate_json = lambda *a, **k: {"caption": "練習に便利です。レビュー44件で評価4.05です。詳細は {AFFILIATE_LINK} からご覧いただけます。", "hashtags": ["#x"]}
c = W.write_caption({"itemName": "n", "itemPrice": 1})["caption"]
assert c == "練習に便利です。レビュー44件で評価4.05です。", c
print("write_captions ok")
