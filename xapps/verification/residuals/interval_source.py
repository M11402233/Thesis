#!/usr/bin/env python3
"""interval_source.py — 區間延遲來源（語意規格 v0.1 §5、§6；2026-11-13）。

以環境變數 ZT_DELAY_SOURCE 選擇 TraceReplaySource 之延遲語意：
  cumulative     （預設）舊行為：p[10] = 自 t=0 起之累計平均（不經本模組，zt_kpm_xapp 原路徑逐位不變）
  reconstructed  由 6 位有效數字之累計平均與累計 nRxPDUs 反推每窗平均：
                 d_w = (D_w·N_w − D_{w−1}·N_{w−1}) / (N_w − N_{w−1})；窗 0 = 累計值（計算器於 t=0 建立，R-3）
  exact          由 R-5 加裝之 <file>_exact.txt（整數 Σdelay_ns 與 nRxPDUs）差分：d_w = ΔΣ / ΔN（精確）
  percell        第二階段（phase2_percell_spec_v0.md §4、§9.1 Q-P5）：r9 之 _percell／_r9rx，cell = 事件自身 cell（D-b），
                 排除零延遲 PDU；分母 0 → 該 (cell, UE) 缺值（D-f，不出現、不報錯）。僅限登錄 r9 aux 之資料集（d30p）
  percell_zero   同上但含零延遲 PDU（Q-P5 之對照版本）
  percell*：parse_interval（→ TraceReplaySource、融合層）回傳 percell_source.xapp_windows 之單一歸屬視圖
           （延遲缺值為 None；mmWave 非 None 值 = si_windows）；cell_delay_means（S_i／E9 族）與 si_cells 直接用 si_windows。
共同約定：
  * cell 歸屬**沿用主檔列之 cell**（= 最後一筆 PDU 所在 cell；規格 F1）。每 cell 拆分屬第二階段，本模組不改歸屬。
  * 當窗無新 Rx PDU（ΔN = 0）時延遲為缺值（D-f）。缺值時**直接報錯（fail-closed）**，不填 0、不沿用舊值；
    D-30 之 72,000 個 (UE, 窗) 皆有新 Rx（explore_review_ch4.json X2），故目前不應觸發。
  * 輸出形狀與 TraceReplaySource 相同：[(w, {cell: {imsi: delay_ms}})]。
"""
import os, collections

MODES = ("cumulative", "reconstructed", "exact", "percell", "percell_zero")


def mode():
    m = os.environ.get("ZT_DELAY_SOURCE", "cumulative")
    if m not in MODES:
        raise SystemExit(f"ZT_DELAY_SOURCE={m!r} 不合法；可用 {MODES}")
    return m


class MissingIntervalDelay(RuntimeError):
    pass


def _rows_old(path):
    """主檔：{(imsi, lcid): {w: (cell, nRx, cumMean_s)}}"""
    R = collections.defaultdict(dict)
    with open(path) as fh:
        fh.readline()
        for line in fh:
            p = line.split("\t")
            if len(p) < 11:
                continue
            try:
                w, cell, imsi, lcid = int(float(p[0])), int(p[2]), int(p[3]), int(p[5])
                R[(imsi, lcid)][w] = (cell, int(p[8]), float(p[10]))
            except ValueError:
                continue
    return R


def exact_path(path):
    base = path[:-4] if path.endswith(".txt") else path
    return base + "_exact.txt"


