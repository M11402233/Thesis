"""C3 單元測試:融合順序 first-match vs severity(規格 docs/thesis/fusion_severity_order_spec.md §3)。

用法:python3 test_fusion_order.py   (失敗即 exit 1)
另做窮舉:全部輸入組合下,severity 與 first-match 之差異僅限 EXPECTED_SEVERITY_DIFF,
且 severity 決策之嚴重度 ≥ first-match(只會更嚴)。
"""
import itertools
import sys
import zt_kpm_xapp as X

fails = []


def check(name, cond, info=""):
    print(f"  {'✓' if cond else '✗'} {name} {info}")
    if not cond:
        fails.append(name)


def run(order, *a):
    X.FUSION_ORDER = order
    if order == "severity":
        return X.fuse_detail(*a)
    return X.fuse(*a) + (None,)


X.FUSION_MODE = "bound"
BOUND_EV = {"cells": [3]}
print("C3 單元測試")
# (1) C_i 第 1 窗 + D2 違反
fm = run("first-match", "violated", 1, "normal", "violated", "normal")
sv = run("severity", "violated", 1, "normal", "violated", "normal")
check("CI 第1窗+D2:first-match 為 R1_CI_PENDING(缺陷重現)", fm[1] == "R1_CI_PENDING", fm[:2])
check("CI 第1窗+D2:severity → rejected/R1_D2_VETO", sv[:2] == ("rejected", "R1_D2_VETO"), sv[:2])
check("  also_matched 含 R1_CI_PENDING", sv[2] == ["R1_CI_PENDING"], sv[2])
# (2) C_i 第 1 窗 + S_i + 綁定強 D1
fm = run("first-match", "violated", 1, "violated", "normal", "strong", BOUND_EV, 3)
sv = run("severity", "violated", 1, "violated", "normal", "strong", BOUND_EV, 3)
check("CI 第1窗+S_i+綁定D1:first-match 為 R1_CI_PENDING", fm[1] == "R1_CI_PENDING", fm[:2])
check("CI 第1窗+S_i+綁定D1:severity → rejected/R2_SI_D1_BOUND",
      sv[:2] == ("rejected", "R2_SI_D1_BOUND"), sv[:2])
check("  also_matched = [R1_CI_PENDING, R2_D1_STRONG]",
      sv[2] == ["R1_CI_PENDING", "R2_D1_STRONG"], sv[2])
# (3) 不應改變之組合
for args, exp in [
    (("violated", 2, "normal", "violated", "normal"), "R1_CI_VETO"),           # 同為 rejected → L1 表序
    (("violated", 1, "violated", "normal", "normal"), "R1_CI_PENDING"),        # 同為 low-trust → L1
    (("violated", 1, "unavailable", "normal", "normal"), "R1_CI_PENDING"),     # low-trust > abstain
    (("normal", 0, "violated", "normal", "strong", {"cells": [5]}, 3), "R2_SI_D1_UNBOUND"),
    (("normal", 0, "unavailable", "normal", "weak"), "R2_D1_WEAK"),
    (("normal", 0, "normal", "normal", "normal"), "R0_CLEAN"),
]:
    f, s = run("first-match", *args), run("severity", *args)
    check(f"不變:{exp}", f[1] == s[1] == exp, (f[1], s[1], s[2]))

# (4) 窮舉
print("窮舉(兩種 FUSION_MODE × 全部輸入組合)")
for mode in ("bound", "legacy"):
    X.FUSION_MODE = mode
    n = nd = 0
    for ci, run_, si, d2, d1, ev in itertools.product(
            ("normal", "violated"), (1, 2), ("normal", "violated", "unavailable"),
            ("normal", "violated"), ("normal", "weak", "strong"),
            (None, {"cells": [3]}, {"cells": [5]})):
        a = (ci, run_, si, d2, d1, ev, 3)
        f = run("first-match", *a)
        s = run("severity", *a)        # 預期外差異會在 fuse_detail 內 SystemExit
        n += 1
        if f[1] != s[1]:
            nd += 1
            if X.SEVERITY[s[0]] <= X.SEVERITY[f[0]]:
                fails.append(f"severity 未更嚴 {a}")
        # first-match 經 fuse() 仍與原始函式一致
        X.FUSION_ORDER = "first-match"
        if X.fuse(*a) != X.fuse_first_match(*a):
            fails.append(f"fuse()≠fuse_first_match {a}")
    check(f"{mode}:{n} 組合中 {nd} 組相異,皆屬預期且更嚴", not any("未更嚴" in x for x in fails))
X.FUSION_MODE, X.FUSION_ORDER = "bound", "first-match"
print(f"預期組合累計:{dict(X.SEVERITY_DIFFS)}")
if fails:
    print("FAIL:", fails)
    sys.exit(1)
print("C3 全部通過")
