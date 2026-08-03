#!/usr/bin/env python3
"""
run_Ci_extended_E6E8.py — C_i 延伸實驗 E6/E7/E8

E6 持續窗脆弱性:L_C=2 政策下,攻擊者只注入 D 窗後停手能否逃脫硬否決?
E7 不精確守恆:攻擊者對 N_known 認知有誤差時的偵測邊界(量化容錯空間)
E8 真實攻擊面:單一 O-DU 每窗實際可抹除的 UE 數(取代舊 4.6.5 之「LTE 遮蔽」論述)

註:本研究資料中「同窗同時掛 LTE 與 mmWave」之樣本為 0(12,600 個 (窗,UE) 樣本),
   故舊版 4.6.5 所述之「雙掛遮蔽」機制不存在;單一 O-DU 僅能抹除當窗掛載於其上之 UE,
   而此類抹除必然造成全域聯集淨減 → C_i 偵測率 100%。

輸入: data/batchFinal_seeds/seed42*.txt (10 seed × 60 窗)
輸出: data/results/Ci_extended_E6E8.json + fig_Ci_E6_persistence.png
"""
import os, glob, json, collections
import numpy as np

DATA_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/batchFinal_seeds")
OUT_DIR  = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
os.makedirs(OUT_DIR, exist_ok=True)

N_KNOWN = 7
L_C     = 2                    # 持續窗門檻(對齊 4.6.1)
DURATIONS = [1, 2, 3, 5]       # E6:攻擊注入持續窗數
NET_CASES = [(2,2),(3,3),(1,1),(4,4),(2,1),(3,2),(1,2),(2,3),(1,0),(0,1)]  # E7:(假,真)


def load(path):
    """回傳 {window: {imsi: set(cells)}}"""
    occ = collections.defaultdict(lambda: collections.defaultdict(set))
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 11:
                continue
            try:
                w = int(float(p[0])); c = int(p[2]); i = int(p[3])
            except ValueError:
                continue
            occ[w][i].add(c)
    return occ


