# 由正式版（新）與 v11 依據（舊）之 JSON 產生 v12 用之數字與表格；不手抄
import json, os
R = os.path.expanduser("~/oran-zt-kpm-verification/data/results")
J = lambda p: json.load(open(os.path.join(R, p)))
N = "d30_delay_reconstructed/"; O = "d30/"
e9n, e9o = J(N+"E9_operating_regime_rt.json"), J(O+"E9_operating_regime_rt.json")
bn, bo = J(N+"E9b_supervised_baseline_rt.json"), J(O+"E9b_supervised_baseline_rt.json")
cn, co = J(N+"E9c_common_mode_rt.json"), J(O+"E9c_common_mode_rt.json")
dn = J(N+"E9d_real_load_alarms_rt.json")
ein = J(N+"E_i/E9_operating_regime.json"); eia = J(N+"E_i/Si_reference_ablation.json")
cv = J(N+"cv_interval.json"); q1 = J("semantics_v0/Q1_scales_final.json")
xn = J(N+"xapp_rule_breakdown_bound_all_uebound_strict_severity.json")
f2 = lambda x: f"{x:.2f}"; f3 = lambda x: f"{x:.3f}"
def m(d): return d["mean"]
def rng(d, f=f2): return f"{f(d['seed_min'])}–{f(d['seed_max'])}"
def sg(x): return f"{'+' if x >= 0 else '−'}{abs(x):.2f}"
RATES = ["0.001","0.002","0.005","0.01","0.02","0.04","0.08","0.15"]
pct = lambda r: f"{float(r)*100:g}".replace("1.0","1.0")
AFS = ["1.2","1.3","1.4","1.5"]
C = lambda d: d["common"]
V = {}
# 4.7.4 表
sp, tp = C(e9n)["spatial"], C(e9n)["temporal"]; spo, tpo = C(e9o)["spatial"], C(e9o)["temporal"]
rows = [f"| **乾淨序列 FPR（注入區間）** | **{f3(m(sp['clean_fpr']))}** | **{f3(m(tp['clean_fpr']))}** | — | {f3(m(spo['clean_fpr']))}／{f3(m(tpo['clean_fpr']))} |"]
for r in RATES:
    a, b = m(sp["drift"][r]), m(tp["drift"][r]); ao, bo_ = m(spo["drift"][r]), m(tpo["drift"][r])
    rows.append(f"| {float(r)*100:.1f} | {f2(a)} | {f2(b)} | {sg(a-b)} | {f2(ao)}／{f2(bo_)} |")
V["T474"] = "\n".join(["| 漂移速率（%/秒） | 空間共識參照 | 時間自我參照 | 差值 | 舊值（累計輸入）空間／時間 |", "|---:|---:|---:|---:|---:|"] + rows)
V["sp_clean"], V["tp_clean"] = f3(m(sp["clean_fpr"])), f3(m(tp["clean_fpr"]))
V["sp_clean_rng"], V["tp_clean_rng"] = rng(sp["clean_fpr"]), rng(tp["clean_fpr"])
V["sp_d05_2"] = f"{f2(m(sp['drift']['0.005']))}–{f2(m(sp['drift']['0.02']))}"
V["tp_d05_2"] = f"{f2(m(tp['drift']['0.005']))}–{f2(m(tp['drift']['0.02']))}"
V["own_sp_clean"] = f3(m(e9n["own"]["spatial"]["clean_fpr"]))
# 4.7.5 表
rows = []
for af in AFS:
    a, b = sp["step"][af], tp["step"][af]
    rows.append(f"| 階躍 | AF = {af} | {f2(m(a))}（{rng(a)}） | {f2(m(b))}（{rng(b)}） | {sg(m(a)-m(b))} | {f2(m(sp['step_onset_hit'][af]))} | {f2(m(tp['step_onset_hit'][af]))} | {f2(m(spo['step'][af]))}／{f2(m(tpo['step'][af]))}；onset {f2(m(spo['step_onset_hit'][af]))}／{f2(m(tpo['step_onset_hit'][af]))} |")
