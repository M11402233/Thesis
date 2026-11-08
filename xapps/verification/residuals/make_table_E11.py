# -*- coding: utf-8 -*-
"""4.4.0（四）E11 結果表之產生器（2026-11-08 新增；正文表格一律由本腳本輸出貼上）。

用法：python3 make_table_E11.py <E11_transitions.json>
欄位定義（與 run_E11_transitions.py 之 analyse()／classify() 一致）：
  引發轉移 = induced 情境數／情境數
  離開 trusted = leave_s 之中位數〔最小–最大〕（僅 induced 且非 None）
  到達 rejected = reject_s 非 None 之情境數／induced 數，中位數
  回到乾淨對照 = back_to_clean_after_end_s 之中位數〔範圍〕
  受測 (節點, 窗) 變化 = 受測節點於全部階段之 tally 加總：
      降級 = 新增非 trusted + 非 trusted 間加重；判定減輕 = 轉成 trusted + 非 trusted 間減輕；
      同狀態改規則；節點消失
"""
import collections
import json
import statistics as st
import sys

NAMES = {"Ci_inflate": "$C_i$ 灌水", "Ci_deflate": "$C_i$ 虛減", "Si_drift": "$S_i$ 漂移 1 %/秒",
         "Si_step": "$S_i$ 階躍 ×1.5", "D1_overtime": "D1 超時（規則回放）", "D2_falseassoc": "D2 偽造關聯（規則回放）"}


def med(v):
    m = st.median(v)
    return str(int(m)) if m == int(m) else f"{m:g}"


def mr(v):
    return f"{med(v)}〔{min(v)}–{max(v)}〕" if v else "—"


def main(path):
    rows = json.load(open(path, encoding="utf-8"))["rows"]
    g = collections.defaultdict(list)
    for r in rows:
        g[(r["kind"], r["T"])].append(r)
    print("| 攻擊 | T | 引發轉移 | 離開 trusted | 到達 rejected | 回到乾淨對照（自攻擊結束起） | 受測 (節點, 窗) 變化：降級（新增非 trusted 或加重）／判定減輕／同狀態改規則／節點消失 |")
    print("|---|---:|---:|---|---|---|---|")
    for (k, T), rs in g.items():
        ind = [r for r in rs if r["induced"]]
        lv = [r["leave_s"] for r in ind if r["leave_s"] is not None]
        rj = [r["reject_s"] for r in ind if r["reject_s"] is not None]
        bc = [r["back_to_clean_after_end_s"] for r in ind if r["back_to_clean_after_end_s"] is not None]
        t = collections.Counter()
        for r in rs:
            for key, v in r["tally"].items():
                who, _ph, face, what = key.split("|")
                if who == "受測":
                    t[(face, what)] += v
        down = t[("判定", "新增非 trusted")] + t[("判定", "非 trusted 間加重")]
        up = t[("判定", "轉成 trusted")] + t[("判定", "非 trusted 間減輕")]
        print(f"| {NAMES[k]} | {T} | {len(ind)}／{len(rs)} | {mr(lv)} | {len(rj)}／{len(ind)}，{med(rj) if rj else '—'} "
              f"| {mr(bc)} | {down:,}／{up}／{t[('判定', '同狀態但規則改變')]}／{t[('上報', '節點消失')]} |")


if __name__ == "__main__":
    main(sys.argv[1])
