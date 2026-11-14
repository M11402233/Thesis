#!/usr/bin/env python3
"""run_Ei_diagnostic.py — S_i 區間延遲更正分析 E-i（規格 docs/thesis/Si_interval_correction_spec_v0.md §6、§9.1 Q-2）。

E-i = 修正後輸入（ZT_DELAY_SOURCE=reconstructed）＋ 原凍結尺度：
  受測 seed k 之 C-2 尺度取 s_old^(-k)（其餘七 seed 之原累計輸入、原 global_scale 公式），
  讀自 check_Q1_scales.py --freeze-ei 之 data/results/semantics_v0/Ei_old_scales_frozen.json。
  τ_S、MIN_PEER、注入參數、時間參照參數全部不變；程式邏輯直接重用 run_Si_reference_ablation.py 與
  run_E9_operating_regime.py 之 main()（只替換 global_scale 之回傳值與輸出目錄，不改兩支腳本）。
  E-i 只含 S_i 乾淨誤報與 E9 階躍／漂移（C-2 尺度）；C-1（TrustAnchor，xApp）不在 E-i 範圍。

內建檢查（任一失敗即停，不調參數）：
  K1 凍結檔之資料 md5 與目前 D-30 分析檔相同。
  K2 每個 fold 恰好缺一個 seed，尺度依該 seed 取用；兩支腳本共 16 次取用、每 seed 各 2 次。
  K3 --self-check（ZT_DELAY_SOURCE=cumulative）：凍結尺度與原 global_scale 差 ≤ 1e-12（凍結檔以自有 MAD 實作算出，
     浮點捨入差約 1e-17；同 check_Q1_scales.py 之容許），且兩支腳本之 JSON
     須與既有主結果（data/results/d30_fusion_order/severity/）逐位相同 → 證明替換機制本身不改變任何結果。
用法：
  ZT_DATASET=d30 ZT_DELAY_SOURCE=cumulative    python3 run_Ei_diagnostic.py --self-check --out <scratch>
  ZT_DATASET=d30 ZT_DELAY_SOURCE=reconstructed python3 run_Ei_diagnostic.py      # → <results_dir>/E_i/
"""
import os, sys, json, hashlib, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datasets as DS, interval_source as IS
import run_Si_reference_ablation as ABL, run_E9_operating_regime as E9

REPO = os.path.expanduser("~/oran-zt-kpm-verification")
FROZEN = os.path.join(REPO, "data/results/semantics_v0/Ei_old_scales_frozen.json")
MAIN_REF = os.path.join(REPO, "data/results/d30_fusion_order/severity")

ap = argparse.ArgumentParser()
ap.add_argument("--self-check", action="store_true")
ap.add_argument("--out", default=None)
a = ap.parse_args()
m = IS.mode()
if DS.NAME != "d30":
    raise SystemExit("E-i 只定義於 ZT_DATASET=d30")
if a.self_check and m != "cumulative":
    raise SystemExit("--self-check 須 ZT_DELAY_SOURCE=cumulative")
if not a.self_check and m == "cumulative":
    raise SystemExit("E-i 須非累計輸入（reconstructed／exact）；累計模式只用於 --self-check")
out = a.out or os.path.join(DS.results_dir(), "E_i")
if not a.self_check and a.out:
    raise SystemExit("正式 E-i 輸出目錄固定為 <results_dir>/E_i")
os.makedirs(out, exist_ok=True)

fz = json.load(open(FROZEN))
C2 = {f["test_seed"]: f["C2"] for f in fz["folds"]}
# K1
files = DS.files()
md5 = {os.path.basename(f): hashlib.md5(open(f, "rb").read()).hexdigest() for f in files}
if md5 != fz["data_md5"]:
    raise SystemExit(f"K1 失敗：凍結檔之資料 md5 與目前分析檔不同\n{md5}\n{fz['data_md5']}")
print(f"K1 ✓ 資料 md5 與凍結檔相同（{len(md5)} 檔）；凍結時程式版本 {fz['code_git_head'][:8]} dirty={fz['code_dirty']}")

used = []; dev = []
def patch(mod, name):
    orig_load, orig_scale = mod.load_cell_delay, mod.global_scale
    ids = {}
    def load(path):
        r = orig_load(path); ids[id(r)] = os.path.basename(path); return r
    def scale(train):
        tid = {id(t) for t in train}
        miss = [b for i, b in ids.items() if i not in tid]
        if len(miss) != 1 or len(train) != len(ids) - 1:
            raise SystemExit(f"K2 失敗（{name}）：無法唯一判定受測 seed：{miss}")
        s = C2[miss[0]]
        if a.self_check:
            s0 = orig_scale(train)
            dev.append(abs(s0 - s))
            if abs(s0 - s) > 1e-12:                    # 與凍結時之內建檢查同一容許（check_Q1_scales.py：1e-12）
                raise SystemExit(f"K3 失敗（{name}）：{miss[0]} 凍結 {s!r} vs 原公式 {s0!r}")
        used.append((name, miss[0], s)); return s
    mod.load_cell_delay, mod.global_scale, mod.OUT_DIR = load, scale, out

patch(ABL, "Si_reference_ablation"); patch(E9, "E9_operating_regime")
print(f"\n=== Si_reference_ablation（E-i，delay={m}）===")
ABL.main()
print(f"\n=== E9_operating_regime（E-i，delay={m}）===")
sys.argv = [sys.argv[0], "--out-dir", out]
E9.main()

cnt = collections.Counter((n, s) for n, s, _ in used)
if len(used) != 16 or set(cnt.values()) != {1} or len({s for _, s, _ in used}) != 8:
    raise SystemExit(f"K2 失敗：尺度取用 {len(used)} 次 {dict(cnt)}")
print("\nK2 ✓ 兩支腳本各 8 個 fold，尺度依受測 seed 取用（s_old^(-k)，C-2）")

res = {"spec": "Si_interval_correction_spec_v0 §6 E-i", "delay_source": m, "self_check": a.self_check,
       "scales_used": [{"script": n, "test_seed": s, "C2_old": v} for n, s, v in used],
       "frozen_file": FROZEN, "frozen_code_git_head": fz["code_git_head"], "data_md5": md5,
       "note": "以現行 cell 歸屬（最後事件）為條件；E-i 只含 C-2 尺度之 S_i 乾淨誤報與 E9"}
if a.self_check:
    diff = {}
    for fn in ("Si_reference_ablation.json", "E9_operating_regime.json"):
        x, y = json.load(open(os.path.join(out, fn))), json.load(open(os.path.join(MAIN_REF, fn)))
        if x != y:
            diff[fn] = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
    res["K3_main_results_identical"] = not diff
    res["K3_max_scale_dev"] = max(dev)
    if diff:
        json.dump(res, open(os.path.join(out, "Ei_meta.json"), "w"), indent=1, ensure_ascii=False)
        raise SystemExit(f"K3 失敗：與主結果不同之鍵 {diff}")
    print(f"K3 ✓ 累計輸入下兩支腳本之 JSON 與主結果（{MAIN_REF}）逐位相同")
json.dump(res, open(os.path.join(out, "Ei_meta.json"), "w"), indent=1, ensure_ascii=False)
print("寫入", os.path.join(out, "Ei_meta.json"))
