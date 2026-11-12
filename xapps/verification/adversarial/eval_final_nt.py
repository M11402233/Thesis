# -*- coding: utf-8 -*-
"""eval_final_nt.py — §6 之延伸：TPR_nt、d_nt 之正式前緣判定（規格要求「另以 TPR_nt、d_nt 報同樣之比較」，
報告階段原漏做，使用者事後手動查看後要求補為正式判定）。

不重跑任何評估（讀 pairs.json 既有快取，與 eval_final.py --stage eval 用同一份資料）；
不修改 eval_final.py 既有邏輯；輸出合併進既有 eval_final.json，並以逐欄位比對確認未改動既有內容（TPR_rej 判準）。
用法：ZT_DATASET=d30 ZT_FUSION_ORDER=severity python3 eval_final_nt.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_final import strategies, all_pairs, Runner, mix, frontier_judge, B2_LS, OUT, rid, meta


def worst_nt(cache, key, sD, aset):
    ms = {a: mix(cache, sD, {a: 1.0}, key) for a in aset}
    a_t = min(aset, key=lambda a: (ms[a]["TPR_nontrusted"], a))
    a_d = max(aset, key=lambda a: (ms[a]["d_nontrusted"]["median"], a))
    return {"by_TPR": {"attacker": a_t, **ms[a_t]}, "by_delay": {"attacker": a_d, **ms[a_d]}}


def main():
    if os.environ.get("ZT_DATASET") != "d30" or os.environ.get("ZT_FUSION_ORDER") != "severity":
        raise SystemExit("須在 ZT_DATASET=d30 與 ZT_FUSION_ORDER=severity 下執行")
    dets, atks, runs = strategies()
    pairs, D, A = all_pairs(dets, atks, runs)
    cache_path = os.path.join(OUT, "pairs.json")
    cache = json.load(open(cache_path, encoding="utf-8"))
    miss = [Runner.key(*p) for p in pairs if Runner.key(*p) not in cache]
    if miss:
        raise SystemExit(f"尚有 {len(miss)} 組未評估（pairs.json 不完整）：{miss[:5]}")
    key = lambda d, a: f"{d}|{a or 'CLEAN'}|"
    base_ids = ["D0"] + [f"B2_L{L}" for L in B2_LS] + [i for i in dets if i.startswith("B3_")]
    scripted = [a for a in A if atks[a]["kind"] == "scripted"]
    A_pool = [a for a in A if not a.endswith(":ABR")]

    out_path = os.path.join(OUT, "eval_final.json")
    out = json.load(open(out_path, encoding="utf-8"))
    before = json.dumps(out, sort_keys=True)  # 比對用：確認本次執行未改動既有欄位（TPR_rej 判準）

    base_nt = {b: {"A-script": worst_nt(cache, key, {b: 1.0}, scripted),
                    "A-pool": worst_nt(cache, key, {b: 1.0}, A_pool)} for b in base_ids}

    summ_nt = {}
    for r, info in runs.items():
        sD = info["sigma_D"]
        e = out["runs"][r]
        nt = {"A-script": worst_nt(cache, key, sD, scripted), "A-pool": worst_nt(cache, key, sD, A_pool),
              "A-eq": e["A-eq"]}
        if "A-BR" in e:
            nt["A-BR"] = e["A-BR"]
        J = {}
        frr = e["clean"]["clean_false_reject"]
        for sname in ["A-script", "A-pool", "A-eq"] + (["A-BR"] if "A-BR" in nt else []):
            if sname in ("A-script", "A-pool"):
                drl_t = nt[sname]["by_TPR"]["TPR_nontrusted"]
                drl_d = nt[sname]["by_delay"]["d_nontrusted"]["median"]
                bp = [(b, out["baselines"][b]["clean"]["clean_false_reject"],
                       base_nt[b][sname]["by_TPR"]["TPR_nontrusted"],
                       base_nt[b][sname]["by_delay"]["d_nontrusted"]["median"]) for b in base_ids]
            else:
                tag = f"{sname}@{r}"
                drl_t, drl_d = nt[sname]["TPR_nontrusted"], nt[sname]["d_nontrusted"]["median"]
                bp = [(b, out["baselines"][b]["clean"]["clean_false_reject"],
                       out["baselines"][b][tag]["TPR_nontrusted"], out["baselines"][b][tag]["d_nontrusted"]["median"])
                      for b in base_ids]
            v, why = frontier_judge((frr, drl_t, drl_d), bp)
            J[sname] = {"verdict": v, "why": why, "DRL": {"FRR": frr, "TPR_nontrusted": drl_t, "d_nontrusted_median": drl_d}}
        e["judgement_nt"] = J

    for lv in ("O-full", "O-outcome"):
        rs = [rid(lv, t) for t in (0, 1, 2)]
        for sname in ["A-script", "A-pool", "A-eq", "A-BR"]:
            vs = [out["runs"][r]["judgement_nt"].get(sname, {}).get("verdict") for r in rs]
            if None in vs:
                continue
            n = vs.count("優於")
            summ_nt[f"{lv}|{sname}"] = {"verdicts": vs, "n_better": n,
                                        "conclusion": "優於" if n == 3 else ("多數情形優於" if n == 2 else "未優於")}
    out["summary_nt"] = summ_nt
    out["meta_nt"] = meta()
    out["meta_nt"]["note"] = "TPR_nt/d_nt 之正式前緣判定（§6「另以 TPR_nt、d_nt 報同樣之比較」，事後補跑，非原始 report 階段產出；不改 TPR_rej 判準）"

    # 確認既有欄位（TPR_rej 判準）未被改動
    out2 = json.loads(json.dumps(out))
    out2.pop("summary_nt", None)
    out2.pop("meta_nt", None)
    for rr in out2["runs"]:
        out2["runs"][rr].pop("judgement_nt", None)
    assert json.dumps(out2, sort_keys=True) == before, "既有欄位被意外修改，已中止、未寫檔"

    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for k, v in summ_nt.items():
        print(k, v)
    print("寫入", out_path)


if __name__ == "__main__":
    main()