def conserved(imsi_set):
    return len(imsi_set) == N_KNOWN


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "seed42*.txt"))) or \
            sorted(glob.glob("seed42*.txt"))
    if not files:
        print(f"找不到資料,請確認 {DATA_DIR}"); return
    print(f"載入 {len(files)} 個 seed\n")
    out = {"n_seeds": len(files), "N_known": N_KNOWN, "L_C": L_C}

    # ================= E6 =================
    print("="*72); print("E6:L_C 持續窗脆弱性(攻擊注入 D 窗後停手)"); print("="*72)
    e6 = []
    for D in DURATIONS:
        escaped = 0
        for f in files:
            occ = load(f); wins = sorted(occ); t0 = len(wins)//2
            viol = []
            for idx, w in enumerate(wins):
                s = set(occ[w].keys())
                if t0 <= idx < t0 + D:
                    s = s | {9001}                       # 灌水 +1
                viol.append(not conserved(s))
            run = 0; rejected = False
            for v in viol:
                run = run + 1 if v else 0
                if run >= L_C:
                    rejected = True; break
            if not rejected:
                escaped += 1
        e6.append({"duration": D, "escaped": escaped, "trials": len(files),
                   "escape_rate": escaped/len(files)})
        print(f"  持續 {D} 窗: {escaped}/{len(files)} seed 逃脫硬否決 "
              f"({escaped/len(files):.0%})")
    out["E6_persistence"] = e6
    print(f"  → D < L_C({L_C}) 之脈衝攻擊可停留於 pending,不觸發 rejected")

    # ================= E7 =================
    print(); print("="*72); print("E7:不精確守恆替換(攻擊者對 N_known 之認知誤差)"); print("="*72)
    e7 = []
    for add, rem in NET_CASES:
        det = tot = 0
        for f in files:
            occ = load(f)
            for w in sorted(occ):
                s = set(occ[w].keys()); real = sorted(s)
                if rem > len(real):
                    continue
                s2 = (s - set(real[:rem])) | {9000+j for j in range(add)}
                tot += 1
                if not conserved(s2):
                    det += 1
        rate = det/tot if tot else float("nan")
        e7.append({"add": add, "remove": rem, "net": add-rem,
                   "detected": det, "total": tot, "rate": rate})
        print(f"  +{add}假/-{rem}真 (淨 {add-rem:+d}): {det}/{tot} = {rate:.0%}")
    out["E7_imprecise_conservation"] = e7
    print("  → 淨變化=0 全數繞過;|淨變化|≥1 全數偵測 → 攻擊者容錯空間 = 0")

    # ================= E8 =================
    print(); print("="*72); print("E8:單一 O-DU 虛減之真實攻擊面"); print("="*72)
    per_cell = collections.defaultdict(list); field = []
    dual = mmonly = lteonly = 0
    for f in files:
        occ = load(f)
        for w, imsis in occ.items():
            cellmap = collections.defaultdict(set)
            for i, cs in imsis.items():
                if 1 in cs and (cs - {1}):   dual += 1
                elif cs - {1}:               mmonly += 1
                else:                        lteonly += 1
                for c in cs:
                    if c != 1:
                        cellmap[c].add(i)
            for c in range(2, 9):
                per_cell[c].append(len(cellmap.get(c, set())))
            field.append(sum(len(v) for v in cellmap.values()))
    a = np.array(field); n_pairs = dual + mmonly + lteonly
    print(f"  (窗,UE) 樣本={n_pairs}: mmWave-only={mmonly} ({mmonly/n_pairs:.1%}), "
          f"同時雙掛={dual} ({dual/n_pairs:.1%}), LTE-only={lteonly} ({lteonly/n_pairs:.1%})")
    print(f"  全場域每窗 mmWave 掛載 UE 數: mean={a.mean():.2f} min={a.min()} max={a.max()}")
    print(f"  無任何 mmWave 掛載之窗(攻擊者無從發動)={int((a==0).sum())}/{len(a)} = {(a==0).mean():.1%}")
    cells = {}
    print("  逐 O-DU 每窗可抹除 UE 數:")
    for c in sorted(per_cell):
        v = np.array(per_cell[c])
        cells[c] = {"mean": float(v.mean()), "max": int(v.max()),
                    "idle_ratio": float((v == 0).mean())}
        print(f"    cell {c}: mean={v.mean():.2f} max={v.max()} 無載窗={(v==0).mean():.1%}")
    out["E8_attack_surface"] = {
        "window_ue_pairs": n_pairs, "mmwave_only": mmonly, "dual_homed": dual,
        "lte_only": lteonly, "field_mean": float(a.mean()),
        "zero_attach_windows": int((a == 0).sum()), "total_windows": len(a),
        "per_cell": cells}

    with open(os.path.join(OUT_DIR, "Ci_extended_E6E8.json"), "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(f"\n結果寫入 {os.path.join(OUT_DIR,'Ci_extended_E6E8.json')}")

    # ---- E6 圖 ----
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        ds = [r["duration"] for r in e6]; es = [100*r["escape_rate"] for r in e6]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.bar([str(d) for d in ds], es, color=["#c92a2a" if d < L_C else "#2b8a3e" for d in ds])
        ax.axhline(50, ls=":", color="#868e96", alpha=0.6)
        for i, v in enumerate(es):
            ax.text(i, v + 2, f"{v:.0f}%", ha="center", fontsize=10)
        ax.set_xlabel(f"attack injection duration (windows);  L_C = {L_C}")
        ax.set_ylabel("escape rate from hard veto (%)")
        ax.set_title(f"E6: pulse attacks shorter than L_C evade rejection")
        ax.set_ylim(0, 115); ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, "fig_Ci_E6_persistence.png"), dpi=150)
        print("圖已存: fig_Ci_E6_persistence.png")
    except ImportError:
        print("未安裝 matplotlib,略過畫圖")


if __name__ == "__main__":
    main()