V["T475"] = "\n".join(["| 攻擊族 | 參數 | 空間共識參照 | 時間自我參照 | 差值 | 空間參照 onset 命中率 | 時間參照 onset 命中率 | 舊值（累計輸入）空間／時間 |", "|---|---|---:|---:|---:|---:|---:|---|"] + rows + ["| 漂移 | 0.1 – 15 %/秒 | 同 4.7.4 | 同 4.7.4 | 同 4.7.4 | — | — | — |"])
V["sp_step"] = f"{f2(m(sp['step']['1.2']))}–{f2(m(sp['step']['1.5']))}"
V["tp_step"] = f"{f2(m(tp['step']['1.2']))}–{f2(m(tp['step']['1.5']))}"
V["sp_on"] = f"{f2(m(sp['step_onset_hit']['1.2']))}–{f2(m(sp['step_onset_hit']['1.5']))}"
V["tp_on"] = f"{f2(m(tp['step_onset_hit']['1.2']))}–{f2(m(tp['step_onset_hit']['1.5']))}"
# E9b
sv, svo = bn["thr_cal"]["common"], bo["thr_cal"]["common"]
rows = [f"| 乾淨誤報率 | — | **{f3(m(sv['clean_fpr']))}**（{rng(sv['clean_fpr'],f3)}） | {V['sp_clean']}（{V['sp_clean_rng']}） | {V['tp_clean']}（{V['tp_clean_rng']}） | {f3(m(svo['clean_fpr']))} |"]
for af in AFS:
    rows.append(f"| 階躍 | AF = {af} | {f2(m(sv['step'][af]))}（{rng(sv['step'][af])}） | {f2(m(sp['step'][af]))} | {f2(m(tp['step'][af]))} | {f2(m(svo['step'][af]))} |")
for r in RATES:
    rows.append(f"| 漂移 | {float(r)*100:g} %/秒 | {f2(m(sv['drift'][r]))}（{rng(sv['drift'][r])}） | {f2(m(sp['drift'][r]))} | {f2(m(tp['drift'][r]))} | {f2(m(svo['drift'][r]))} |")
V["T9b"] = "\n".join(["| 攻擊族 | 參數 | 監督式分類器 | 空間共識參照（E9） | 時間自我參照（E9） | 舊值（累計輸入）監督式 |", "|---|---|---:|---:|---:|---:|"] + rows)
V["b_target"] = f"{bn['calibration_target_fpr']:.4f}"; V["b_target_old"] = f"{bo['calibration_target_fpr']:.4f}"
V["b_clean"] = f3(m(sv["clean_fpr"])); V["b_clean_rng"] = rng(sv["clean_fpr"], f3)
V["b_on"] = f"{f2(min(m(sv['step_onset_hit'][a]) for a in AFS))}–{f2(max(m(sv['step_onset_hit'][a]) for a in AFS))}"
t05 = bn["thr0.5"]["common"]; V["b05_clean"] = f3(m(t05["clean_fpr"]))
V["b05_maxdiff"] = f2(max(abs(m(t05[k][x]) - m(sv[k][x])) for k, xs in (("step", AFS), ("drift", RATES)) for x in xs))
V["b_2c"] = f2(m(sv["clean_2c_floor"])); V["b_2c_rng"] = rng(sv["clean_2c_floor"])
fits = [v["balanced_acc"] for v in bn["train_fit"].values()]; V["b_fit"] = f"{min(fits):.3f}–{max(fits):.3f}"
V["b_d1"] = f2(m(sv["drift"]["0.01"])); V["b_d05"] = f2(m(sv["drift"]["0.005"]))
V["b_ratio"] = f"{m(sv['clean_fpr'])/m(sp['clean_fpr']):.1f}"
# E9c
def cm(x, meth, key): return x["alarm"]["common"][meth][key]
labels = [("base","無（基線）"),("step1.1","共模階躍 ×1.1"),("step1.2","共模階躍 ×1.2"),("step1.3","共模階躍 ×1.3"),("step1.5","共模階躍 ×1.5"),("drift0.005","共模漂移 0.5 %/秒"),("drift0.01","共模漂移 1 %/秒"),("drift0.02","共模漂移 2 %/秒")]
rows = []
for k, lab in labels:
    c = [cm(cn, mm, k) for mm in ("spatial","temporal","supervised")]; o = [cm(co, mm, k) for mm in ("spatial","temporal","supervised")]
    rows.append(f"| {lab} | {f2(m(c[0]))}（{rng(c[0])}） | {f2(m(c[1]))}（{rng(c[1])}） | {f2(m(c[2]))}（{rng(c[2])}） | {'／'.join(f2(m(x)) for x in o)} |")
