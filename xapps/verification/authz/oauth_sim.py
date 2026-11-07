"""OAuth 2.0（RFC 6749, client credentials grant）之邏輯層模擬：DU → Near-RT RIC 之逐筆授權。

規格：docs/thesis/E19_DRL_game_spec.md §5（P10 = B：token 與信任連動，2026-11-07 使用者決定）。
不實作 HTTP／TLS；只模擬 token 發放、scope 檢查、到期、撤銷與續發，供 AuthZ Gate（⓪）與賽局環境使用。

分工（論文須寫清楚）：OAuth 限制 DU 能要求什麼；C_i／S_i／H_i 質疑它說了什麼。
被攻陷 DU 持有合法 token 時，在 scope 內竄改自己 cell 之數值**不會**被本層擋下。

連動（P10=B）之條件與參數（【待確認】，見規格 §10 Q-g）：
  revoke_after_n : 連續 rejected ≥ N 窗才撤銷
  revoke_delay   : 撤銷生效之隨機延遲 U[0, D] 窗（以 rng_seed 固定，確定性）
  cooldown       : 撤銷後 T 窗內不得重新取得 token
coupled=False 為不連動對照版（token 生命週期與信任狀態無關）。
所有 token 事件記入 events，供量測資訊洩漏（規格 §5 (i)–(iii)）。
"""
import random
from dataclasses import dataclass, field

R1_AUTHZ = "R1_AUTHZ"

# 請求種類（最小權限：每個 DU 只取得需要的）
REQ_KPM_REPORT = "kpm_report"          # 上報自身 cell 之 E2SM-KPM
REQ_LOAD_CLAIM = "load_claim"          # 宣告自身 cell 之可用資源（供 steering）
REQ_HANDOVER = "handover_request"      # 要求把 UE 轉入（教授舉例之內部攻擊）


@dataclass
class Token:
    token_id: str
    du_id: str
    cells: frozenset
    meas_types: frozenset
    req_types: frozenset
    issued_at: int
    expires_at: int


@dataclass
class DURegistration:
    du_id: str
    cells: frozenset
    meas_types: frozenset = frozenset({"DRB.RlcSduDelayDl", "DRB.UEThpDl", "RRU.PrbUsedDl"})
    req_types: frozenset = frozenset({REQ_KPM_REPORT, REQ_LOAD_CLAIM})


@dataclass
class AuthorizationServer:
    registry: dict                      # du_id → DURegistration
    lifetime: int = 60                  # token 有效窗數（短效）
    coupled: bool = False               # P10：True = 連動版
    revoke_after_n: int = 3
    revoke_delay: int = 5
    cooldown: int = 30
    rng_seed: int = 0
    events: list = field(default_factory=list)

    def __post_init__(self):
        self._rng = random.Random(self.rng_seed)
        self._seq = 0
        self._rej_run = {}              # du_id → 連續 rejected 窗數
        self._pending_revoke = {}       # du_id → 生效窗
        self._blocked_until = {}        # du_id → 冷卻結束窗（不含）
        self._revoked = set()           # 已撤銷之 token_id

    # ---- RFC 6749 §4.4 client credentials：發 token ----
    def issue(self, du_id, w):
        reg = self.registry.get(du_id)
        if reg is None:
            self.events.append((w, du_id, "issue_denied", "unregistered"))
            return None
        if w < self._blocked_until.get(du_id, -1):
            self.events.append((w, du_id, "issue_denied", "cooldown"))
            return None
        self._seq += 1
        t = Token(f"tok{self._seq}", du_id, reg.cells, reg.meas_types, reg.req_types,
                  w, w + self.lifetime)
        self.events.append((w, du_id, "issue", t.token_id))
        return t

    def revoke(self, token, w, reason):
        self._revoked.add(token.token_id)
        self.events.append((w, token.du_id, "revoke", reason))

    # ---- 逐筆驗證（AuthZ Gate ⓪ 呼叫）----
    def check(self, token, w, cell, req_type, meas_type=None):
        """回傳 (ok, reason)。ok=False → 規則 R1_AUTHZ（rejected）。"""
        if token is None:
            return False, "no_token"
        if token.token_id in self._revoked:
            return False, "revoked"
        if w >= token.expires_at:
            return False, "expired"
        if cell not in token.cells:
            return False, "cell_out_of_scope"
        if req_type not in token.req_types:
            return False, "request_out_of_scope"
        if meas_type is not None and meas_type not in token.meas_types:
            return False, "measurement_out_of_scope"
        return True, "ok"

    # ---- P10 連動：每窗收到該 DU 之信任判定後呼叫 ----
    def observe_verdict(self, du_id, token, w, decision):
        """decision ∈ {trusted, low-trust, abstain, rejected}。不連動版只記錄、不動作。"""
        if not self.coupled or token is None or token.token_id in self._revoked:
            return                      # 已撤銷之 token 不再累計（避免重複撤銷、延長冷卻）
        run = self._rej_run.get(du_id, 0) + 1 if decision == "rejected" else 0
        self._rej_run[du_id] = run
        if run >= self.revoke_after_n and du_id not in self._pending_revoke:
            self._pending_revoke[du_id] = w + self._rng.randint(0, self.revoke_delay)
        due = self._pending_revoke.get(du_id)
        if due is not None and w >= due:
            self.revoke(token, w, f"trust_rejected_run>={self.revoke_after_n}")
            self._blocked_until[du_id] = w + self.cooldown
            del self._pending_revoke[du_id]
            self._rej_run[du_id] = 0
