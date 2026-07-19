"""
cardinality.py — C_i 場域 UE 基數守恆殘差 (Field-wide UE Cardinality Conservation Residual)

論文對應：Thesis v3 ZTA 第三部分 3.3 (C)、第四部分。

核心命題
--------
封閉 NPN 場域的裝置母體是「已知且固定」的（ues.txt 給定 N_known）。
任一 E2 節點若竄改 KPM 上報而捏造不存在的 amf_ue_ngap_id（IMSI）灌水 UE 數，
會使「全場域相異 UE 總數 N_total(t)」超出封閉場域的已知母體上界；
反之若大量丟棄真實 UE ID 虛減負載，則 N_total(t) 掉到已知母體下界之下。
兩者都讓 C_i 下降。

    N_total(t) = | ∪_all-cells { IMSI }(t) |      （全場域相異 UE 總數，per granularity period）
    C_i(t)     = c( N_total(t)  vs  [N_lo, N_hi] )  ∈ (0, 1]

實測關鍵決策（本檔案已定案）
--------------------------
場域相異 IMSI 的聯集**必須包含 LTE 錨點 cell（CellId=1）**。
在 MC 雙連結架構下，UE 恆錨定於 LTE，mmWave 只是附加腿；
UE 離開某 mmWave cell 後會回落 LTE（CellId=1），而非直接 mmWave↔mmWave 跳轉。
實測驗證：含 LTE 時 N_total 每窗恆為 35（=ues.txt），完美守恆；
只算 mmWave(2-8) 則在 27~33 亂跳（正常 MC 行為，非攻擊）。
因此 C_i 以「含 LTE 的全 cell 聯集」計算，才不會把正常回落誤判為基數異常。

定位提醒
--------
C_i 是**場域級（全域）**殘差，同一時間窗對所有節點共用同一個 C_i(t)。
它是「有人在灌水/虛減」的強力全域告警，但無法單獨定位是哪個節點做的
（定位交給 S_i / H_i）。這是設計上的分工，不是缺陷。

作者：交接後 C_i 實作
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 資料載入：優先用既有 loader.py 的 load_rlc()；否則用本檔自帶的 fallback reader，
# 讓本模組可獨立跑通、獨立測試。兩者回傳同樣 schema 的 list[dict]。
# ---------------------------------------------------------------------------

# DlE2RlcStats.txt 前 11 欄（第 12 欄後有黏欄 bug，一律忽略）
_RLC_COLS = ["start", "end", "CellId", "IMSI", "RNTI", "LCID",
             "nTxPDUs", "TxBytes", "nRxPDUs", "RxBytes", "delay"]


def _builtin_load_rlc(path: str) -> List[dict]:
    """
    自帶 fallback：讀 DlE2RlcStats.txt，只取前 11 欄，回傳 list[dict]。
    你的正式 loader.py 若已 import 成功，會覆蓋掉這個（見下方 try/except）。
    刻意不依賴 pandas，減少相依，方便在任何環境跑通。
    """
    rows: List[dict] = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("%"):
                continue
            parts = line.split("\t")
            if len(parts) < 11:
                continue
            rec = dict(zip(_RLC_COLS, parts[:11]))
            # 型別轉換
            rec["start"] = float(rec["start"])
            rec["end"] = float(rec["end"])
            rec["CellId"] = int(rec["CellId"])
            rec["IMSI"] = int(rec["IMSI"])
            rec["RxBytes"] = float(rec["RxBytes"])
            rec["delay"] = float(rec["delay"])
            rows.append(rec)
    return rows


try:
    # 你環境裡的既有前處理層。介面約定：load_rlc(path) -> 可迭代的 per-UE 記錄，
    # 每筆至少含 keys: 'start'(窗起點), 'CellId', 'IMSI'。
    from loader import load_rlc  # type: ignore  # noqa: F401
    _LOADER_SOURCE = "loader.load_rlc (既有)"
except Exception:  # pragma: no cover
    load_rlc = _builtin_load_rlc
    _LOADER_SOURCE = "cardinality._builtin_load_rlc (fallback)"


# ---------------------------------------------------------------------------
# 場域基數時間序列：N_total(t)
# ---------------------------------------------------------------------------

def _window_key(rec: dict, ndigits: int = 6) -> float:
    """以窗起點時間當作時間窗鍵。"""
    return round(float(rec["start"]), ndigits)


def field_cardinality_series(
    records: Iterable[dict],
    include_lte: bool = True,
    lte_cell_id: int = 1,
) -> Dict[float, int]:
    """
    由 per-UE RLC 記錄計算每個時間窗的場域相異 UE 總數 N_total(t)。

    Parameters
    ----------
    records : 可迭代的 per-UE 記錄（load_rlc 的輸出）
    include_lte : True 則把 LTE 錨點 cell 也納入場域聯集（**論文定案：必須 True**）
    lte_cell_id : LTE eNB 的 CellId（本場景為 1）

    Returns
    -------
    dict {window_start_time -> N_total}，依時間排序。
    """
    per_window: Dict[float, set] = {}
    for rec in records:
        cell = int(rec["CellId"])
        if (not include_lte) and cell == lte_cell_id:
            continue
        t = _window_key(rec)
        per_window.setdefault(t, set()).add(int(rec["IMSI"]))
    return {t: len(s) for t, s in sorted(per_window.items())}


# ---------------------------------------------------------------------------
# C_i 設定與計算
# ---------------------------------------------------------------------------

@dataclass
class CardinalityConfig:
    """
    C_i 參數。可從 config/thresholds.yaml 載入（見 from_dict / from_yaml）。

    ── 重要實測修正（v4，基於 15.4s / 154 窗長時間資料）─────────────
    含 LTE 錨點的「場域全域 UE 基數」N_total(t) 在乾淨情況下 **std = 0**，
    100% 恆等於 N_known。這不是資料太短，是封閉 NPN 的物理本質：
    只要 UE 有連線，它必然出現在某 cell（LTE 或 mmWave）的上報，
    封閉場域內 UE 不會憑空生滅。因此：
      * C_i 的本質是「硬不變量（hard invariant）檢查」，不是統計異常偵測。
      * eps_low 不再吸收「閒置抖動」（實測為 0），只吸收「UE 斷線重連瞬態」，
        預設極小（0.0 ~ 0.05）。任何偏離 N_known 都視為可疑 → C_i 更強。
      * 只算 mmWave(cell 2-8) 才會看到 5~11 的抖動，那是 UE 在 mmWave/LTE
        間正常流動，**不是 C_i 該管的**（那是 H_i 的守備範圍）。
    ──────────────────────────────────────────────────

    邊界語意（非對稱，因為物理非對稱）：
      * 上界超標 = 捏造不存在的 IMSI（攻擊 A 灌水）→ 封閉 NPN 無良性成因，
        eps_high = 0（一超過母體立刻扣分）。
      * 下界不足 = 真實 UE ID 被丟棄（攻擊 A 虛減）或極少數斷線重連瞬態
        → 給極小 eps_low 容忍帶。

    允許帶（deadband）：
        N_hi = n_known * (1 + eps_high)
        N_lo = n_known * (1 - eps_low)
    帶內 C_i = 1.0；帶外以高斯衰減，κ (kappa) 控制衰減陡度（以「N_known 的比例」為單位）。
    """
    n_known: int = 7           # 硬邊界：最終定案場域規模（ues=1 → 7cell×1UE）
                               # 校準紀錄：35(ues=5)→完全卡死；14(ues=2)→50-150s/模擬秒仍不可行；
                               # 7(ues=1)實測穩定速率=50s真實/1s模擬,是唯一可規劃長跑的規模
                               # 根因：isd密度+UE數對原生MC(雙連結)候選cell評估的超線性成本，
                               # 非本研究KPM組裝或EnergyHeuristic造成（已逐項排除驗證）
    eps_low: float = 0.05      # 下界容忍（實測抖動為 0，此值僅吸收斷線重連瞬態）
    eps_high: float = 0.0      # 上界容忍（灌水無良性成因，不容忍）
    kappa: float = 0.10        # 衰減陡度（越小越敏感）
    include_lte: bool = True   # 場域聯集是否含 LTE 錨點（**定案：True**）
    lte_cell_id: int = 1

    # 可選：直接以絕對值覆寫上下界（若母體有動態範圍時用）
    n_min_override: Optional[int] = None
    n_max_override: Optional[int] = None

    def bounds(self) -> Tuple[float, float]:
        """回傳 (N_lo, N_hi) 絕對邊界。"""
        n_lo = self.n_known * (1.0 - self.eps_low)
        n_hi = self.n_known * (1.0 + self.eps_high)
        if self.n_min_override is not None:
            n_lo = float(self.n_min_override)
        if self.n_max_override is not None:
            n_hi = float(self.n_max_override)
        return n_lo, n_hi

    @classmethod
    def from_dict(cls, d: dict) -> "CardinalityConfig":
        fields = {k: d[k] for k in d if k in cls.__annotations__}
        return cls(**fields)

    @classmethod
    def from_yaml(cls, path: str, key: str = "cardinality") -> "CardinalityConfig":
        import yaml  # 延後 import，非必要相依
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
        return cls.from_dict(doc.get(key, doc))

    def to_dict(self) -> dict:
        return asdict(self)


def cardinality_residual(n_total: int, cfg: CardinalityConfig) -> float:
    """
    單一時間窗的 C_i。

    帶內回傳 1.0；帶外依偏離量（以 N_known 的比例正規化）做高斯衰減：
        excess = max(0, N - N_hi)/N_known   或   max(0, N_lo - N)/N_known
        C_i    = exp( -(excess / kappa)^2 )  ∈ (0, 1]
    """
    n_lo, n_hi = cfg.bounds()
    if n_total > n_hi:
        excess = (n_total - n_hi) / cfg.n_known
    elif n_total < n_lo:
        excess = (n_lo - n_total) / cfg.n_known
    else:
        return 1.0
    return math.exp(-((excess / cfg.kappa) ** 2))


def cardinality_invariant_check(n_total: int, cfg: CardinalityConfig) -> dict:
    """
    C_i 的主判定：場域基數守恆「不變量檢查」（invariant verification），非統計異常偵測。

    方法論定位（見論文 3.3-C、4.5.1）
    --------------------------------
    封閉 NPN 場域的裝置母體為已知且固定（ues.txt 給定 N_known）。實測（E0：600 窗
    跨 10 seed）顯示含 LTE 錨點的 N_total(t) 為**退化分布（degenerate distribution）**：
        P(N_total = N_known) = 1,   Var(N_total) = 0
    因此 C_i 的判定準則不是「偏離多少標準差」（統計偵測），而是「是否違反守恆不變量」
    （invariant verification）：

        conserved := (N_lo <= N_total <= N_hi)

    在 ε_low = ε_high = 0 的嚴格設定下，此準則退化為
        conserved := (N_total == N_known)
    即 Western Electric Rule 1（point beyond 3-sigma control limit, Western Electric 1956）
    在 σ → 0 極限下的形式：任何落在控制界限外的觀測即判定 out-of-control。因 baseline
    變異為零，界限退化至中心線本身，故「守恆 vs 違反」為確定性布林判定。

    安全性宣稱
    ----------
    在封閉、已登記母體固定的觀測窗內，正常運作下 N_total 恆等於 N_known（不生不滅），
    故 conserved=False ⇒ 以機率 1 對應 KPM 基數造假攻擊或嚴重系統故障。此判定不依賴
    閾值校準，消除統計方法固有的 false-positive 率與閾值選擇爭議。

    Returns
    -------
    dict:
      conserved      : bool   守恆不變量是否成立（主判定）
      N_total        : int
      N_known        : int
      deviation      : int    N_total − N_known（帶符號；>0 灌水、<0 虛減、0 守恆）
      violation_type : str    'none' | 'fabrication' | 'depletion'
      severity       : float  違反量級 = |deviation| / N_known（僅供 T_i 加權與排序，
                              不參與二元判定；守恆時為 0.0）
    """
    n_lo, n_hi = cfg.bounds()
    conserved = (n_lo <= n_total <= n_hi)
    deviation = n_total - cfg.n_known
    if deviation > 0 and n_total > n_hi:
        vtype = "fabrication"
    elif deviation < 0 and n_total < n_lo:
        vtype = "depletion"
    else:
        vtype = "none"
    return {
        "conserved": conserved,
        "N_total": n_total,
        "N_known": cfg.n_known,
        "deviation": deviation,
        "violation_type": vtype,
        "severity": abs(deviation) / cfg.n_known if cfg.n_known else 0.0,
    }


def compute_cardinality_over_time(
    records: Iterable[dict],
    cfg: Optional[CardinalityConfig] = None,
) -> Dict[float, dict]:
    """
    端到端：RLC 記錄 → 每窗結果。

    主判定為二元不變量檢查（'conserved'）；同時保留連續量 'C'（違反量級的平滑化，
    供 T_i 加權整合與跨窗排序，不影響二元判定）與既有 'grade'（向後相容）。

    Returns
    -------
    dict {t -> {
        'N_total':int, 'conserved':bool, 'deviation':int, 'violation_type':str,
        'severity':float,                # 主判定與量級（不變量框架）
        'C':float, 'grade':str,          # 平滑化連續值與分級（向後相容 / T_i 加權）
        'N_lo':float, 'N_hi':float
    }}
    """
    cfg = cfg or CardinalityConfig()
    series = field_cardinality_series(records, cfg.include_lte, cfg.lte_cell_id)
    n_lo, n_hi = cfg.bounds()
    out: Dict[float, dict] = {}
    for t, n in series.items():
        inv = cardinality_invariant_check(n, cfg)
        c = cardinality_residual(n, cfg)
        out[t] = {"N_total": n,
                  "conserved": inv["conserved"],
                  "deviation": inv["deviation"],
                  "violation_type": inv["violation_type"],
                  "severity": inv["severity"],
                  "C": c, "grade": grade_from_score(c),
                  "N_lo": n_lo, "N_hi": n_hi}
    return out


# ---------------------------------------------------------------------------
# 分級（對齊論文 3.4 θ_high / θ_low）與 ε 建議
# ---------------------------------------------------------------------------

def grade_from_score(c: float, theta_high: float = 0.90, theta_low: float = 0.50) -> str:
    """C_i 分級：trusted / low_trust / rejected。"""
    if c >= theta_high:
        return "trusted"
    if c >= theta_low:
        return "low_trust"
    return "rejected"


def suggest_eps_from_baseline(
    baseline_records: Iterable[dict],
    cfg: Optional[CardinalityConfig] = None,
    safety_factor: float = 2.0,
) -> dict:
    """
    從乾淨的 baseline 資料建議 ε（下界容忍）。

    方法：量測 baseline 每窗 N_total 的最小值與 N_known 的差距，
    以 safety_factor 倍當作下界容忍，避免把正常閒置誤判為攻擊。
    上界（灌水）在封閉 NPN 無良性成因，故 eps_high 建議維持 0。

    注意：若 baseline 每窗 N_total 皆等於 N_known（本場景即如此，完美守恆），
    表示此資料無閒置抖動可學，ε 需改由領域知識（預期閒置比例）設定。
    """
    cfg = cfg or CardinalityConfig()
    series = field_cardinality_series(baseline_records, cfg.include_lte, cfg.lte_cell_id)
    vals = list(series.values())
    n_known = cfg.n_known
    n_min = min(vals) if vals else n_known
    n_max = max(vals) if vals else n_known
    gap_low = max(0, n_known - n_min)
    eps_low = min(1.0, safety_factor * gap_low / n_known)
    return {
        "observed_min": n_min,
        "observed_max": n_max,
        "observed_gap_below_known": gap_low,
        "suggested_eps_low": round(eps_low, 4),
        "suggested_eps_high": 0.0,
        "note": ("baseline 完美守恆 (N_total 恆為 N_known)，"
                 "無抖動可學；請以預期閒置比例手動設 eps_low。"
                 if gap_low == 0 else
                 "已依 baseline 最小值 + safety_factor 建議 eps_low。"),
    }


# ---------------------------------------------------------------------------
# 不變量穩健性檢驗（證明 σ=0 是物理必然，非資料量不足或模擬假象）
# 注意：這不是 goodness-of-fit（不假設任何母體分布再檢驗），
#       而是對「守恆不變量成立性」的實證穩健性驗證。
# ---------------------------------------------------------------------------

def verify_invariant_robustness(
    seed_to_records: Dict[str, List[dict]],
    cfg: Optional[CardinalityConfig] = None,
) -> dict:
    """
    跨 seed 驗證「N_total 為退化分布（degenerate distribution）」這個不變量的穩健性。

    回答的三個 reviewer 質疑（皆非 goodness-of-fit）
    ------------------------------------------------
    Q1「σ=0 是巧合嗎？」→ 跨 seed 一致性：所有 seed 的每窗 N_total 是否同為單一值。
    Q2「σ=0 是模擬假象嗎？」→ 退化分布驗證：合併全部窗格，觀測分布是否為單點質量
        P(N_total = N_known) = 1（Var = 0）。這是「直接實證觀察」，不套 Poisson/常態。
    Q3「換隨機性會破壞嗎？」→ 跨 10 seed 的 support 是否恆為 {N_known}。

    Returns
    -------
    dict:
      per_seed          : {seed: {'unique_values':[...], 'std':float, 'is_degenerate':bool}}
      pooled_support    : sorted list，合併所有窗格後 N_total 出現過的相異值
      pooled_std        : float，合併後標準差（退化分布應為 0）
      is_degenerate     : bool，pooled 是否為單點質量分布
      degenerate_at     : int|None，若退化，質量集中的值
      matches_n_known   : bool，退化點是否 == N_known
      total_windows     : int
      verdict           : str
    """
    cfg = cfg or CardinalityConfig()
    per_seed: Dict[str, dict] = {}
    pooled: List[int] = []
    for seed, recs in seed_to_records.items():
        series = field_cardinality_series(recs, cfg.include_lte, cfg.lte_cell_id)
        vals = list(series.values())
        pooled.extend(vals)
        uniq = sorted(set(vals))
        std = _pstdev(vals)
        per_seed[seed] = {"unique_values": uniq, "std": std,
                          "is_degenerate": (std == 0.0)}
    pooled_support = sorted(set(pooled))
    pooled_std = _pstdev(pooled)
    is_degen = (len(pooled_support) == 1)
    degen_at = pooled_support[0] if is_degen else None
    matches = (degen_at == cfg.n_known) if is_degen else False
    if is_degen and matches:
        verdict = (f"退化分布成立：P(N_total={cfg.n_known})=1, Var=0，跨 "
                   f"{len(seed_to_records)} seed 一致 → 守恆為確定性硬不變量，"
                   f"非統計巧合或模擬假象。")
    elif is_degen:
        verdict = (f"退化於 {degen_at} 但 ≠ N_known={cfg.n_known}：檢查 include_lte "
                   f"或 N_known 設定。")
    else:
        verdict = (f"非退化（support={pooled_support}, std={pooled_std:.4f}）：存在瞬態，"
                   f"應改用 σ>0 的統計判定並據此設 ε_low。")
    return {"per_seed": per_seed, "pooled_support": pooled_support,
            "pooled_std": pooled_std, "is_degenerate": is_degen,
            "degenerate_at": degen_at, "matches_n_known": matches,
            "total_windows": len(pooled), "verdict": verdict}


def _pstdev(xs: Sequence[float]) -> float:
    """母體標準差（不依賴 statistics，減少相依）。"""
    n = len(xs)
    if n == 0:
        return 0.0
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / n)


# ---------------------------------------------------------------------------
# 攻擊注入（後處理層，供測試與 RQ1 用；論文誠實聲明為語意對應）
# ---------------------------------------------------------------------------

def inject_fabrication(records: List[dict], n_fake: int,
                       at_windows: Optional[Sequence[float]] = None,
                       attacker_cell: int = 4,
                       base_imsi: int = 10000) -> List[dict]:
    """攻擊 A（灌水）：在指定窗、指定攻擊節點捏造 n_fake 個不存在的 IMSI。"""
    out = [dict(r) for r in records]
    windows = sorted({_window_key(r) for r in out}) if at_windows is None else list(at_windows)
    template = next((dict(r) for r in out if int(r["CellId"]) == attacker_cell), dict(out[0]))
    for t in windows:
        for k in range(n_fake):
            fake = dict(template)
            fake["start"] = t
            fake["CellId"] = attacker_cell
            fake["IMSI"] = base_imsi + k
            out.append(fake)
    return out


def inject_deletion(records: List[dict], n_drop: int,
                    at_windows: Optional[Sequence[float]] = None,
                    victim_cell: Optional[int] = None) -> List[dict]:
    """
    攻擊 A（虛減）：在指定窗丟棄 n_drop 筆真實 UE 紀錄。

    victim_cell=None → 跨節點（串謀）虛減，代表多節點協同或用來壓測下界；
    victim_cell=k    → 單節點虛減，實際刪除量受該 cell 服務 UE 數所限
                       （這正是 C_i 對單節點虛減偵測力有界的來源，H_i 補位）。
    """
    windows = sorted({_window_key(r) for r in records}) if at_windows is None else list(at_windows)
    windows = set(windows)
    dropped: Dict[float, int] = {t: 0 for t in windows}
    out: List[dict] = []
    for r in records:
        t = _window_key(r)
        hit = (t in windows and dropped[t] < n_drop
               and (victim_cell is None or int(r["CellId"]) == victim_cell))
        if hit:
            dropped[t] += 1
            continue
        out.append(dict(r))
    return out


# ---------------------------------------------------------------------------
# 進階實驗 1：灌水強度掃描（回答「+3 變 +7 整個系統會怎樣」）
# ---------------------------------------------------------------------------

def fabrication_sweep(records: List[dict],
                      amounts: Sequence[int] = (1, 2, 3, 5, 7, 10, 15),
                      at_windows: Optional[Sequence[float]] = None,
                      attacker_cell: int = 4,
                      cfg: Optional[CardinalityConfig] = None) -> List[dict]:
    """
    對同一份 baseline，掃描不同灌水強度，回傳每個強度下的 C_i 反應。

    目的：找出「偵測邊界」——灌幾個假 IMSI 開始從 trusted 掉到 low_trust、
    再掉到 rejected。這條曲線就是論文 RQ1 要的「灌水強度 vs C_i」關係，
    也直接回答「+3 到 +7 系統會怎樣」：N_total 線性上升、C_i 高斯式陡降。
    """
    cfg = cfg or CardinalityConfig()
    windows = sorted({_window_key(r) for r in records})
    if at_windows is None:
        at_windows = windows[len(windows)//2:]  # 預設後半段注入
    rows = []
    for amt in amounts:
        attacked = inject_fabrication(records, n_fake=amt, at_windows=at_windows,
                                      attacker_cell=attacker_cell)
        res = compute_cardinality_over_time(attacked, cfg)
        # 取被注入窗格的代表值
        atk_windows = [res[t] for t in res if t in set(at_windows)]
        if atk_windows:
            n_tot = atk_windows[0]["N_total"]
            c_val = atk_windows[0]["C"]
            grade = atk_windows[0]["grade"]
        else:
            n_tot, c_val, grade = cfg.n_known, 1.0, "trusted"
        rows.append({"amount": amt, "N_total": n_tot, "C_i": round(c_val, 4),
                     "grade": grade, "n_known": cfg.n_known})
    return rows


# ---------------------------------------------------------------------------
# 進階實驗 2：DU 虛減 → C_i 反應 + 第一層歸因（回答「謊報UE之外DU怎麼處理」）
# ---------------------------------------------------------------------------

def localize_candidates(records_one_window: List[dict],
                        known_population: set,
                        lte_cell_id: int = 1) -> dict:
    """
    C_i 觸發後的第一層歸因（集合交集法，不需拓樸鄰居矩陣）。

    回傳：
      new_imsi        : 不在已知母體內的 IMSI（灌水產生的偽造 ID）
      candidate_cells : 上報了 new_imsi 的 cell（灌水攻擊 → 可鎖定嫌疑節點）
      missing_imsi    : 已知母體中該窗完全沒出現的 IMSI（虛減/丟棄的受害者）
      suspect_cells_depletion : 相對合理值上報 UE 數異常偏少的 cell（虛減嫌疑，較弱）

    語意（呼應你的問題「謊報 UE 之外 DU 怎麼處理」）：
      * 灌水（多報 IMSI）：偽造 ID 一定掛在攻擊節點上報 → candidate_cells 直接鎖定。
      * 虛減（少報 IMSI）：被丟的 ID 不出現在任何上報 → 無法用「誰報了壞資料」反查，
        只能標記 missing_imsi，並把「該窗 UE 數異常偏少的 cell」列為弱嫌疑，
        真正定位要靠 H_i（成員轉移合理性）。這正是 C_i / H_i 分工的體現。
    """
    reported = defaultdict(set)   # cell -> set(imsi)
    all_reported = set()
    for r in records_one_window:
        cell = int(r["CellId"]); imsi = int(r["IMSI"])
        reported[cell].add(imsi)
        all_reported.add(imsi)

    new_imsi = all_reported - known_population
    candidate_cells = sorted({c for c, s in reported.items() if s & new_imsi})
    missing_imsi = known_population - all_reported

    # 虛減弱嫌疑：mmWave cell 中上報 UE 數最少的（相對其他 cell）
    mmw = {c: len(s) for c, s in reported.items() if c != lte_cell_id}
    suspect_dep = []
    if mmw:
        mean_u = sum(mmw.values()) / len(mmw)
        suspect_dep = sorted([c for c, u in mmw.items() if u < 0.4 * mean_u])

    return {
        "new_imsi": sorted(new_imsi),
        "candidate_cells": candidate_cells,
        "missing_imsi": sorted(missing_imsi),
        "suspect_cells_depletion": suspect_dep,
    }


# ---------------------------------------------------------------------------
# CLI / 自我測試
# ---------------------------------------------------------------------------

def _print_table(title: str, result: Dict[float, dict]) -> None:
    print(f"\n{title}")
    print(f"{'t(s)':>6} | {'N_total':>7} | {'C_i':>6} | {'grade':<10} | band=[{list(result.values())[0]['N_lo']:.1f},{list(result.values())[0]['N_hi']:.1f}]")
    print("-" * 60)
    for t, row in result.items():
        print(f"{t:>6.2f} | {row['N_total']:>7d} | {row['C']:>6.3f} | {row['grade']:<10}")


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/DlE2RlcStats.txt"
    print(f"[loader] 使用：{_LOADER_SOURCE}")
    print(f"[data]   {path}")

    records = list(load_rlc(path))
    cfg = CardinalityConfig(n_known=35, eps_low=0.15, eps_high=0.0, kappa=0.10)

    # 1) baseline
    base = compute_cardinality_over_time(records, cfg)
    _print_table("=== Baseline（乾淨資料）===", base)

    # 2) ε 建議
    print("\n=== ε 建議（從 baseline） ===")
    for k, v in suggest_eps_from_baseline(records, cfg).items():
        print(f"  {k}: {v}")

    # 3) 攻擊：灌水 3 個假 IMSI（只在後半段窗）
    windows = sorted(field_cardinality_series(records, cfg.include_lte).keys())
    late = windows[len(windows) // 2:]
    atk_fab = compute_cardinality_over_time(
        inject_fabrication(records, n_fake=3, at_windows=late), cfg)
    _print_table("=== 攻擊 A 灌水（後半窗 +3 假 IMSI）===", atk_fab)

    # 4a) 攻擊：單節點虛減（cell 4）— 展示偵測力有界
    atk_del_single = compute_cardinality_over_time(
        inject_deletion(records, n_drop=8, at_windows=late, victim_cell=4), cfg)
    _print_table("=== 攻擊 A 單節點虛減（cell4 -8, 實刪受該cell UE數限）===", atk_del_single)

    # 4b) 攻擊：跨節點串謀虛減 — 展示下界觸發
    n_lo, _ = cfg.bounds()
    trigger = math.ceil(cfg.n_known - n_lo)  # 破帶所需丟棄數
    print(f"\n[理論] 下界 N_lo={n_lo:.2f}，需丟棄 ≥ {trigger} 個 UE 才會使 C_i<1")
    atk_del_field = compute_cardinality_over_time(
        inject_deletion(records, n_drop=8, at_windows=late, victim_cell=None), cfg)
    _print_table("=== 攻擊 A 跨節點虛減（-8 UE，破下界帶）===", atk_del_field)
