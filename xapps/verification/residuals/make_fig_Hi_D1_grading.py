#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_fig_Hi_D1_grading.py — 重繪 H_i-D1 分級圖(修正圖文矛盾)

【要解決的問題】
舊圖(fig_Hi_H5_grading)之圖例直接標為:
    rejected   z >= 3
    low-trust  2 <= z < 3
    trusted    z < 2
但 4.8.5 已定案:D1 單獨違反**不**直接 hard reject,z >= tau_reject 僅為
strong statistical evidence,須交叉佐證或多窗持續才升級 rejected。

其根因不只在繪圖:run_Hi_experiments.py 的 grade(z) 直接回傳
'rejected'/'low-trust'/'trusted',把「證據強度」與「信任狀態」混為一談。
本檔將二者分離:

    d1_evidence(z)  -> 'strong' / 'warning' / 'none'      (D1 能產生的東西)
    fuse_d1(...)    -> 'rejected' / 'low-trust' / 'trusted' (融合層才能產生的東西)

【對應 4.8.5 的五列規則】
    D2 violated                        -> rejected           (hard veto)
    D1 z >= tau_reject  且有佐證        -> rejected
    D1 z >= tau_reject  單獨            -> low-trust / investigation
    tau_warn <= D1 z < tau_reject       -> low-trust
    D1 z < tau_warn                     -> trusted

【輸出】
    fig_Hi_D1_grading.png   左:z_d 分布與三個證據等級  右:證據 -> 信任狀態對應

【跑法】
    python3 make_fig_Hi_D1_grading.py
    python3 make_fig_Hi_D1_grading.py --data-dir ./seeds/si_lstm_seeds --out-dir ./results
    python3 make_fig_Hi_D1_grading.py --lang en      # 英文標籤(避開中文字型問題)
