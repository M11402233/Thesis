"""OAuth 層測試（規格 E19 §5）：越權全數被擋；持合法 token 之數值竄改不被擋；連動版之撤銷條件。"""
import sys
from oauth_sim import AuthorizationServer, DURegistration, REQ_KPM_REPORT, REQ_HANDOVER

fails = []
def check(name, cond):
    print(f"  {'✓' if cond else '✗'} {name}")
    if not cond: fails.append(name)

reg = {f"du{c}": DURegistration(f"du{c}", frozenset({c})) for c in range(2, 9)}
for coupled in (False, True):
    print(f"coupled={coupled}")
    a = AuthorizationServer(reg, coupled=coupled, revoke_after_n=3, revoke_delay=5, cooldown=30, rng_seed=1)
    t = a.issue("du3", 0)
    check("合法上報自身 cell", a.check(t, 1, 3, REQ_KPM_REPORT)[0])
    check("替他 cell 上報 → 擋", a.check(t, 1, 4, REQ_KPM_REPORT) == (False, "cell_out_of_scope"))
    check("超出最小權限之請求 → 擋", a.check(t, 1, 3, REQ_HANDOVER) == (False, "request_out_of_scope"))
    check("到期 → 擋", a.check(t, 60, 3, REQ_KPM_REPORT) == (False, "expired"))
    check("未登記 DU 不發 token", a.issue("du99", 0) is None)
    # 數值竄改：OAuth 不看數值 → 必定通過（分工之證明）
    check("持合法 token 之數值竄改不被 OAuth 擋", a.check(t, 2, 3, REQ_KPM_REPORT, "DRB.RlcSduDelayDl")[0])
    # 連動
    for w in range(3, 20):
        a.observe_verdict("du3", t, w, "rejected")
    revoked = a.check(t, 20, 3, REQ_KPM_REPORT) == (False, "revoked")
    check("連動版連續 rejected 後撤銷" if coupled else "不連動版不撤銷", revoked == coupled)
    if coupled:
        ev = [e for e in a.events if e[2] == "revoke"]
        check("撤銷於第 3 個 rejected 窗之後 0–5 窗內生效", len(ev) == 1 and 5 <= ev[0][0] <= 10)
        check("冷卻期內不得重新取得", a.issue("du3", ev[0][0] + 1) is None)
        check("冷卻後可重新取得", a.issue("du3", ev[0][0] + 30) is not None)
    b = AuthorizationServer(reg, coupled=coupled, rng_seed=1); tb = b.issue("du3", 0)
    for w, d in enumerate(["rejected", "rejected", "low-trust", "rejected", "rejected"]):
        b.observe_verdict("du3", tb, w, d)
    check("非連續 rejected 不撤銷", b.check(tb, 6, 3, REQ_KPM_REPORT)[0])
sys.exit(1 if fails else print("全部通過"))
