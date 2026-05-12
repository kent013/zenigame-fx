# Round 1 結審サマリー (zenigame vs zenigame-fx 横断議論)

作成: 2026-05-12 12:00 JST
前提: 旧セッション `2112480e-f161-4fcb-b9c2-e73aba553c29` が Round 1 で停止していたため、本セッションで結審 → 引き継ぎ。

## Codex Round 1 判定 (2026-05-12 10:09 JST 取得)

**全体判定**: CHANGES_REQUESTED

| 区分 | 提案 | Codex 評価 |
|------|------|-----------|
| Critical | `graduation_criteria.require_cross_pair_pass` を shadow モード時に自動バイパス | 期待効果=高、複雑性=低、抵触=なし |
| Warning 1 | T501-T506 Mission Shortfall fitness を `fitness_pen` に組み込む | 期待効果=高、複雑性=中 |
| Warning 2 | Stage A gate に `n_fold_effective >= wf_min_safe_folds` のハードチェック追加 | 期待効果=中、複雑性=低 |
| QB 棄却 | Q1 (`total_pnl` 50000 円→相対) | 禁止事項 4 抵触 |
| QC | 「先人の知恵」逆移植が最短 | Phase 2 新要素は補助評価で OK |

完全文面: [`codex-response-round-1.md`](./codex-response-round-1.md)。

## 自己検証 (Explore agent による現状コード fact-check)

Codex 評価と現状実装の整合性を確認した結果、 **複雑性評価で 2 件、 適用先で 1 件のズレ** を検出。 これは「コード読まずに表層判断する Codex Recursive 落し穴」を Round 1 で完全には回避できなかった例 (C5 並列独立性 / C1 Design-first 視点)。

