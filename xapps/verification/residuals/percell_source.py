#!/usr/bin/env python3
"""
percell_source.py — 第二階段新輸入層（規格 docs/thesis/phase2_percell_spec_v0.md §4、§9.1；
語意 docs/thesis/report_semantics_spec_v0.md §2 D-a～D-f）。讀 r9 輸出（D-30P）。

輸入檔（每 seed 之 aux 目錄）：
  DlE2RlcStats_percell.txt  % start end EventCellId IMSI LCID nTxPDUs TxBytes nRxPDUs RxBytes delaySumNs
                            自 t=0 起累計（依事件自身 cell），本模組逐 (cell, IMSI, LCID) 差分 → D-a、D-b
  DlE2RlcStats_r9rx.txt     % start end EventCellId IMSI LCID nRxPDUs nRxZeroDelay nRxNoRlcTag nRxTagUnknown（累計）→ O-4
  DlE2RlcStats_exact.txt    % start end CellId IMSI LCID ... delaySumNs（每 UE 合計，累計）→ 檢查 X1
  R9_enb_uemap.txt          % timeNs cellId rnti IMSI ueManagerState → O-1 eNB 側 GetUeMap()（F5）
  R9_ue_rrc.txt             % timeNs IMSI lteCell lteRnti lteState mmCell mmRnti mmState → O-1 UE 側

輸出（窗 k = [k, k+1) 秒，k = 0…max_window）：
  si_windows(aux, zero=False)   [(k, {cell: {imsi: delay_ms}})]；delay = Δ delaySumNs ÷ (ΔnRx − ΔnZero)（zero=True 時分母為 ΔnRx）；
                                分母 0 → 該 (cell, UE) 缺值（不出現，D-f）。cell 含 LTE 1（呼叫端決定是否使用）
  traffic_lists(aux)            {k: {cell: set(IMSI with ΔnTx > 0)}}            C_i (B)
  enb_lists(aux)                {k: {cell: set(IMSI)}}，窗末後之報表時點（LTE、mmWave 各一）依 cell 合併   C_i (A)
  serving(aux)                  {k: {imsi: (mmCell, mmState)}}，取窗末後第一個 UE RRC 時點   D-c
自我檢查 check(aux)：X1 Σ_cell Δ = exact Δ（整數逐位）；X2 同一窗之各 eNB 報表時點中每個 cell 只出現一次（LTE +0.5 ms、mmWave +0.8 ms）；
X3 每窗每 UE 之 serving mmCell 皆在其 enb 名單中（mmState = 9 時）。任一不符 → 列出，呼叫端應停止。
"""
import os, gzip, collections

NS = 1_000_000_000


def _open(path):
    if os.path.exists(path):
        return open(path)
    if os.path.exists(path + ".gz"):
        return gzip.open(path + ".gz", "rt")
    raise FileNotFoundError(path)


def _rows(path):
    with _open(path) as fh:
        for line in fh:
            if line[0] == "%" or not line.strip():
                continue
            yield line.split()


def _diff_cum(path, key_idx, val_idx, max_window):
    """累計檔 → {k: {key: (Δvals…)}}；key 由 key_idx 欄組成，k = start // 1e9"""
    last = {}
    out = collections.defaultdict(dict)
    for p in _rows(path):
        k = int(p[0]) // NS
        key = tuple(int(p[i]) for i in key_idx)
        v = tuple(int(p[i]) for i in val_idx)
        prev = last.get(key, (0,) * len(v))
        d = tuple(a - b for a, b in zip(v, prev))
        if any(x < 0 for x in d):
            raise ValueError(f"{os.path.basename(path)} 累計值下降 {key} k={k}")
        last[key] = v
        if max_window is None or k <= max_window:
            out[k][key] = d
    return out


def percell_delta(aux, max_window=299):
    """{k: {(cell, imsi, lcid): (dnTx, dTxB, dnRx, dRxB, dSumNs)}}"""
    return _diff_cum(os.path.join(aux, "DlE2RlcStats_percell.txt"), (2, 3, 4), (5, 6, 7, 8, 9), max_window)


def zero_delta(aux, max_window=299):
    """{k: {(cell, imsi, lcid): (dnRx, dZero, dNoTag, dUnknown)}}"""
    return _diff_cum(os.path.join(aux, "DlE2RlcStats_r9rx.txt"), (2, 3, 4), (5, 6, 7, 8), max_window)