V["T9c1"] = "\n".join(["| 擾動 | 空間共識參照 | 時間自我參照 | 監督式分類器 | 舊值（累計輸入）空間／時間／監督式 |", "|---|---:|---:|---:|---|"] + rows)
au, auo = cn["attack_under_common_mode"], co["attack_under_common_mode"]
rows = []
for k, lab in [("step1.3","階躍 AF = 1.3"),("step1.5","階躍 AF = 1.5"),("drift0.01","漂移 1 %/秒"),("drift0.02","漂移 2 %/秒")]:
    cells = [f"{f2(m(au['with_cm'][mm][k]))}／{f2(m(au['without_cm'][mm][k]))}" for mm in ("spatial","temporal","supervised")]
    olds = [f"{f2(m(auo['with_cm'][mm][k]))}／{f2(m(auo['without_cm'][mm][k]))}" for mm in ("spatial","temporal","supervised")]
    rows.append(f"| {lab} | " + " | ".join(cells) + " | " + "；".join(olds) + " |")
V["T9c2"] = "\n".join(["| 攻擊 | 空間共識參照 | 時間自我參照 | 監督式分類器 | 舊值（累計輸入）空間；時間；監督式 |", "|---|---:|---:|---:|---|"] + rows)
V["c_sup_base"] = f2(m(cm(cn,"supervised","base"))); V["c_sup_11"] = f2(m(cm(cn,"supervised","step1.1"))); V["c_sup_12"] = f2(m(cm(cn,"supervised","step1.2")))
V["c_sp_base"] = f2(m(cm(cn,"spatial","base"))); V["c_sp_steps"] = f"{f2(m(cm(cn,'spatial','step1.1')))}–{f2(m(cm(cn,'spatial','step1.5')))}"
V["c_sp_d2"] = f2(m(cm(cn,"spatial","drift0.02"))); V["c_tp_d2"] = f2(m(cm(cn,"temporal","drift0.02"))); V["c_sup_d2"] = f2(m(cm(cn,"supervised","drift0.02")))
V["c_tp_base"] = f2(m(cm(cn,"temporal","base"))); V["c_tp_steps"] = f"{f2(m(cm(cn,'temporal','step1.1')))}–{f2(m(cm(cn,'temporal','step1.5')))}"
V["c_n"] = str(cn["n_samples"])
# E9d
g = dn["analyses"]["main"]["groups"]; HH, LL = g["其他cell高負載高延遲"], g["其他cell低負載低延遲"]
def gl(G, mm): return f"{G[mm]['alarms']:,}（{f3(G[mm]['rate'])}）"
V["T9d"] = "\n".join(["| 組別 | 樣本數 | 監督式分類器告警 | 空間參照告警 | 時間參照告警 |", "|---|---:|---:|---:|---:|",
    f"| 其他 cell 高負載、高延遲背景 | {HH['n_seed_cell_window']:,} | {gl(HH,'supervised')} | {gl(HH,'spatial')} | {gl(HH,'temporal')} |",
    f"| 其他 cell 低負載、低延遲背景 | {LL['n_seed_cell_window']:,} | {gl(LL,'supervised')} | {gl(LL,'spatial')} | {gl(LL,'temporal')} |"])