def _rows_exact(path):
    """R-5 精確檔：{(imsi, lcid): {w: (nRx, sumNs)}}；w = start_ns // 1e9"""
    E = collections.defaultdict(dict)
    with open(path) as fh:
        for line in fh:
            if line[0] == "%":
                continue
            p = line.split("\t")
            E[(int(p[3]), int(p[4]))][int(p[0]) // 10**9] = (int(p[7]), int(p[9]))
    return E


def is_percell(m=None):
    return (m or mode()).startswith("percell")


def valid_vals(v):
    """第二階段：延遲缺值為 None（percell_source.xapp_windows）。回傳非缺值之列表；無 None 時與 list(v.values()) 相同。"""
    return [x for x in v.values() if x is not None]


def mean_valid(v):
    xs = valid_vals(v)
    return float(sum(xs) / len(xs)) if xs else None


def percell_aux(path, m=None):
    import datasets as DS
    m = m or mode()
    if not DS.CFG.get("percell"):
        raise SystemExit(f"ZT_DELAY_SOURCE={m} 只適用登錄 r9 aux 之資料集（目前 ZT_DATASET={DS.NAME}）")
    return os.path.dirname(DS.aux_path(DS.seed_of(path), "x")), DS.CFG["max_window"] - 1


def si_cells(path, m=None):
    """S_i 用：每事件 cell 之區間平均（含 LTE cell 1），[(w, {cell: {imsi: ms}})]"""
    import percell_source as PS
    m = m or mode(); aux, mw = percell_aux(path, m)
    return PS.si_windows(aux, zero=(m == "percell_zero"), max_window=mw)


def ci_lists(path, m=None):
    import percell_source as PS
    aux, mw = percell_aux(path, m)
    return PS.ci_lists(aux, mw)


def parse_percell(path, m):
    import percell_source as PS
    aux, mw = percell_aux(path, m)
    return PS.xapp_windows(aux, zero=(m == "percell_zero"), max_window=mw)


def parse_interval(path, m=None):
    m = m or mode()
    if is_percell(m):
        return parse_percell(path, m)
    R = _rows_old(path)
    E = None
    if m == "exact":
        ep = exact_path(path)
        if not os.path.exists(ep):
            raise SystemExit(f"ZT_DELAY_SOURCE=exact 需要 {ep}（R-5 加裝輸出）")
        E = _rows_exact(ep)
    buf = collections.defaultdict(lambda: collections.defaultdict(dict))
    for (imsi, lcid), S in R.items():
        for w in sorted(S):
            cell, N, D = S[w]
            if m == "reconstructed":
                if w - 1 in S:
                    _, N0, D0 = S[w - 1]
                elif w == min(S) and w == 0:
                    N0, D0 = 0, 0.0
                else:
                    raise MissingIntervalDelay(f"{path}: IMSI {imsi} 窗 {w} 無前一窗累計值，無法反推")
                dn = N - N0
                if dn <= 0:
                    raise MissingIntervalDelay(f"{path}: IMSI {imsi} 窗 {w} 無新 Rx PDU（延遲缺值）")
                d_s = (D * N - D0 * N0) / dn
            else:  # exact
                Ek = E.get((imsi, lcid), {})
                if w not in Ek:
                    raise MissingIntervalDelay(f"{path}: 精確檔缺 IMSI {imsi} 窗 {w}")
                Ne, Se = Ek[w]
                if Ne != N:
                    raise MissingIntervalDelay(f"{path}: IMSI {imsi} 窗 {w} nRx 不一致（主檔 {N}、精確檔 {Ne}）")
                if w - 1 in Ek:
                    N0e, S0e = Ek[w - 1]
                elif w == 0:
                    N0e, S0e = 0, 0
                else:
                    raise MissingIntervalDelay(f"{path}: 精確檔缺 IMSI {imsi} 窗 {w - 1}")
                dn = Ne - N0e
                if dn <= 0:
                    raise MissingIntervalDelay(f"{path}: IMSI {imsi} 窗 {w} 無新 Rx PDU（延遲缺值）")
                d_s = (Se - S0e) / dn * 1e-9
            buf[w][cell][imsi] = d_s * 1000.0   # 與舊 _parse 相同：不分 LCID（D-30 只有 LCID 3）
    return [(w, buf[w]) for w in sorted(buf)]


def results_suffix():
    m = mode()
    return "" if m == "cumulative" else f"_delay_{m}"


def cell_delay_means(path, m=None):
    """與 run_E9_operating_regime／run_Si_reference_ablation／run_adversarial_msweep 之 load_cell_delay 同形：
    {w: {cell: 該 cell 當窗各 UE 延遲之平均 (ms)}}，排除 LTE 錨點（cell 1）。延遲語意依 mode。"""
    out = {}
    for w, cells in (si_cells(path, m) if is_percell(m) else parse_interval(path, m)):
        out[w] = {c: float(sum(u.values()) / len(u)) for c, u in cells.items() if c != 1 and u}
    return out