def si_windows(aux, zero=False, max_window=299, _pc=None, _z=None):
    pc = _pc or percell_delta(aux, max_window)
    z = _z or zero_delta(aux, max_window)
    out = []
    for k in sorted(pc):
        acc = collections.defaultdict(lambda: [0, 0])          # (cell, imsi) → [sumNs, n]
        for (c, i, l), d in pc[k].items():
            n = d[2] - (0 if zero else z.get(k, {}).get((c, i, l), (0, 0))[1])
            acc[(c, i)][0] += d[4]; acc[(c, i)][1] += n
        cells = collections.defaultdict(dict)
        for (c, i), (s, n) in acc.items():
            if n > 0:
                cells[c][i] = s / n / 1e6                       # ms
        out.append((k, dict(cells)))
    return out


def traffic_lists(aux, max_window=299, _pc=None):
    pc = _pc or percell_delta(aux, max_window)
    out = {}
    for k, d in pc.items():
        L = collections.defaultdict(set)
        for (c, i, l), v in d.items():
            if v[0] > 0:
                L[c].add(i)
        out[k] = dict(L)
    return out


def _instants(path, tcol):
    by_t = collections.defaultdict(list)
    for p in _rows(path):
        by_t[int(p[tcol])].append(p)
    return by_t


def enb_lists(aux, max_window=299, all_instants=False):
    by_t = _instants(os.path.join(aux, "R9_enb_uemap.txt"), 0)
    per_k = collections.defaultdict(list)
    for t in sorted(by_t):
        k = t // NS - 1                                        # 窗末 (k+1)·1e9 之後之報表 → 窗 k
        if 0 <= k <= max_window:
            L = collections.defaultdict(set)
            for p in by_t[t]:
                L[int(p[1])].add(int(p[3]))
            per_k[k].append((t, dict(L)))
    if all_instants:
        return per_k
    out = {}
    for k, v in per_k.items():                                 # LTE（cell 1）於 +0.5 ms、mmWave（2–8）於 +0.8 ms 各報一次 → 依 cell 合併
        m = {}
        for _, L in v:
            m.update(L)
        out[k] = m
    return out


def serving(aux, max_window=299):
    by_t = _instants(os.path.join(aux, "R9_ue_rrc.txt"), 0)
    out = {}
    for t in sorted(by_t):
        k = t // NS - 1
        if 0 <= k <= max_window and k not in out:
            out[k] = {int(p[1]): (int(p[5]), int(p[7])) for p in by_t[t]}
    return out


def xapp_windows(aux, zero=False, max_window=299):
    """融合層用之單一歸屬視圖（phase2_percell_spec_v0.md §4 H_i-D1；步 3／4）：[(k, {cell: {imsi: delay_ms | None}})]。
    每個已連線（D-c，mmState = 9）之 UE 每窗恰屬一個 cell：
      * 當窗有 mmWave Rx PDU（任何 cell ≠ 1，ΔnRx > 0）→ 該 mmWave cell；須唯一且 = D-c serving cell，否則報錯；
      * 已連線但當窗無 mmWave Rx → LTE 錨點 cell 1（= 新 D1 定義之「mmWave 缺席」）。
    延遲 = 該 (cell, UE) 之區間平均（同 si_windows）；分母 0（例：Rx 全為零延遲 PDU、zero=False）→ None（缺值，D-f）。
    未連線之 UE 不出現（D-f）；未連線卻有 Rx → 報錯。mmWave cell 之非 None 值與 si_windows 逐值相同（check_xapp_view）。"""
    pc = percell_delta(aux, max_window); z = zero_delta(aux, max_window); sv = serving(aux, max_window)
    out = []
    for k in sorted(pc):
        acc = collections.defaultdict(lambda: [0, 0, 0])      # (cell, imsi) → [sumNs, n_valid, nRx]
        for (c, i, l), d in pc[k].items():
            n = d[2] - (0 if zero else z.get(k, {}).get((c, i, l), (0, 0))[1])
            a = acc[(c, i)]; a[0] += d[4]; a[1] += n; a[2] += d[2]
        S = sv.get(k)
        if S is None:
            raise ValueError(f"{aux}: 窗 {k} 無 UE RRC 時點")
        cells = collections.defaultdict(dict)
        for i, (mc, ms) in sorted(S.items()):
            mm = sorted(c for (c, j), a in acc.items() if j == i and c != 1 and a[2] > 0)
            if ms != 9:
                if any(j == i and a[2] > 0 for (c, j), a in acc.items()):
                    raise ValueError(f"{aux}: 窗 {k} IMSI {i} 未連線卻有 Rx")
                continue
            if len(mm) > 1 or (mm and mm[0] != mc):
                raise ValueError(f"{aux}: 窗 {k} IMSI {i} mmWave Rx 於 {mm}，serving {mc}")
            c = mm[0] if mm else 1
            sm, n, _ = acc.get((c, i), (0, 0, 0))
            cells[c][i] = sm / n / 1e6 if n > 0 else None
        for (c, j), a in acc.items():
            if a[2] > 0 and j not in S:
                raise ValueError(f"{aux}: 窗 {k} IMSI {j} 有 Rx 但無 RRC 列")
        out.append((k, {c: cells[c] for c in sorted(cells)}))
    return out