"""
import os
import glob
import argparse
import collections
import numpy as np

# ---- 門檻(對齊 4.8.5;此處僅用於證據分級,不產生信任狀態)----
TAU_WARN = 2.0      # tau_H^warn
TAU_REJECT = 3.0    # tau_H^reject
EDGE_SPLIT = 0.55   # LTE-only 佔比 >= 0.55 判為 edge
MIN_EVENTS = 8      # per-UE-index 基線所需最少事件數,不足時退回群層級
LTE_CELL = 1

SI_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/si_lstm_seeds")
OUT_DIR = os.path.expanduser("~/oran-zt-kpm-verification/data/results")

# ---- 配色(與其他論文圖一致)----
C_NONE = "#6C8EBF"     # 藍 — 無 D1 證據
C_WARN = "#D6B656"     # 黃 — warning evidence
C_STRONG = "#B85450"   # 紅 — strong evidence
C_TRUST = "#82B366"    # 綠 — trusted
C_GRAY = "#666666"


# ==========================================================================
# 資料載入(與 run_Hi_experiments.py 同一套邏輯)
# ==========================================================================
def load(path):
    rec = collections.defaultdict(dict)
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 4:
                continue
            try:
                w = int(float(p[0])); cell = int(p[2]); imsi = int(p[3])
            except ValueError:
                continue
            rec[imsi].setdefault(w, set()).add(cell)
    return rec


def state_seq(wm, all_w):
    s = []
    for w in all_w:
        cells = wm.get(w, set())
        if any(c != LTE_CELL for c in cells):
            s.append("mmw")
        elif LTE_CELL in cells:
            s.append("lte")
        else:
            s.append("absent")
    return s


def dwell_events(seq):
    """擷取每次「離開 mmWave 後連續掛 LTE-only 的窗數」"""
    ev, i = [], 0
    while i < len(seq):
        if seq[i] == "mmw":
            j, run = i + 1, 0
            while j < len(seq) and seq[j] == "lte":
                run += 1; j += 1
            if run > 0:
                ev.append(run)
            i = j
        else:
            i += 1
    return ev


def build_baseline(train_files):
    """per-UE-index 停留基線(唯讀,永不線上更新)+ resident/edge 群層級退回"""
    dwell = collections.defaultdict(list)
    ltefrac = collections.defaultdict(list)
    for f in train_files:
        rec = load(f)
        all_w = sorted({w for _, wm in rec.items() for w in wm})
        for imsi, wm in rec.items():
            seq = state_seq(wm, all_w)
            dwell[imsi] += dwell_events(seq)
            na = sum(1 for s in seq if s != "absent")
            if na:
                ltefrac[imsi].append(sum(1 for s in seq if s == "lte") / na)
    grp = {"resident": [], "edge": []}
    for imsi, d in dwell.items():
        lf = np.mean(ltefrac[imsi]) if ltefrac[imsi] else 0.5
        grp["edge" if lf >= EDGE_SPLIT else "resident"] += d
    hampel = {}
    for imsi, d in dwell.items():
        if len(d) >= MIN_EVENTS:
            med = np.median(d)
            mad = np.median(np.abs(np.array(d) - med))
            hampel[imsi] = (float(med), float(1.4826 * mad if mad > 0 else 1.0))
    return hampel, {k: sorted(v) for k, v in grp.items()}, ltefrac


def robust_z(d, med, sigma):
    return (d - med) / sigma if sigma > 0 else 0.0


# ==========================================================================
# 核心修正:證據等級 與 信任狀態 分離
# ==========================================================================
def d1_evidence(z):
    """H_i-D1 能產生的東西:證據強度,不是信任狀態。"""
    if z >= TAU_REJECT:
        return "strong"
    if z >= TAU_WARN:
        return "warning"
    return "none"


def fuse_d1(evidence, d2_violated=False, corroborated=False):
    """信任狀態只能由融合層產生(4.8.5 五列規則)。

    corroborated: 同窗有 C_i/S_i 示警,或該證據已多窗持續。
    """
    if d2_violated:
        return "rejected"                    # hard veto,架構斷言
    if evidence == "strong":
        return "rejected" if corroborated else "low-trust"
    if evidence == "warning":
        return "low-trust"
    return "trusted"


# 供 run_Hi_experiments.py 對照用:舊的 grade() 等價於
#   fuse_d1(d1_evidence(z), corroborated=True)
# ——亦即它隱含假設「永遠有佐證」,這正是圖文矛盾的來源。


# ==========================================================================
# 收集 z_d 樣本
# ==========================================================================
def collect(files, seeds):
    """LOSO:對每個 held-out seed,以其餘 seed 建基線,收集乾淨與注入之 z_d。"""
    clean_z, inj_z = [], []
    for ts in seeds:
        train = [f for f, s in zip(files, seeds) if s != ts]
        test = [f for f, s in zip(files, seeds) if s == ts][0]
        hampel, grp, _ = build_baseline(train)

        rec = load(test)
        all_w = sorted({w for _, wm in rec.items() for w in wm})
        for imsi, wm in rec.items():
            seq = state_seq(wm, all_w)
            na = sum(1 for s in seq if s != "absent")
            lf = sum(1 for s in seq if s == "lte") / na if na else 0.5
            gname = "edge" if lf >= EDGE_SPLIT else "resident"

            if imsi in hampel:
                med, sig = hampel[imsi]
            else:
                cd = grp[gname]
                med = float(np.median(cd)) if cd else 2.0
                mad = float(np.median(np.abs(np.array(cd) - med))) if cd else 1.0
                sig = 1.4826 * mad if mad > 0 else 1.0

            # 乾淨:該 seed 中實際發生的每一次停留事件
            for d in dwell_events(seq):
                clean_z.append(robust_z(d, med, sig))

            # 注入:以目標 z 反推注入長度(與 run_Hi_experiments.py 同法)
            for target_z in (1.5, 2.5, 4.0):
                L = max(2, int(round(med + target_z * sig)))
                inj = len(all_w) // 2
                while inj < len(seq) - L and seq[inj] != "mmw":
                    inj += 1
                if inj >= len(seq) - L:
                    continue
                inj_z.append(robust_z(L, med, sig))
    return np.array(clean_z), np.array(inj_z)


# ==========================================================================
# 繪圖
# ==========================================================================
def draw(clean_z, inj_z, out_path, lang="en"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch

    if lang == "zh":
        for cand in ("Noto Sans CJK TC", "Microsoft JhengHei", "PingFang TC",
                     "Noto Sans TC", "WenQuanYi Zen Hei"):
            try:
                matplotlib.rcParams["font.sans-serif"] = [cand]
                matplotlib.rcParams["axes.unicode_minus"] = False
                break
            except Exception:
                continue
        T = dict(
            title="H_i-D1:證據強度分級(信任狀態由階層式融合決定)",
            xlabel="robust z 統計量  $z_d$", ylabel="事件數",
            none="無 D1 證據  $z_d < \\tau_{warn}$",
            warn="warning evidence  $\\tau_{warn} \\leq z_d < \\tau_{reject}$",
            strong="strong evidence  $z_d \\geq \\tau_{reject}$",
            clean="乾淨資料", inj="注入事件",
            none_s="無證據", warn_s="warning", strong_s="strong",
            tail="尾端 %d 筆 > 圖示範圍(max $z_d$ = %.1f)",
            maph="證據  →  信任狀態", note="D1 單獨違反不構成 hard veto",
        )
        rows = [
            ("H_i-D2 violated（瞬移）", "rejected", C_STRONG, "hard veto"),
            ("D1 strong  +  交叉佐證／多窗持續", "rejected", C_STRONG, ""),
            ("D1 strong  單獨", "low-trust / investigation", C_WARN, "← 舊圖誤標為 rejected"),
            ("D1 warning", "low-trust", C_WARN, ""),
            ("D1 none", "trusted", C_TRUST, ""),
        ]
    else:
        T = dict(
            title="H_i-D1: evidence strength (trust state is decided by hierarchical fusion)",
            xlabel="robust z statistic  $z_d$", ylabel="events",
            none="no D1 evidence  $z_d < \\tau_{warn}$",
            warn="warning evidence  $\\tau_{warn} \\leq z_d < \\tau_{reject}$",
            strong="strong evidence  $z_d \\geq \\tau_{reject}$",
            clean="clean data", inj="injected events",
            none_s="none", warn_s="warning", strong_s="strong",
            tail="%d events beyond axis (max $z_d$ = %.1f)",
            maph="evidence  →  trust state",
            note="D1 alone is never a hard veto",
        )
        rows = [
            ("H_i-D2 violated (teleport)", "rejected", C_STRONG, "hard veto"),
            ("D1 strong  +  corroboration / persistence", "rejected", C_STRONG, ""),
            ("D1 strong  alone", "low-trust / investigation", C_WARN,
             "← previously mislabelled"),
            ("D1 warning", "low-trust", C_WARN, ""),
            ("D1 none", "trusted", C_TRUST, ""),
        ]

    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(14, 5.4), gridspec_kw={"width_ratios": [1.15, 1]})

    # ---------------- 左:z_d 分布,依證據等級著色 ----------------
    # 重尾裁切:主圖聚焦門檻鄰域,尾端筆數另行標註
    XMAX = 8.0
    allz = np.concatenate([clean_z, inj_z])
    n_tail = int(np.sum(allz > XMAX))
    zmax = float(allz.max())

    bins = np.linspace(0, XMAX, 41)
    ax.hist(clean_z, bins=bins, color=C_NONE, alpha=0.78, label=T["clean"])
    ax.hist(inj_z, bins=bins, color=C_STRONG, alpha=0.55, label=T["inj"])
    # log 縱軸:z_d 分布極度右偏(眾數在 0 附近),線性軸會把門檻鄰域壓平
    ax.set_yscale("log")
    ax.set_ylim(0.7, None)

    ax.axvspan(0, TAU_WARN, color=C_NONE, alpha=0.06)
    ax.axvspan(TAU_WARN, TAU_REJECT, color=C_WARN, alpha=0.14)
    ax.axvspan(TAU_REJECT, XMAX, color=C_STRONG, alpha=0.09)
    ax.axvline(TAU_WARN, color=C_WARN, ls="--", lw=1.8)
    ax.axvline(TAU_REJECT, color=C_STRONG, ls="--", lw=1.8)

    # 證據等級色帶:x 用資料座標、y 用軸座標,故與 log 縱軸相容
    from matplotlib.patches import Rectangle
    tr = ax.get_xaxis_transform()
    for x0, x1, colour, key in ((0, TAU_WARN, C_NONE, "none"),
                                (TAU_WARN, TAU_REJECT, C_WARN, "warn"),
                                (TAU_REJECT, XMAX, C_STRONG, "strong")):
        ax.add_patch(Rectangle((x0, -0.135), x1 - x0, 0.095, transform=tr,
                               facecolor=colour, alpha=0.6, edgecolor="white",
                               lw=1.2, clip_on=False, zorder=5))
        ax.text((x0 + x1) / 2, -0.0875, T[key + "_s"], transform=tr,
                ha="center", va="center", fontsize=9.5, color="white",
                weight="bold", zorder=6)

    ax.annotate(r"$\tau_{warn}=%g$" % TAU_WARN, xy=(TAU_WARN, 0.93),
                xytext=(TAU_WARN - 1.5, 0.93), xycoords=tr, textcoords=tr,
                fontsize=10, color="#8a7220", va="center",
                arrowprops=dict(arrowstyle="->", color="#8a7220", lw=1.2))
    ax.annotate(r"$\tau_{reject}=%g$" % TAU_REJECT, xy=(TAU_REJECT, 0.80),
                xytext=(TAU_REJECT + 0.5, 0.80), xycoords=tr, textcoords=tr,
                fontsize=10, color=C_STRONG, va="center",
                arrowprops=dict(arrowstyle="->", color=C_STRONG, lw=1.2))
    if n_tail:
        ax.text(0.985, 0.60, T["tail"] % (n_tail, zmax), transform=ax.transAxes,
                ha="right", va="center", fontsize=8.5, color=C_GRAY,
                style="italic")

    ax.set_xlabel(T["xlabel"], fontsize=11, labelpad=34)
    ax.set_ylabel(T["ylabel"], fontsize=11)
    ax.set_xlim(0, XMAX)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(alpha=0.22, axis="y", which="both")

    # ---------------- 右:證據 → 信任狀態 對應 ----------------
    bx.axis("off")
    bx.set_xlim(0, 1); bx.set_ylim(0, 1)
    bx.text(0.5, 0.95, T["maph"], ha="center", fontsize=13, weight="bold")

    y = 0.80
    for cond, state, colour, tag in rows:
        bx.text(0.02, y, cond, fontsize=10.5, va="center", ha="left")
        arr = FancyArrowPatch((0.545, y), (0.615, y), arrowstyle="-|>",
                              mutation_scale=13, lw=1.4, color=C_GRAY)
        bx.add_patch(arr)
        bx.text(0.635, y, state, fontsize=10.5, va="center", ha="left",
                color=colour, weight="bold")
        if tag:
            bx.text(0.635, y - 0.052, tag, fontsize=8.5, va="center",
                    ha="left", color=C_GRAY, style="italic")
            y -= 0.155
        else:
            y -= 0.13

    bx.axhline(0.075, xmin=0.02, xmax=0.98, color="#CCCCCC", lw=1)
    bx.text(0.5, 0.035, T["note"], ha="center", fontsize=10, style="italic",
            color=C_GRAY)

    fig.suptitle(T["title"], fontsize=12.5, y=0.985)
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    fig.savefig(out_path, dpi=200)
    print(f"圖已存: {out_path}")


# ==========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--lang", choices=["en", "zh"], default="en",
                    help="zh 需系統已安裝中文字型,否則會出現缺字方塊")
    args = ap.parse_args()

    out_dir = args.out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    search = [args.data_dir] if args.data_dir else [
        SI_DIR, os.path.join("seeds", "si_lstm_seeds"), "."]
    files = []
    for d in search:
        files = sorted(glob.glob(os.path.join(d, "ues1_t300_seed*.txt")))
        if len(files) >= 2:
            break
    if len(files) < 2:
        print(f"資料不足(找到 {len(files)} 檔)。用 --data-dir 指定 seed 目錄。")
        return
    seeds = [os.path.basename(f).split("seed")[-1].replace(".txt", "")
             for f in files]
    print(f"載入 {len(seeds)} seeds: {seeds}")

    clean_z, inj_z = collect(files, seeds)

    def share(a):
        n = len(a)
        return (np.mean(a < TAU_WARN), np.mean((a >= TAU_WARN) & (a < TAU_REJECT)),
                np.mean(a >= TAU_REJECT), n)

    for name, arr in (("乾淨", clean_z), ("注入", inj_z)):
        none_, warn_, strong_, n = share(arr)
        print(f"  {name}事件 n={n}: none {none_:.1%} / warning {warn_:.1%} "
              f"/ strong {strong_:.1%}")
    print("\n注意:上列為『證據強度』分布,非信任狀態分布。"
          "strong evidence 單獨僅得 low-trust(4.8.5)。")

    draw(clean_z, inj_z, os.path.join(out_dir, "fig_Hi_D1_grading.png"),
         lang=args.lang)


if __name__ == "__main__":
    main()