### Critical (shadow バイパス)
- 定義: [`config/alpha_factory/default.yaml:244`](../../config/alpha_factory/default.yaml#L244) `require_cross_pair_pass: true`
- 判定: [`src/alpha_factory/swim_lane.py:385-412`](../../src/alpha_factory/swim_lane.py#L385-L412) — `stage_c_result.passed AND cross_pair_result.passed` の単純 AND。 `cross_pair_result=None` は保守的に False。
- mode: [`src/alpha_factory/cross_pair.py:99`](../../src/alpha_factory/cross_pair.py#L99) `mode: Literal["shadow","hard"] = "shadow"`
- shadow sidecar: [`src/alpha_factory/stage_gate.py:680,1738`](../../src/alpha_factory/stage_gate.py) 経由で `_shadow_sidecar_inputs` に非侵襲格納
- **ズレ**: `graduation_criteria` は `cross_pair.mode` を参照しておらず、 シグネチャ変更 or config 注入が必要。 Phase 2 では `_mark_for_graduation` が即時実行 (deferred_promotion 未実装) で構造的に困難。 **複雑性=中〜大** (Codex の「低」は誤評価)。

### Warning 1 (Mission Shortfall T501-T506)
- zenigame 実装: [`/Users/ishitoya/repository/zenigame/src/trading/alpha_factory/ga/nsga2/mission_shortfall.py:1-120`](../../../zenigame/src/trading/alpha_factory/ga/nsga2/mission_shortfall.py#L1-L120) — `compute_mission_shortfall_s()` で 3 窓 × 4 指標の smooth-worst → Huber penalty
- zenigame-fx `fitness_pen` 構成: [`src/alpha_factory/stage_gate.py:876-880`](../../src/alpha_factory/stage_gate.py#L876-L880) `fitness_raw - alpha * size_norm - trade_count_penalty` (Stage A のみ 3 項)
- mission_inf_gap: [`src/alpha_factory/mission_inf_gap.py:87-166`](../../src/alpha_factory/mission_inf_gap.py#L87-L166) → archive CA で T064 ordering / NSGA2 selection (f3 軸)
- **整合性**: zenigame の T501-T506 はモジュール独立 (`mission_shortfall.py` standalone) のため、 import + `fitness_pen` への新項目追加で移植可能。 mission_inf_gap (制約違反度) と mission_shortfall_s (smooth 距離) は **概念的に独立** で衝突なし。 但し fitness 空間の重み軸増加で α 校正と回帰 test 必要。 **複雑性=中** (Codex 評価と一致)。

### Warning 2 (n_fold_effective ハードチェック)
- Stage A: [`src/alpha_factory/stage_gate.py:724-914`](../../src/alpha_factory/stage_gate.py#L724-L914) — **60 日窓の単一 backtest、 fold 概念なし**
- Stage B `n_fold_effective`: [`src/alpha_factory/stage_gate.py:1197`](../../src/alpha_factory/stage_gate.py#L1197) `n_fold - n_fold_unavailable`
- `wf_min_safe_folds`: [`src/alpha_factory/stage_gate.py:417`](../../src/alpha_factory/stage_gate.py#L417) default=5。 [`src/alpha_factory/swim_lane.py:502`](../../src/alpha_factory/swim_lane.py#L502) で lane preflight (`lane_max_folds < wf_min_folds` → Stage B skip, `stage_b_pre_flight_underfilled`)
- **重大なズレ**: **Codex の「Stage A gate に追加」は適用先誤り**。 Stage A は fold-free のため、 `n_fold_effective` 参照不可。 実装すべきは **Stage B の `evaluate_stage_b()` 内**、 または **lane preflight の閾値強化**。 修正は 3-5 行で済むが、 Codex が掴んでいた「Run 60 best n_fold=4 で fp 0.54」 artifact は **Stage B が underfilled scope で fold ≥1 でも通過した artifact** と解釈すべき。

## 統合判定 (本セッション側)

Codex 提案を「方向性」として採用するが、 **複雑性 / 適用先を訂正した上で TODO 化** する:

| Priority | 施策 | 真の複雑性 | 真の適用先 | mission 寄与 |
|---------:|------|----------|----------|------------|
| **P1 (Quick win)** | Stage B `n_fold_effective >= wf_min_safe_folds` hard guard | 低 (3-5 行) | `stage_gate.py:evaluate_stage_b` L1206 付近、 `insufficient_folds` 拡張 | 中 (artifact 排除) |
| **P2 (Structural)** | Mission Shortfall fitness 移植 (T501-T506) | 中 (1-3 日) | zenigame の `mission_shortfall.py` を `src/alpha_factory/` 配下に移植 → `stage_gate.py` の `fitness_pen` 拡張 | 高 (selection 圧の方向修正) |
| **P3 (Deferred / 設計)** | shadow mode 時 `require_cross_pair_pass` 自動バイパス | 中〜大 (signature 変更必要) | `swim_lane.py:graduation_criteria` に `cross_pair_mode` 注入 + Phase 2 の即時実行構造の調整 | 高 (graduation=0/18 のロック解除) |

### 採用しない / 棄却済
- **Q1 (live_criteria 緩和)**: Codex 棄却 + 禁止事項 4 抵触 で確定。 採用しない。
- **Q3 (min_win_rate 復活)**: Codex は明示判定無し。 本セッションでも **保留** — Mission Shortfall (P2) に win_rate 軸を含めるかどうかは詳細設計時に再評価。
- **Q5 (mutation 0.5→0.26 / elite 2→5)**: Codex は明示推奨無し。 本セッションでも 後続施策の効果を確認後、 別 RUN で seed sweep + GA params A/B が妥当。 単独で動かさない。

### 「先人の知恵」観点 (QC)
Codex の判断「未成熟な zenigame-fx 固有ロジック (mission_inf_gap 単独最適化 / shadow 卒業ロック) より、 zenigame で実績検証済の logic を再導入する方が早い」 は **支持**。 但し:
- zenigame-fx 独自の Phase 2 設計 (canonical_five / mission_inf_gap / cpps_archive FSM / DSR scaffold) は **継承維持**。 先人 logic を上書き / 置換 ではなく **加算** で導入する設計とする。
- 「先人=zenigame」も T540 sharpe annualization が broken のままで、 zenigame-fx 側が修正済の事実は逆方向の知恵移転として記録 (将来 zenigame に back-port 余地)。

## 次アクション (本セッション継続)

1. **P1 (Quick win) — 完了 ✅**: `Stage B n_fold_effective hard guard` を `T092` として登録済 (2026-05-12 12:23)
   - 設計: [`devnotes/20260512-1216-stage-b-nfold-safe-guard/`](../20260512-1216-stage-b-nfold-safe-guard/) (conceptual + detailed)
   - TODO: [`docs/alpha_factory/TODO.md`](../../docs/alpha_factory/TODO.md) `T092` Priority=High / mode=incremental
   - 実装パス: 次の `/zenigame-fx-autopilot` or `/zenigame-fx-improve-cycle` で自動選定候補
2. **P2 (Structural) — 引き継ぎ**: `Mission Shortfall fitness 移植 (T501-T506)` は別セッションで `/zenigame-fx-alpha-design "mission-shortfall-fitness-port"` を起動して概念設計 → Codex 1-5 round → 詳細設計 → TODO 登録のフルフローに乗せる。 概念設計時に「`min_win_rate` 軸を mission_shortfall に含めるか」「fitness 空間の重み α 校正」「mission_inf_gap (T062) との lex 順での共存方式」を主論点とする。
3. **P3 (Deferred) — 設計 intent のみ記録**: shadow mode 時 `require_cross_pair_pass` バイパスは、 実装には swim_lane.py の `graduation_criteria` シグネチャ変更 + Phase 2 即時実行構造の調整が必要で複雑性大。 Phase 4 (`cross_pair.mode='hard'` 本格化) との合算設計が筋良いと判断し、 本セッションでは **TODO 登録せず、 design intent を本 devnote に記録のみ**。

### P3 設計 intent (Phase 4 持ち越し)

- 現状の論理矛盾: `graduation_criteria.require_cross_pair_pass=true` AND `cross_pair_runtime_mode='shadow'` の組合せで、 shadow 評価結果が `cross_pair_result.passed` を populate しないまま `graduation_criteria` が AND で潰す → graduation=0/18 のロック。
- 暫定対処の選択肢:
  - (a) `require_cross_pair_pass=false` に設定変更 (config 1 行、 最小侵襲) — 但し Phase 4 で hard mode 切替時に再び true にする必要があり、 トレードオフが浅い
  - (b) `graduation_criteria` に `cross_pair_mode` 注入し、 shadow 時 bypass — 構造変更で工数中、 Phase 4 で hard 切替時も同コードで継続使用可
  - (c) Phase 4 で `cross_pair.mode='hard'` 切替と同時に require_cross_pair_pass の bypass logic を組み込み (合算実装) — 工数集約で重複作業回避
- 推奨: **(c) Phase 4 合算実装**。 本セッションでは (a) を **暫定対処として next Run の config に検討候補とする** (但し本 verdict 内で config 変更はしない — 別途ユーザー合議)。

---

## セッション引き継ぎ完了 (2026-05-12 12:24 JST)

- 本 devnote の Round 1 結審状態: **CLOSED**
- 旧セッション `2112480e-...` の Round 1 出力は確定し、 本セッションで verification + verdict + 次アクション割り当てを完了
- Round 2 は **実施しない** (1 round 収束ルール + 提案の方向性が支持できるため)
- 後続作業はそれぞれ別 devnote で進行:
  - P1: `devnotes/20260512-1216-stage-b-nfold-safe-guard/` (T092 で実装待ち)
  - P2: 別セッションで `/zenigame-fx-alpha-design mission-shortfall-fitness-port` 起動
  - P3: 本 devnote 内に design intent 記録のみ、 Phase 4 で再活性化

## メモ (議論プロセスの自己評価)

- Codex Round 1 は **1 round で 1 仮説 + 1 最小変更** ルールに従い Critical を出してくれたが、 適用先 / 複雑性で実コードと乖離していた (Stage A vs Stage B / signature 変更必要)。
- これは **C1 Design-first** discipline で「コード読まずに表層判断する」典型例。 Round 1 後の自己検証 (Explore agent) を挟まなかった旧セッションが該当パターン。
- 教訓: **Codex Round 1 出力 → 必ず Explore による 5 分検証 → 結審** を運用標準にすべき (本セッションで実施したフロー)。