def ci_lists(aux, max_window=299):
    """C_i (A)：{k: ({mmWave cell: set(IMSI)}, 錨點 cell 1 之 set)}（enb_lists 之 RRC 名單）"""
    out = {}
    for k, L in enb_lists(aux, max_window).items():
        out[k] = ({c: set(v) for c, v in L.items() if c != 1}, set(L.get(1, set())))
    return out


def check_xapp_view(aux, zero=False, max_window=299):
    """xapp_windows 之 mmWave 非 None 值須與 si_windows 之 mmWave 值（集合與數值）逐位相同"""
    a = dict(si_windows(aux, zero, max_window)); b = dict(xapp_windows(aux, zero, max_window))
    bad = 0; n_none = 0; n_lte = 0
    for k in a:
        for c in set(a[k]) | set(b.get(k, {})):
            if c == 1:
                n_lte += len(b.get(k, {}).get(1, {}))
                continue
            va = a[k].get(c, {}); vb = b.get(k, {}).get(c, {})
            n_none += sum(v is None for v in vb.values())
            if {i: v for i, v in vb.items() if v is not None} != va:
                bad += 1
    return {"mismatch_cell_windows": bad, "mm_none_ue_windows": n_none, "lte_ue_windows": n_lte, "PASS": bad == 0}


def check(aux, max_window=299):
    rep = {}
    pc = percell_delta(aux, max_window)
    ex = _diff_cum(os.path.join(aux, "DlE2RlcStats_exact.txt"), (3, 4), (5, 6, 7, 8, 9), max_window)
    bad = 0
    for k in pc:
        s = collections.defaultdict(lambda: [0] * 5)
        for (c, i, l), d in pc[k].items():
            for j in range(5):
                s[(i, l)][j] += d[j]
        keys = set(s) | set(ex.get(k, {}))
        for key in keys:
            if tuple(s.get(key, [0] * 5)) != ex.get(k, {}).get(key, (0,) * 5):
                bad += 1
    rep["X1_percell_sum_eq_exact_mismatch"] = bad
    pk = enb_lists(aux, max_window, all_instants=True)
    rep["X2_windows"] = len(pk)
    rep["X2_instants_per_window"] = sorted({len(v) for v in pk.values()})
    # X2：同一窗之各報表時點，每個 cell 只出現一次（LTE 與 mmWave 分屬不同時點）
    rep["X2_mismatch"] = sum(1 for v in pk.values()
                             if sum(len(L) for _, L in v) != len({c for _, L in v for c in L}))
    sv = serving(aux, max_window); el = enb_lists(aux, max_window)
    x3 = 0; n3 = 0
    for k, d in sv.items():
        for i, (mc, ms) in d.items():
            if ms == 9:
                n3 += 1
                x3 += i not in el.get(k, {}).get(mc, set())
    rep["X3_connected_ue_windows"] = n3
    rep["X3_not_in_enb_list"] = x3
    rep["windows"] = [min(pc), max(pc)]
    rep["PASS"] = bad == 0 and rep["X2_mismatch"] == 0 and x3 == 0
    return rep


if __name__ == "__main__":
    import sys, json
    for aux in sys.argv[1:]:
        print(os.path.basename(aux.rstrip("/")), json.dumps(check(aux), ensure_ascii=False))