op = dn["overall_pooled"]; V["d_overall"] = f"監督式 {f3(op['supervised'])}、空間參照 {f3(op['spatial'])}、時間參照 {f3(op['temporal'])}"
V["d_n"] = f"{dn['n_rows']:,}"
for mm in ("supervised","spatial"):
    V[f"d_dir_{mm}"] = sum(1 for s in HH["per_seed"] if HH["per_seed"][s][mm] > LL["per_seed"][s][mm])
def sens(name):
    gg = dn["analyses"][name]["groups"]; h, l = gg["其他cell高負載高延遲"], gg["其他cell低負載低延遲"]
    return f"{h['supervised']['alarms']:,}／{h['n_seed_cell_window']:,}（{f3(h['supervised']['rate'])}）對 {l['supervised']['alarms']:,}／{l['n_seed_cell_window']:,}（{f3(l['supervised']['rate'])}）"
V["d_s50"], V["d_snew"], V["d_s90"] = sens("sens_q0.5"), sens("sens_newtx"), sens("sens_q0.9")
gg = dn["analyses"]["sens_q0.5"]["groups"]; V["d_s50_dir"] = sum(1 for s in gg["其他cell高負載高延遲"]["per_seed"] if gg["其他cell高負載高延遲"]["per_seed"][s]["supervised"] > gg["其他cell低負載低延遲"]["per_seed"][s]["supervised"])
# E-i（原始評估集合、以窗索引為單位之實作）
rows = [f"| 乾淨 FPR | {f3(eia['clean_fpr']['spatial'])} | {f3(eia['clean_fpr']['temporal'])} |"]
for r in RATES: rows.append(f"| 漂移 {float(r)*100:g} %/秒 | {f2(eia['drift_detection']['spatial'][r])} | {f2(eia['drift_detection']['temporal'][r])} |")
for af in AFS: rows.append(f"| 階躍 AF = {af}（onset） | {f2(ein['step']['spatial'][af]['mean'])}（{f2(ein['step_onset_hit']['spatial'][af]['mean'])}） | {f2(ein['step']['temporal'][af]['mean'])}（{f2(ein['step_onset_hit']['temporal'][af]['mean'])}） |")
V["TEi"] = "\n".join(["| 項目 | 空間共識參照 | 時間自我參照 |", "|---|---:|---:|"] + rows)
ena = J(N+"Si_reference_ablation.json"); V["eii_nonrt"] = f"{f3(ena['clean_fpr']['spatial'])}／{f3(ena['clean_fpr']['temporal'])}"
V["ei_clean"] = f"{f3(eia['clean_fpr']['spatial'])}／{f3(eia['clean_fpr']['temporal'])}"
# 尺度與 CV
V["cv"] = f"{cv['delay_cv']['median']:.3f}"; V["cv_q"] = f"{cv['delay_cv']['q25']:.3f}–{cv['delay_cv']['q75']:.3f}"; V["cv_n"] = f"{cv['delay_cv']['n']:,}"
folds = q1["cross_seed_reconstructed"]["folds"]; V["s_new_rng"] = f"{min(x['C2'] for x in folds):.3f}–{max(x['C2'] for x in folds):.3f}"
olds = json.load(open(os.path.join(R, N+"E_i/Ei_meta.json")))["scales_used"]; ov = sorted({x["C2_old"] for x in olds})
V["s_old_rng"] = f"{min(ov):.3f}–{max(ov):.3f}"
V["x_si_viol"] = f"{xn['si_raw_availability']['violated']:,}"; V["x_si_share"] = f"{xn['si_raw_availability']['violated']/15534*100:.1f}%"
if __name__ == "__main__":
    for k, v in V.items(): print(f"[{k}]\n{v}\n" if "\n" in str(v) else f"{k} = {v}")
