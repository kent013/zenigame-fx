# 概念設計: B Phase 2 切替コミット step 1.8 — Stage C cross_pair (ii-lite) dual-path 拡張

**作成日時**: 2026-05-04 00:10 JST (Round 2 改訂: 2026-05-04 00:25 JST、 Round 3 改訂: 2026-05-04 00:38 JST、 案 A' 採用)
**起源**: B Phase 2 切替コミット step 1.7 (= Stage C stress dual-path 配線、 main commit e3a428b) 完了後の段階的拡張
**性質**: step 1 / 1.5 / 1.6 / 1.7 で確立した dual-path helper / adapter を **Stage C cross_pair (= ii-lite shadow 評価) にも適用**。 cross_pair の構造的制約 (= per-pair backtest 結果が破棄される) を踏まえ、 Codex Round 1 review の Critical 反映で **案 A' を採用**: cross_pair.py は per-pair sidecar input を保持して返すだけ、 canonical 計算と dual-path log emit は stage_gate.py 側に残す責務分離。 Round 3 で multiprocessing pickle / 循環依存 / sanitize 漏れの 3 Critical を反映。
**位置付け**: cascade port v2 Phase 2 切替コミット 7 step segmentation の **step 1.8** (= mission 必須軸 = ii-lite の観測完成、 step 2 を block しない optional observability step)
**status**: **概念設計 Round 3 APPROVED** (= A' 改訂、 Codex Round 1-3 反映済、 Critical 0 / Warning 3 件は文言修正で反映済 / Suggestion 1 件は acceptance E4 に取込)。 推奨案 A' で確定、 詳細設計フェーズへ進行可。

---

## 0. 改訂対応マトリクス

### 0.1 Round 1 → Round 2 改訂対応マトリクス

| Round 1 指摘 | 対応 |
|---|---|
| § 全体 [Critical] 案 A は cross_pair.py に canonical 計算責務まで持ち込みすぎ → A' (= cross_pair.py は sidecar 保持・返却のみ、 canonical 計算と log emit は stage_gate.py 側) を推奨 | **案 A' を採用**。 § 1.4 / § 2 を全面改訂、 cross_pair.py 内で canonical 計算する経路を全削除、 stage_gate.py 側に集約 |
| § 全体 [Critical] CrossPairConfig への dual-path field 追加は伝搬面が広すぎる | `CrossPairConfig` 不変 (= `dual_path_enabled` / `live_criteria` / `window_days` の追加を撤回)。 stage_gate.py 側 caller が既存 `stage_config.live_criteria` / `stage_config.stage_c_holdout_days` をそのまま再利用 |
| § Warning `metrics["canonical_per_pair"]` / `["legacy_per_pair"]` を公開 metrics 空間に混ぜるのは境界が弱い | `CrossPairResult.metrics` に sidecar を入れない。 cross_pair.py が `evaluate_cross_pair` 内で生成する sidecar は **戻り値拡張** (= `CrossPairResult` の新規 sub-attribute) として隔離、 ephemeral object として in-memory only で扱う + payload/archive transport テストで固定 |
| § Warning メモリ見積りは「実測前提」で blocker ではないが Round 1 では断定不可 | Acceptance B2 を **merge 条件に格上げ** (= 実測 PASS なしで step 1.8 を main merge しない)、 sidecar の即時破棄 (= canonical 計算後 dict drop) を § 2 / 詳細設計 § X で明文化、 sidecar はコピーではなく参照保持を契約化 |
| § Warning C1/C4 はこの round では未充足 → Round 2 で payload/archive transport / `_run_pair_sharpe` caller / `cp_inputs` 構築経路を抜粋提示 | § 9 に「Round 2 の独立検証成果」として 3 経路を抜粋掲載 (= 詳細設計 round で expansion 予定) |
| § Suggestion `pair_label` 追加は妥当、 fold_index 流用 (A2) は却下、 A3 採用 | A3 (= `_log_canonical_dual_path` に optional `pair_label: str | None = None` 追加) を確定 |
| § Suggestion `pair_label` には実 pair 名 (= `EUR_USD`) を使うべき、 役割名は別 field | `pair_label` には **実 pair 名** (= `EUR_USD` 等) を渡す。 役割識別 (= target / anchor1 / anchor2) は別途 dict で stage_gate.py caller が把握、 dual-path log には emit しない (= Round 2 [Suggestion] 反映、 SSOT 簡潔化) |

### 0.2 Round 2 → Round 3 改訂対応マトリクス

| Round 2 指摘 | 対応 |
|---|---|
| § [Critical] `_shadow_sidecar_inputs` は `del sidecar_map` だけでは破棄されない (= cp_result が `cross_pair_payload["result"]` / `GenomeStageResult.cross_pair` に残るため payload 内に永続化される) | **canonical log 後、 StageResult 構築前に sanitize**: `cross_pair_payload["result"] = replace(cp_result, _shadow_sidecar_inputs={})` で sidecar 空の `CrossPairResult` に差し替え。 § 2.4 のコード骨子を更新、 acceptance E1/E2 を「payload に key がない」 から「payload 内 `CrossPairResult._shadow_sidecar_inputs` が空」 に拡張 |
| § [Critical] `MappingProxyType({})` default は multiprocessing 経路で pickle 失敗 (= `parallel_eval._pool.map(...)` で `TypeError: cannot pickle 'mappingproxy' object`) | **default を `field(default_factory=dict, repr=False, compare=False)` に変更**。 immutability は payload 返却前の sanitize + shallow copy で担保。 § 2.3 を更新 |
| § [Critical] `_PairSidecarInputs` を cross_pair.py に定義し `CrossPairResult` field 型として参照すると循環依存 (= cross_pair.py は stage_gate から `CrossPairResult` を import 済) | **`_PairSidecarInputs` を stage_gate.py 側の `CrossPairResult` 近傍に定義**。 cross_pair.py は `CrossPairResult` と同時に `_PairSidecarInputs` も import (= 単方向 import 経路維持)。 § 2.1 / § 4.1 の配置を更新 |
| § [Warning] 「参照保持のみ」 表現は現行コードと完全一致しない (= `bars=list(pair_bars[pair])` で shallow copy 入っている) | 「deep copy なし、 既存経路の shallow copy を許容」 に修正。 § 2.1 / § 4.4 の表現を更新、 B2 merge 条件は維持 |
| § [Warning] dataclass field は明示しないと repr / equality に sidecar が混じり snapshot 比較が不安定 | `_shadow_sidecar_inputs` は **`field(default_factory=dict, repr=False, compare=False)` を必ず指定**。 § 2.3 を更新、 acceptance E に repr/compare 除外契約を追加 |
| § [Suggestion] 役割識別 (target/anchor1/anchor2) は将来分析で必要なら Stage C payload 側の `target_pair` / `anchor_pairs` と join する前提を明記 | § 2.6 に「将来 role 分析時は dual-path log と Stage C payload の `(target_pair, anchor_pairs)` を join する」 設計前提を追記 |

---

## 1. 背景・課題

### 1.1 step 1.7 完了時点の状態

step 1.7 (= main commit e3a428b) で:
- Stage A / Stage B IS / Stage B fold (= n_fold 動的) / Stage C base / Stage C stress の 5 系列で dual-path 観測点を確立
- helper (`_try_evaluate_canonical_five_safe` / `_log_canonical_dual_path`) は凍結 (= step 1.6 で `fold_index: int | None = None` optional kwarg 追加後不変)
- 物理隔離 pattern (= 別 try ブロック) で 4 系列で rigorous に動作することを実証

**Stage C cross_pair (ii-lite) shadow 区画は依然として未配線**: `evaluate_stage_c` の cross_pair 区画 (= stage_gate.py:1508-1555) では `cross_pair_evaluator.evaluate(...)` を呼び `CrossPairResult` を受け取るが、 canonical 5 軸は計算されない。

### 1.2 着手前調査 (= Verified Fact)

`zenigame-fx-codex-review` の C1 Design-first 順守で、 grep + Read で着手前調査済:

**(a) cross_pair_evaluator は実装済 + main flow 配線済** (= handoff § 4.2 「未配線」 認識は古い):
- `StageCRunCrossPairEvaluator` (= `src/alpha_factory/cross_pair.py:364-418`) が `CrossPairEvaluator` Protocol (= `stage_gate.py:562-572`) を満たす実装
- main flow:
  - `parallel_eval.py:342-365` — `ctx.cp_inputs is not None` のとき `cp_evaluator` を作って Stage C へ渡す
  - `swim_lane.py:677` — 同型 配線
- → `cross_pair_evaluator=None` が default ではなく、 production run では cp_inputs が供給される限り常に評価される

**(b) cross_pair 内部構造**:
- `evaluate_cross_pair` (= `cross_pair.py:214-356`) は **3 つの backtest を内部で実行** (= target + anchor1 + anchor2)
- 各 pair は `_run_pair_sharpe` (= `cross_pair.py:122-164`) で:
  - `run_backtest(...)` → `BacktestResult` (= trades / equity_curve)
  - `compute_metrics(...)` → `BacktestMetrics`
  - **`bt.trade_sharpe_raw` だけ抽出**、 trades / equity_curve は局所変数 `result` / `bt` のスコープ終了で破棄
- `CrossPairResult.metrics` には `sharpe_per_pair: dict[str, float]` 等の集約値のみ保持、 **canonical_five 計算入力 (= trades / equity_curve / bars) は不在**

**(c) canonical_five 計算契約** (= 既存 helper の API):
- `_try_evaluate_canonical_five_safe(trades, equity_curve, bars, live_criteria, window_days, stage_label, genome_name, enabled)` で trades + equity_curve + bars が必須入力
- `_log_canonical_dual_path(stage_label, genome_name, legacy: BacktestMetrics, canonical: CanonicalFiveResult | None, fold_index)` で legacy = `BacktestMetrics` instance が必須

**(d) 構造的制約 = この step の本質的課題**:
- canonical 計算には per-pair の `trades / equity_curve / bars` が必要 → cross_pair.py 改修なしには取得不能
- step 1.5 / 1.6 / 1.7 と同じ「stage_gate.py のみ改変」 「helper シグネチャ変更なし」 「adapter 凍結」 原則を **完全には維持できない**: cross_pair.py に最小限の sidecar 保持 / 返却の改修が必要

### 1.3 課題

- **観測範囲不足 (mission 必須軸)**: Stage C の **cross_pair (ii-lite) 評価経路** で canonical 5 軸を観測できない。 mission 必須軸 (= ii-lite 通過は live_criteria 達成の条件) のため、 step 2 着手前に観測完成すべき
- **構造的制約**: step 1.5 / 1.6 / 1.7 で確立した「stage_gate.py のみ改変」原則を本 step では維持不能 (= cross_pair.py 内部の per-pair backtest 結果が破棄される設計)
- **責務境界**: 案 A (Round 1 提案) では cross_pair.py に canonical 計算責務まで持ち込み、 cross-pair 評価器が Stage C shadow 観測ポリシーまで知る形になり責務境界が悪い → 案 A' (Round 2) で「cross_pair.py は sidecar 保持・返却のみ」 に切り直し

### 1.4 step 1.8 のスコープ確定 (= 案 A' 採用)

**採用案: A'** (= cross_pair.py は per-pair sidecar input を保持して返すだけ、 canonical 計算と dual-path log emit は stage_gate.py 側で実行)

#### 案 A' (採用) の改修方針

**cross_pair.py 側** (= 最小改修):
1. `_run_pair_sharpe` の戻り値を `(sharpe, failure_reason)` から `(sharpe, failure_reason, sidecar_inputs: _PairSidecarInputs | None)` に拡張
2. `_PairSidecarInputs` (= 新規 frozen dataclass) で `bars / trades / equity_curve / bt: BacktestMetrics` を保持。 backtest 例外時 (= pair_failure) は None
3. `evaluate_cross_pair` で `sidecar_inputs_per_pair: dict[str, _PairSidecarInputs]` を構築し、 `CrossPairResult` の **新規属性** (例えば `_shadow_sidecar_inputs`) として返す。 `CrossPairResult.metrics` には絶対入れない (= public metrics 空間を汚染しない、 § 2.6 名前空間隔離)
4. `CrossPairConfig` 不変 (= dual-path 経路用 field 追加なし)
5. canonical 計算は cross_pair.py 内では一切しない

**stage_gate.py 側** (= 観測ポリシーを集約):
6. `_log_canonical_dual_path` に optional kwarg `pair_label: str | None = None` 追加 (= step 1.6 `fold_index` と同型 backward-compatible 拡張)
7. `_log_canonical_dual_path(stage_label="C_cross_pair", pair_label=None)` のとき ValueError fail-fast (= 識別子契約 SSOT)
8. `evaluate_stage_c` の cross_pair 区画で `cp_result is not None and not cross_pair_payload["skipped"]` のとき:
   - `cp_result._shadow_sidecar_inputs` (= per-pair dict) を取り出し、 別 try ブロックで per-pair iterate
   - 各 pair について `_try_evaluate_canonical_five_safe(..., live_criteria=stage_config.live_criteria, window_days=stage_config.stage_c_holdout_days, stage_label="C_cross_pair", ...)` を呼び canonical 計算
   - `_log_canonical_dual_path(stage_label="C_cross_pair", pair_label=<実 pair 名>, legacy=sidecar.bt, canonical=canonical_sidecar)` で per-pair × 3 entries / genome emit
9. canonical 計算後、 sanitize (= `replace(cp_result, _shadow_sidecar_inputs={})`) で payload 内 cp_result の sidecar を空 dict に差し替え、 元 dict を GC 対象化 (= memory short-lived peak、 § 2.4 詳述)
10. **既存判定値 / metrics / reason_codes は touch しない** (= 物理隔離契約)。 sidecar sanitize のため `cross_pair_payload["result"]` の参照だけを sanitized cp_result に差し替えるのは禁止対象外 (= Round 3 [Warning 3] 反映、 「既存判定値・metrics・reason_codes は touch しない、 sidecar sanitize のため result 参照だけ差し替える」)

**観測値**: target + anchor1 + anchor2 = 3 entries / genome (= mission 必須軸 完全観測)

#### 案 A' のメリット

1. **責務境界が明確**: cross_pair.py は cross-pair 評価本体に責務を限定 (= sharpe 集約 / pass 判定)、 canonical shadow 観測は stage_gate.py に集約
2. **伝搬面最小**: `CrossPairConfig` / `parallel_eval.py` / `swim_lane.py` 不変 (= dual-path 経路情報の transport 漏れリスク 0)
3. **public metrics 空間の隔離**: `CrossPairResult.metrics` を汚染しない、 sidecar は ephemeral 専用属性に格納
4. **既存原則の維持**: stage_gate.py 側で canonical 計算・log emit する pattern は step 1.5 / 1.6 / 1.7 と同型 (= 「観測ポリシーは stage_gate.py 集約」 を保つ)

#### 案 B / 案 C は不採用 (= Round 1 で否決)

- 案 B (target のみ観測): ii-lite 集約判定の constituent observability を欠く、 mission 軸として不完全
- 案 C (skeleton のみ): canonical 観測が完成せず、 mission 必須軸の observability 完成という step 1.8 の目的に届かない

### 1.5 切替誘因のガード (step 1.7 § 1.5 継承)

step 1.8 完了後、 観測 only の C_cross_pair dual-path log を切替判断の根拠にしないこと:
- C_cross_pair canonical_gate_pass は mission 判定にも切替判定にも使わない
- C_cross_pair pass/fail 分布だけで step 2 (= 判定切替) のタイミングを決めない
- live_criteria 不変 (= 禁止事項 #4)、 評価期間 (= stage_c_holdout_days) 不変 (= 禁止事項 #1)
- 解釈単位は run/genome 横断 n>30 を満たした後の集計でのみ (= C7 sample size guard)
- canonical / cross_pair gate (= aggregate_fitness / sharpe_ratio / mean_sharpe / min_sharpe) は同じものを見ていない (= per-pair canonical はいわば「ii-lite gate の constituent observability」)
- per-pair canonical 比較は **後段集計で `(genome, pair)` を join した descriptive analysis のみ**

= step 1.8 完了後の状態 (= 案 A' 採用):
- main flow が canonical 5 metrics の観測値を **Stage A / Stage B IS / Stage B fold / Stage C base / Stage C stress / Stage C cross_pair (per-pair × 3) の 6 評価点 (= cross_pair は 3 entries / genome、 他 stage は 1 entry / genome)** で生成可能
- Stage C 全評価軸 (= base + stress + cross_pair) の canonical 観測完成 → mission 必須軸の observability 達成

---

## 2. 改善アイデア (= 案 A' 採用)

### 2.1 `_PairSidecarInputs` の配置 (= stage_gate.py 側に定義、 循環依存回避)

**配置先**: `src/alpha_factory/stage_gate.py` 内、 `CrossPairResult` dataclass の近傍 (= cross_pair.py からは同 module の `CrossPairResult` と一緒に import)。 cross_pair.py が stage_gate.py を import する単方向経路は既存通り (= `cross_pair.py:36` `from src.alpha_factory.stage_gate import CrossPairResult` の隣に `_PairSidecarInputs` を追加 import)。

```python
# stage_gate.py に定義
@dataclass(frozen=True)
class _PairSidecarInputs:
    """canonical_five 計算用 input 集合 (= dual-path 経路でのみ使用、
    cross_pair.py 内では参照保持のみ、 canonical 計算は呼ばない).

    保持コピー方針: deep copy なし。 list は既存経路の shallow copy を許容
    (= `bars=list(pair_bars[pair])` 等で list constructor が走る既存挙動を許容、
    deep copy はしない)。 canonical 計算後 stage_gate.py 側で sanitize → dict drop で
    即時 GC 対象。
    """
    bars: list[PriceBar]            # cp_inputs.pair_bars_map[pair] の shallow copy 許容
    trades: list[BrokerTrade]       # backtest 結果の参照保持 (= deep copy なし)
    equity_curve: list[tuple[datetime, Decimal]]  # 同上
    bt: BacktestMetrics             # legacy log 用 BacktestMetrics 参照保持
```

`cross_pair.py` 側は `from src.alpha_factory.stage_gate import CrossPairResult, _PairSidecarInputs` で受け取り。 既存の単方向 import 経路 (cross_pair → stage_gate) を維持、 循環依存リスクなし。

`_run_pair_sharpe` の戻り値を `(sharpe: float, failure_reason: str | None, sidecar_inputs: _PairSidecarInputs | None)` に拡張:
- 成功時: `(sharpe, None, sidecar_inputs)` で trades/equity_curve/bt の参照を保持して返す
- 失敗時 (= no trades / pair_failure 例外): `(0.0, "<reason>", None)` で sidecar は None
- caller (= `evaluate_cross_pair`) は backward-compatible に分解代入で受け取り可能

**設計判断**:
- sidecar は **deep copy なし**、 list constructor 等の既存 shallow copy 経路は許容 (= Round 2 [Warning] 反映、 「参照保持のみ」 表現を訂正)
- 失敗 pair は sidecar None で dual-path skip 経路に直結 (= acceptance C6)
- helper シグネチャ拡張は cross_pair.py 内のみ、 外部 API には影響なし
- _PairSidecarInputs を stage_gate.py 側に定義することで `CrossPairResult` field 型として通常 import で参照可能 (= Round 2 [Critical 3] 反映)

### 2.2 `evaluate_cross_pair` の sidecar 集約 (= canonical 計算は呼ばない)

```python
# === 既存 legacy 集計 (= sharpe_per_pair / aggregator / pass_criteria 確定、 完全不変) ===
sharpe_per_pair: dict[str, float] = {}
pair_failures: list[str] = []
sidecar_inputs_per_pair: dict[str, _PairSidecarInputs] = {}  # 新規
for pair in required:
    sh, fail, sidecar_inputs = _run_pair_sharpe(...)
    sharpe_per_pair[pair] = sh
    if fail is not None:
        pair_failures.append(...)
    if sidecar_inputs is not None:
        sidecar_inputs_per_pair[pair] = sidecar_inputs

# ... 既存 aggregation / ratio / pass criteria は完全不変 ...

# 戻り値: CrossPairResult に新規属性 _shadow_sidecar_inputs を渡す
return CrossPairResult(
    target_pair=target,
    anchor_pairs=(a1, a2),
    aggregator_name=...,
    window=window,
    passed=...,
    metrics=metrics,                     # 既存通り、 sidecar は入れない
    reason_codes=...,
    _shadow_sidecar_inputs=sidecar_inputs_per_pair,  # 新規 (= ephemeral)
)
```

**設計判断**:
- `CrossPairResult.metrics` には sidecar を絶対入れない (= public metrics 空間を汚染しない、 archive/payload transport テストで固定)
- `_shadow_sidecar_inputs` は `CrossPairResult` の **新規 dataclass field** (= 非 public な leading underscore で内部用を明示)、 default は `dict` の `default_factory` (= 空 dict、 backward-compat、 詳細は § 2.3 参照、 Round 3 [Warning 1] 反映)
- cross_pair.py は canonical 計算を一切呼ばない (= `_try_evaluate_canonical_five_safe` を import すらしない)

### 2.3 `CrossPairResult` の新規属性 (= multiprocessing pickle 互換、 repr/compare 除外)

```python
@dataclass(frozen=True)
class CrossPairResult:
    target_pair: str
    anchor_pairs: tuple[str, ...]
    aggregator_name: str
    window: tuple[datetime, datetime]
    passed: bool
    metrics: Mapping[str, object]
    reason_codes: tuple[str, ...] = ()
    # B step 1.8: dual-path 経路用 ephemeral sidecar (= public API ではない、
    # archive / payload transport には絶対流れないことを test で固定)。
    # Round 2 [Critical 2] 反映: MappingProxyType は multiprocessing で pickle 不可
    # のため通常 dict を default_factory で生成。 repr=False / compare=False で
    # snapshot 比較 / equality 比較から除外。
    _shadow_sidecar_inputs: dict[str, _PairSidecarInputs] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )
```

**設計判断**:
- leading underscore で「ephemeral / 内部用」 を命名で明示
- `default_factory=dict` で multiprocessing pickle 互換性確保 (= Round 2 [Critical 2] 反映、 `parallel_eval._pool.map(...)` 経路で `pickle.dumps` できる)
- `repr=False` / `compare=False` で既存 snapshot 比較 / dataclass equality に sidecar が混入しない (= Round 2 [Warning] 反映)
- `CrossPairResult` の既存 7 fields は順序・型完全不変 (= positional caller 互換性、 既存 `_make_skipped_result` 等は default で空 dict を取る)
- skip 時は default の空 dict (= sidecar 不在 = dual-path も skip)
- 既存 archive `_extract_cross_pair` 経路では `metrics` だけを参照する設計 (= sidecar は archive に流れない)、 acceptance test で固定
- immutability は payload 返却前の sanitize (= § 2.4) + shallow copy で実質担保 (= 通常 dict だが production code は touch しない契約)

### 2.4 stage_gate.py 側で per-pair iterate して canonical 計算 + log emit + sanitize

`evaluate_stage_c` の cross_pair 区画 (= stage_gate.py:1508-1555) の **既存 cp_result 受け取り後、 cross_pair_payload 確定後** に **別 try ブロック** で dual-path、 完了後に sanitized `CrossPairResult` へ差し替え (= sidecar が payload / IPC に残らないことを保証):

```python
from dataclasses import replace  # 既存 import に追加 (= 既存 src 内に同 import あり)

# 既存 cross_pair 経路 (= cross_pair_payload 確定、 完全不変)
# ... cross_pair_evaluator.evaluate(...) → cp_result → cross_pair_payload[...] ...

# === 新規 dual-path: per-pair canonical 計算 + log emit (= 別 try で物理隔離) ===
if cp_result is not None and not bool(cross_pair_payload["skipped"]):
    sidecar_map: dict[str, _PairSidecarInputs] = getattr(
        cp_result, "_shadow_sidecar_inputs", {}
    ) or {}
    enabled = stage_config.phase2_canonical_metrics_mode != "disabled"
    for pair, sidecar in sidecar_map.items():
        try:
            canonical_sidecar_cp = _try_evaluate_canonical_five_safe(
                trades=sidecar.trades,
                equity_curve=sidecar.equity_curve,
                bars=sidecar.bars,
                live_criteria=stage_config.live_criteria,
                window_days=stage_config.stage_c_holdout_days,
                stage_label="C_cross_pair",
                genome_name=genome.name,
                enabled=enabled,
            )
            try:
                _log_canonical_dual_path(
                    stage_label="C_cross_pair",
                    genome_name=genome.name,
                    legacy=sidecar.bt,
                    canonical=canonical_sidecar_cp,
                    pair_label=pair,  # 新規 optional kwarg = 実 pair 名 (例 "EUR_USD")
                )
            except Exception as log_exc:
                logger.warning(
                    "stage_gate.canonical_five.log_failed",
                    stage="C_cross_pair", genome=genome.name, pair=pair,
                    error=str(log_exc), error_type=type(log_exc).__name__,
                )
        except Exception as canonical_exc:
            logger.warning(
                "stage_gate.canonical_five.unexpected_failure",
                stage="C_cross_pair", genome=genome.name, pair=pair,
                error=str(canonical_exc), error_type=type(canonical_exc).__name__,
            )

# === sanitize (= sidecar が payload / IPC / archive に絶対残らないことを保証) ===
# Round 2 [Critical 1] 反映: del sidecar_map だけでは cp_result が
# cross_pair_payload["result"] / GenomeStageResult.cross_pair に格納された後も
# sidecar を保持し続けるため、 cp_result を sanitize 版に差し替える必須経路。
# 例外発生時 / disabled mode / sidecar_map 空 (= cp_result is None or skipped) でも
# 安全に走る (= cp_result is None なら何もしない)。
if cp_result is not None and getattr(cp_result, "_shadow_sidecar_inputs", None):
    cp_result_sanitized = replace(cp_result, _shadow_sidecar_inputs={})
    cross_pair_payload["result"] = cp_result_sanitized
    # 注: 上記 dual-path ブロック以後、 cp_result の参照を使わない (= 取り違え防止)。
    # 後段の payload return 経路は cross_pair_payload["result"] のみ参照する設計を維持。
```

**設計判断**:
- `cp_result._shadow_sidecar_inputs` は `getattr(..., {})` で安全 access (= backward-compat、 古い CrossPairResult instance が来ても crash しない)
- `pair_label=pair` は **実 pair 名** (= `"EUR_USD"` 等)、 役割識別 (= target / anchor1 / anchor2) は emit しない (= Round 1 [Suggestion] 反映、 SSOT 簡潔化、 将来 role 分析時は § 2.6 の `(target_pair, anchor_pairs)` join 経路で対応)
- 物理隔離: 二重 try (= helper 例外 + log 例外) で多層防御、 cross_pair_payload / cp_result.metrics には絶対書き込まない (= sanitize は sidecar を空に置き換えるだけで metrics には touch しない)
- enabled=False (= disabled mode) のとき helper は None 返り、 `_log_canonical_dual_path(canonical=None, pair_label=pair)` で `canonical_skipped=True, pair=<pair>` の dual_path event は emit される (= step 1.6 disabled mode と同型)
- **sanitize 経路** (= Round 2 [Critical 1] 反映): canonical log 完了後、 cp_result を `_shadow_sidecar_inputs={}` 版に差し替えて payload に格納する。 これにより:
  - `cross_pair_payload["result"]` = sanitized cp_result (= sidecar 空)
  - `parallel_eval._extract_cross_pair_result(c_result)` も sanitized 版を返す
  - `GenomeStageResult.cross_pair` も sanitized 版で IPC pickling 経路を通る
  - sidecar dict は元 cp_result が GC 対象になるタイミングで dispose
- sanitize は **dual-path 例外時にも常に走る** (= 例外ハンドリング外、 上記コード末尾で if-guard)、 acceptance E1/E2 で「payload 内 sidecar が空」 を deep snapshot 比較で固定

### 2.5 `_log_canonical_dual_path` への `pair_label` 追加 (= step 1.6 `fold_index` 同型)

```python
def _log_canonical_dual_path(
    *,
    stage_label: str,
    genome_name: str,
    legacy: BacktestMetrics,
    canonical: CanonicalFiveResult | None,
    fold_index: int | None = None,
    pair_label: str | None = None,  # 新規 step 1.8
) -> None:
    # 識別子契約 SSOT 拡張 (= step 1.6 B_fold + step 1.8 C_cross_pair)
    if stage_label == "B_fold" and fold_index is None:
        raise ValueError(...)  # step 1.6 既存
    if stage_label == "C_cross_pair" and pair_label is None:
        raise ValueError(
            "_log_canonical_dual_path(stage_label='C_cross_pair') requires pair_label "
            "(= step 1.8 acceptance D5 / 識別子契約 SSOT、 "
            "C_cross_pair log entry は (stage, genome, pair) で一意特定可能でなければならない)"
        )

    # ... (canonical is None / canonical exists) の両分岐で
    #     pair_label is not None なら log_kwargs["pair"] = pair_label を追加 ...
```

**設計判断**:
- step 1.6 で `fold_index` を追加した同型 backward-compatible 拡張
- 既存 51 caller (= A / B_IS / B_fold / C_base / C_stress) は keyword 呼出で完全互換 (= `pair_label=None` default)
- `stage_label="C_cross_pair"` 限定 fail-fast (= acceptance D5)、 pair_label 不在は識別子契約違反

### 2.6 stage_label / 識別子契約 SSOT 拡張 + 将来 role 分析時の join 設計

| stage_label | 評価対象 | step | fold_index | pair_label |
|---|---|---|---|---|
| `A` | Stage A 評価窓 (60d) | step 1 | None | None |
| `B_IS` | Stage B 18m 全体 IS | step 1.5 | None | None |
| `B_fold` | Stage B per-fold OOS | step 1.6 | 必須 (0..n_fold-1) | None |
| `C_base` | Stage C base evaluation (holdout 60d) | step 1.5 | None | None |
| `C_stress` | Stage C spread stress backtest | step 1.7 | None | None |
| **`C_cross_pair` (本)** | Stage C cross-pair (ii-lite) shadow per-pair | **step 1.8** | None | **必須 (実 pair 名 = "EUR_USD" 等)** |

各 dual-path log には `interpretation_note="direction_monitoring_only"` を継承 (= step 1 で導入済)。

C_cross_pair log entry の識別子契約: `(stage="C_cross_pair", genome=<genome.name>, pair=<実 pair 名>)` の 3 つで一意特定可能 (= 1 entry / genome / pair、 計 3 entries / genome / Stage C 評価)。

`_log_canonical_dual_path` の識別子契約 SSOT 拡張:
- `stage_label="B_fold"` → `fold_index` 必須 (= ValueError fail-fast、 step 1.6 で確立済)
- `stage_label="C_cross_pair"` → `pair_label` 必須 (= ValueError fail-fast、 本 step で新設)
- 他 stage は両 kwargs 共に None default (= A / B_IS / C_base / C_stress)

#### 将来 role 分析時の join 設計 (= Round 2 [Suggestion] 反映)

dual-path log には role (target / anchor1 / anchor2) を emit しない方針を採用。 将来 role 別の挙動分析が必要になった場合は **後段集計で Stage C payload 側の `target_pair` / `anchor_pairs` と join する** 前提:
- dual-path log: `(stage="C_cross_pair", genome=<g>, pair=<p>)` で identifier
- Stage C payload: `payload["cross_pair"]["result"].target_pair` (= target pair 名) + `.anchor_pairs` (= anchor pair tuple)
- 後段集計で `(genome, pair)` → role mapping を `payload.target_pair == pair` か `pair in payload.anchor_pairs` で判定
- 利点: dual-path log が SSOT 簡潔 (= pair 名のみ)、 role は payload 側に既存、 join で復元可能

### 2.7 名前空間隔離契約 (= Round 1 [Warning] 反映)

`CrossPairResult._shadow_sidecar_inputs` は **archive / payload に絶対流れない** ことを以下で固定:
- archive 書き出し経路 (`_extract_cross_pair_result` 等): metrics dict 経由のみ参照 → sidecar は不在
- archive Parquet schema: cross_pair 関連カラム (= aggregate_fitness / mean_sharpe / sharpe_per_pair JSON 等) に sidecar 起源 field を持たせない
- acceptance test (= 新規 transport 固定 test): 任意の `CrossPairResult(_shadow_sidecar_inputs=...)` に対して archive 書き込み結果 / `cross_pair_payload` の deep snapshot に sidecar が混入しないことを deep equality で固定

### 2.8 canonical / legacy gate の意味整合 (collider bias 注記)

**Fact**:
- Stage C cross_pair の canonical 計算入力 (per-pair): `pair_bars[pair]` + `_run_pair_sharpe` 内 backtest の trades / equity_curve
- 各 pair は **異なる instrument + 異なる spread/cost params** (= per-pair home モード、 T019 で MockBroker 多通貨対応済)
- canonical 側 threshold は全 pair で同じ (= `stage_config.live_criteria` ベース、 60d window scaling)、 実際の cross_pair gate (= aggregate_fitness / mean_sharpe / sharpe_ratio / min_sharpe) とは異なる軸
- 既存 cross_pair pass criteria は **集約値 (= per-pair sharpe の mean / std / min / target_ratio)** に対する判定、 per-pair canonical はいわば「ii-lite gate の constituent observability」

**Interpretation (collider bias 警告)**:
- per-pair canonical の pass/fail を「ii-lite gate に通る genome の特徴」 と因果解釈すると collider bias (= cross_pair pass は集約 sharpe gate を通った subgroup、 per-pair canonical はその constituent)
- per-pair canonical の pass/fail を既存 cross_pair gate の代理指標と解釈してはならない (= 別ゲート観測)
- step 1.8 の C_cross_pair dual-path log は **descriptive observation only**、 解釈側で run/genome 横断 n>30 を満たした後の集計でのみ評価する (= C7 sample size guard)
- per-pair canonical の比較は **後段集計で `(genome, pair)` を join した descriptive analysis のみ** (= 単一 dual-path log entry には同 pair 内の `legacy - canonical` diff のみ、 cross-pair diff は含まない)

### 2.9 sharpe 読み替え表 (= step 1.7 § 2.5 継承 + cross_pair 拡張)

Stage C cross_pair 内には sharpe を表す異なる量が複数系列存在し、 dual-path log の解釈時に混同しないこと:

| 量 | 意味 | 出力先 |
|---|---|---|
| per-pair `sharpe` (= cross_pair 集計入力) | `bt.trade_sharpe_raw` (= **trade-level Sharpe v2**) | `CrossPairResult.metrics["sharpe_per_pair"][pair]` |
| `sharpe_target_cross` | target pair の trade_sharpe_raw | `CrossPairResult.metrics["sharpe_target_cross"]` |
| `mean_sharpe` / `min_sharpe` (= 集約) | per-pair sharpe の集約 | `CrossPairResult.metrics["mean_sharpe"] / ["min_sharpe"]` |
| `aggregate_fitness` | `mean - λ × std` (cross_pair config) | `CrossPairResult.metrics["aggregate_fitness"]` |
| `legacy_sharpe` (dual-path log kwarg) | per-pair `BacktestMetrics.sharpe` (= **bar-level annualized**) | `_log_canonical_dual_path` の `legacy_sharpe` field |
| `canonical_sr_worst_block` / `canonical_sr_worst_annual` (dual-path log kwarg) | per-pair canonical 5 metrics の session-block worst-aggregation Sharpe | `_log_canonical_dual_path` の `canonical_sr_*` fields |

→ 解釈時にどの sharpe を見ているか SSOT で確認すること。 dual-path log の `legacy_sharpe` (per-pair) と `sharpe_per_pair[pair]` は **異なるスケール** (= bar-level annualized vs trade-level Sharpe v2)。

---

## 3. 期待効果 (= 案 A' 採用、 descriptive observation only)

### 3.1 直接的 (= descriptive observation only)

- main flow が canonical 5 metrics の **観測値を Stage C cross_pair で per-pair × 3 で descriptive に生成可能** に (= 3 entries / genome の cross_pair 観測、 cross-pair diff は dual-path log に含まれない)
- step 1.8 完了後の観測点: 6 系列 (= A / B_IS / B_fold / C_base / C_stress / C_cross_pair × 3 pairs) = 6 + n_fold + 2 entries / genome (= n_fold ≈ 8 想定で計 ~16 entries / genome)
- per-pair canonical 比較は **後段集計で `(genome, pair)` を join した descriptive analysis のみ可能**

### 3.2 間接的 (= mission 必須軸の observability 完成)

- **Stage C side calibration data 完全観測** (= base + stress + cross_pair の 3 評価軸全て canonical 観測)
- step 2 着手前提条件 (= mission 軸の observability 完成) を完全達成
- mission 必須軸 (= ii-lite) の per-pair constituent を直接観測、 集約 ii-lite gate の挙動分析の基盤データを確立

### 3.3 live_criteria 達成への寄与

- **直接寄与**: なし (= 観測のみ、 判定ロジック完全不変、 GA fitness 不変)
- **間接寄与**: 中 (= mission 必須軸の per-pair observability、 step 2 での切替判断の constituent data として有用、 ただし「使う」 のは step 2 以降)
- **C_cross_pair canonical_gate_pass** は mission 判定にも切替判定にも使わない (= § 1.5 切替誘因ガード)

---

## 4. 実装方針 (= 案 A' 採用)

### 4.1 変更ファイル候補

1. `src/alpha_factory/stage_gate.py` (= 主改修先):
   - **`_PairSidecarInputs` 新規 frozen dataclass を `CrossPairResult` 近傍に定義** (= Round 2 [Critical 3] 反映、 cross_pair.py から単方向 import で参照可能)
   - `CrossPairResult` dataclass に `_shadow_sidecar_inputs: dict[str, _PairSidecarInputs] = field(default_factory=dict, repr=False, compare=False)` field 追加 (= Round 2 [Critical 2] / [Warning] 反映、 leading underscore + repr/compare 除外 + multiprocessing pickle 互換)
   - `_log_canonical_dual_path` に optional kwarg `pair_label: str | None = None` 追加 (= step 1.6 `fold_index` 同型)
   - `stage_label="C_cross_pair"` で `pair_label is None` のとき ValueError fail-fast 追加
   - log_kwargs に `pair_label is not None` で `log_kwargs["pair"] = pair_label` 追加
   - `evaluate_stage_c` の cross_pair 区画 (= 1508-1555) の cp_result 受け取り後・cross_pair_payload 確定後に:
     - per-pair iterate dual-path 配線追加 (= 別 try、 物理隔離)
     - **sanitize 経路追加** (= `cross_pair_payload["result"] = replace(cp_result, _shadow_sidecar_inputs={})`、 Round 2 [Critical 1] 反映)
   - `from dataclasses import replace` を import (= 既存 src 内に同 import あり、 確認済)
2. `src/alpha_factory/cross_pair.py` (= 最小改修):
   - `from src.alpha_factory.stage_gate import CrossPairResult, _PairSidecarInputs` の追加 import (= 既存 `CrossPairResult` import 行の隣)
   - `_run_pair_sharpe` 戻り値を 3-tuple に拡張 (= sidecar_inputs を 3 番目で返す)
   - `evaluate_cross_pair` で `sidecar_inputs_per_pair` 集約 → `CrossPairResult(_shadow_sidecar_inputs=sidecar_inputs_per_pair, ...)` に渡す
   - `_make_skipped_result` は default 空 dict を維持 (= sidecar 不在 = dual-path skip)
   - **canonical 計算は呼ばない** (= `_try_evaluate_canonical_five_safe` を import すらしない、 責務境界明確化)
3. `src/alpha_factory/parallel_eval.py` / `src/alpha_factory/swim_lane.py`:
   - **完全不変** (= 案 A の伝搬経路は不要、 `CrossPairConfig` 不変なので caller 側の改修なし)
4. テスト追加: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 51 ケース → +n ケース) and/or `tests/alpha_factory/test_cross_pair*.py`
   - **新規 multiprocessing pickle test** (= acceptance E4): `pickle.dumps(CrossPairResult(...))` が両 sidecar 状態 (= 空 / non-空) で成功
   - **新規 sanitize test** (= acceptance E2): dual-path 経路の各分岐 (= 成功 / 例外 / disabled) で payload 内 sidecar が空 dict
5. ドキュメント更新候補: `docs/alpha_factory/cross-pair.md` § dual-path 配線、 `docs/alpha_factory/stage-gates.md` § 4.7 ログ命名規約 SSOT

### 4.2 影響範囲

- stage_gate.py で計算量 +3 calc/genome (= per-pair canonical 計算 3 回、 cross_pair が走った場合のみ)
- per-pair の trades/equity_curve の **参照保持** (= コピーではない) で評価窓中のみ生存、 stage_gate.py 側 dict drop で即時 GC 対象、 メモリ +ɛ の short-lived peak
- archive Parquet schema 不変 (= sidecar は archive に流れない、 acceptance § 2.7 で固定)
- helper シグネチャに `pair_label` 追加 (= optional kwarg、 既存 51 caller 影響なし)

### 4.3 LOG_ONLY 維持

step 1.8 では LOG_ONLY 維持 (= 既存判定経路完全不変、 判定結果回帰 0)。 FAIL_CLOSED 切替は step 2 以降。

### 4.4 メモリ概算 (= acceptance B2 を merge 条件に格上げ、 実測必須)

per-pair backtest を逐次実行する既存設計のため、 sidecar 保持中は 3 pair 分 (= 評価窓 ~60d M1 想定、 ~60K bars 想定):
- per-pair: BarEquitySeries ~5-7 MB / pair, TradeRecord <0.5 MB / pair, business_day_universe / CanonicalFiveResult <50 KB / pair
- 3 pairs 全保持 (= sidecar_inputs_per_pair dict): ~15-22 MB / genome (= **deep copy なし、 既存経路の shallow copy を許容**、 Round 2 [Warning] 反映)
- canonical 計算後 stage_gate.py 側で sanitize (= `replace(cp_result, _shadow_sidecar_inputs={})`) で payload 内 sidecar を空 dict に差し替え、 元の dict は cp_result の GC タイミングで dispose、 long-lived 保持なし
- 6 worker 並列 worst case: 概算 ~90-130 MB / 全体 (= step 1.5 / 1.7 同等オーダー)
- per-genome 追加 RSS: **3 GB/worker を大きく下回る低リスク仮説**
- **実測判断 (= merge 条件に格上げ)**: acceptance B2 (= smoke 5 Run の `/usr/bin/time -l`) で実測 PASS なしで step 1.8 を main merge しない

### 4.5 stage_label 命名 + 識別子契約

`"C_cross_pair"` で C_base / C_stress と区別。 `pair_label` で per-pair 識別 (= 実 pair 名)。 § 4.7 ログ命名規約 SSOT に追記:

| 評価対象 | stage_label | pair_label | step |
|---|---|---|---|
| Stage C base evaluation | `C_base` | None | step 1.5 |
| Stage C spread stress backtest | `C_stress` | None | step 1.7 |
| **Stage C cross-pair per-pair (本)** | **`C_cross_pair`** | **実 pair 名** (例: "EUR_USD") | **step 1.8** |

---

## 5. 制約・前提

### 5.1 前提表 (= 4 段階分解、 step 1.7 と同型 + cross_pair 構造制約反映)

| 前提 | 状態 | 検証方法 / Out-of-scope 理由 |
|---|---|---|
| **(a) Verified — 既存コード / テストで固定済** | | |
| `canonical_adapter.py` の helper が UTC-aware datetime 契約に依存 | **Verified** | step 1 で実装・テスト済 |
| `_try_evaluate_canonical_five_safe` / `_log_canonical_dual_path` は Stage A / B_IS / B_fold / C_base / C_stress で正常動作 | **Verified** | step 1.5 / 1.6 / 1.7 で再利用済、 既存 51 ケース PASS |
| cross_pair_evaluator (= StageCRunCrossPairEvaluator) は実装済 + main flow 配線済 | **Verified** | grep + Read で着手前調査済 (parallel_eval.py:342-365 / swim_lane.py:677、 ctx.cp_inputs is not None で評価) |
| cross_pair 内部で 3 つの per-pair backtest が逐次実行され、 sharpe のみ抽出されて trades/equity_curve は破棄される | **Verified** | cross_pair.py:122-164 `_run_pair_sharpe` で確認 |
| **(b) Inferred — 同型 pattern からの推論、 step 1.8 で実証検証必要** | | |
| `_log_canonical_dual_path` に `pair_label: str | None = None` を追加するのは step 1.6 `fold_index` 追加と同型 backward-compatible 拡張 | **To Verify in step 1.8** | helper docstring 拡張、 acceptance test で C_cross_pair pair-label 契約確認 (= 必須 fail-fast、 1 pair / entry) |
| `CrossPairResult` に新規 dataclass field `_shadow_sidecar_inputs` 追加で archive / payload transport に流れない | **To Verify in step 1.8** | acceptance test (= cross_pair_payload と archive snapshot に sidecar 起源 key が混入しない deep equality) + sanitize 経路 (= `replace(cp_result, _shadow_sidecar_inputs={})`) で payload 内常時空 dict (= acceptance E2) |
| `dict[str, _PairSidecarInputs]` field default が multiprocessing pickle 経路で TypeError を出さない | **To Verify in step 1.8** | acceptance E4 で `pickle.dumps(CrossPairResult(...))` 成功を test 固定 (= MappingProxyType 不採用、 通常 dict + repr=False / compare=False) |
| `_PairSidecarInputs` を stage_gate.py 側に定義して循環依存を回避 | **Verified in design** | cross_pair.py:36 が既に `from src.alpha_factory.stage_gate import CrossPairResult` を持つため、 `_PairSidecarInputs` を CrossPairResult 近傍に定義すれば単方向 import で完結 (= Round 2 独立検証成果 § 9.4) |
| **(c) Unverified — step 1.8 で検証** | | |
| cross_pair.py 内で sidecar 保持 + 返却追加が rigorous に物理隔離可能 | **To Verify in step 1.8** | acceptance test (= cross_pair_payload / cross_pair reasons / cp_result.metrics 完全不変、 deep equality 比較) |
| pair_failure / skipped 経路で C_cross_pair dual-path 行が emit されない (= dual_path event + canonical_five.skipped event 両者) | **To Verify in step 1.8** | skip 整合 acceptance test |
| per-pair の trades/equity_curve 参照保持で peak RSS が 3GB budget 内 | **To Verify in step 1.8 (= merge 条件)** | acceptance B2 (= smoke 5 Run 実測)、 実測 PASS なしで main merge しない |
| **(d) False / Out-of-scope — step 1.8 では達成しない** | | |
| step 2 の前提条件「全 Stage 全評価軸の canonical 観測完成」 | **True after 1.8** | step 1.8 (案 A') 完了で達成 (= base + stress + cross_pair 全観測) |
| C_cross_pair canonical 値の cross_pair gate との calibration 整合 | **Out-of-scope** | step 1.8 では健全性確認のみ。 cross_pair gate との対応付けは step 2 か別 step |
| target pair canonical と Stage C base canonical の cross-stage diff 直接観測 | **False / 未達** | dual-path log は同 pair / 同 stage 内 `legacy - canonical` のみ、 cross-stage 比較は後段 join が必要 |
| pair_failure (= run_backtest 例外) genome での per-pair canonical 観測 | **Out-of-scope** | pair_failure pair は trades / equity_curve が無効、 dual-path skip (= acceptance C6) |

### 5.2 制約

- adapter 改変禁止 (= step 1 で凍結、 案 A' でも canonical_adapter.py は touch しない)
- `_log_canonical_dual_path` シグネチャは backward-compatible 拡張のみ (= optional kwarg `pair_label` 追加、 step 1.6 同型 pattern)
- `_try_evaluate_canonical_five_safe` シグネチャ完全不変 (= stage_gate.py から呼び出すだけ、 cross_pair.py は import しない)
- 既存 `evaluate_stage_c` の戻り `StageResult` schema 不変 (= archive 互換、 cross_pair_payload 全件不変)
- 既存 `CrossPairResult` 7 fields の順序・型完全不変 + 新規 field `_shadow_sidecar_inputs` を末尾追加 (= positional 互換性)、 default 空 dict、 `field(default_factory=dict, repr=False, compare=False)` (= Round 2 [Critical 2] / [Warning] 反映)
- canonical sidecar は archive Parquet 非添付 (= cross_pair.py の `_shadow_sidecar_inputs` は ephemeral in-memory only、 sanitize 経路で payload 内常時空 dict 化、 transport テストで固定)
- `CrossPairConfig` 完全不変 (= dual-path 経路 field 追加なし、 Round 1 [Critical] 反映)
- LOG_ONLY mode で既存判定完全不変
- live_criteria 不変
- `parallel_eval.py` / `swim_lane.py` 完全不変

### 5.3 Acceptance Criteria

**A. 判定結果回帰 0 (必須、 deep dict comparison)**
- [A1] Stage C の `StageResult.passed` / `reason_codes` / `metrics["payload"]["cross_pair"]` の **既存 public keys** (= `skipped` / `result` / `error_type`) が canonical 配線追加で内容不変。 `result` (= `CrossPairResult`) の比較は **`_shadow_sidecar_inputs` を除外比較** (= sanitize 経路で空 dict 化されているため除外比較で判定可能、 Round 3 [Warning 2] 反映)
- [A2] CrossPairResult の `passed` / `reason_codes` / 既存 metrics keys (= sharpe_per_pair / mean_sharpe / std_sharpe / min_sharpe / aggregate_fitness / aggregator_lambda / sharpe_target_single / sharpe_target_cross / sharpe_target_cross_ratio / liquidity_weighted_mean / pass_criteria / skipped / skip_reason / mode) が **不変** (= 既存 public field のみ比較、 新規 `_shadow_sidecar_inputs` は除外、 `field(compare=False)` で dataclass equality からも除外)
- [A3] archive Parquet schema 完全不変 (= cross_pair_payload に書き込まれる sub-set は既存通り、 _shadow_sidecar_inputs は archive に流れない acceptance test で固定)
- [A4] GA fitness 不変
- [A5] Stage A / Stage B IS / Stage B fold / Stage C base / Stage C stress の dual-path log は step 1.7 と完全一致 (= 既存 51 ケース全 PASS で確認)

**B. 運用回帰検証**
- [B1] dual-path log が Stage C cross_pair で per-pair × 3 で crash なく出力 (= cross_pair_payload.skipped is False かつ pair_failure 不在の場合のみ)
- [B2] **(merge 条件に格上げ)** smoke 5 Run で peak RSS が worker 3 GB budget 内、 実測 PASS なしで main merge しない
- [B3] smoke 5 Run の所要時間が step 1.7 比 ±20% 以内
- [B4] dual-path log が legacy log (= cross_pair.pair_failure / stage_c.cross_pair_failure) と独立出力

**C. legacy 比較可能性 + 識別子契約**
- [C1] dual-path log の `stage` field が `"C_cross_pair"` で正しく区別可能
- [C2] `legacy_*` / `canonical_*` field が同 log entry に共存
- [C3] `interpretation_note="direction_monitoring_only"` が継承
- [C4] **C_cross_pair 識別子契約**: `(stage, genome, pair)` 3 つの kwargs key で一意特定可能 (= 1 entry / genome / pair、 fold key 不在、 pair は実 pair 名)
- [C5] C_cross_pair log は `cross_pair_payload["skipped"] is True` または `cp_result is None` または `_shadow_sidecar_inputs` が空のときに emit されない (= **`stage_gate.canonical_five.dual_path` event と `stage_gate.canonical_five.skipped` event の両者** が `stage="C_cross_pair"` で 0 件)
- [C6] **pair-level skip 整合**: pair_failure があった pair に対して C_cross_pair dual-path 行は emit されない (= `_run_pair_sharpe` 内 backtest 例外 pair は sidecar_inputs が None、 dual-path 経路で iterate 対象外)

**D. 例外隔離契約 (= 物理隔離保証)**
- [D1] dual-path 経路で例外発生しても `cross_pair_payload` (= skipped / result / error_type) と `cp_result` (= passed / reason_codes / metrics 既存 keys) 完全不変
- [D2] dual-path 経路の例外は `stage_gate.canonical_five.unexpected_failure` または `stage_gate.canonical_five.log_failed` の WARN log のみ、 既存 `cross_pair.pair_failure` / `stage_c.cross_pair_failure` reason 経路は touch しない
- [D3] monkeypatch で `_try_evaluate_canonical_five_safe` を `stage_label="C_cross_pair"` 限定 raise させても evaluate_stage_c の StageResult が disabled mode と一致 (= `passed` / `reason_codes` / `metrics["payload"]` の deep comparison、 `wall_time_seconds` 除外)
- [D4] dual-path ブロック内では `cross_pair_payload` / `cp_result.metrics` / `sharpe_per_pair` を write しない (= 物理隔離契約、 runtime test では D1/D3 の snapshot deep equality 比較で実質担保)
- [D5] **pair_label 識別子契約 fail-fast**: `_log_canonical_dual_path(stage_label="C_cross_pair")` で `pair_label is None` のとき ValueError raise (= step 1.6 `fold_index` 必須 fail-fast と同型)

**E. 名前空間隔離契約 + multiprocessing pickle / sanitize 経路 (= Round 1 + Round 2 [Critical/Warning] 反映)**
- [E1] `CrossPairResult._shadow_sidecar_inputs` 起源の dict / 値が archive Parquet schema に絶対流れない (= archive 書き込み snapshot に sidecar 起源 key 不在)
- [E2] **payload 内 `CrossPairResult._shadow_sidecar_inputs` が常に空 dict** (= sanitize 経路で `replace(cp_result, _shadow_sidecar_inputs={})` 後に `cross_pair_payload["result"]` に格納される)。 deep snapshot 比較で固定:
  - dual-path 経路成功時に `cross_pair_payload["result"]._shadow_sidecar_inputs == {}`
  - dual-path 経路例外時 (= `_try_evaluate_canonical_five_safe` raise / `_log_canonical_dual_path` raise) でも sanitize は走り、 同様に空 dict
  - disabled mode (= phase2_canonical_metrics_mode == "disabled") でも sanitize は走り、 同様に空 dict
- [E3] `_shadow_sidecar_inputs` 名前 leading underscore で ephemeral / 内部用が明示されている (= public API ではない契約)
- [E4] **multiprocessing pickle 互換**: 主目的は **sanitize 後の `GenomeStageResult` が pickle 可能** (= 親プロセスへ実運用で渡るのは sanitized cp_result、 `cross_pair_payload["result"]._shadow_sidecar_inputs == {}` 状態で `pickle.dumps(GenomeStageResult)` が `TypeError` を出さず成功)。 防御的テストとして `pickle.dumps(CrossPairResult(_shadow_sidecar_inputs={}))` および non-empty `_shadow_sidecar_inputs={"EUR_USD": _PairSidecarInputs(...)}` 両方の成功も望ましい (= Round 3 [Suggestion] 反映、 merge 必須は sanitized 経路に寄せる)。 `field(default_factory=dict)` + 通常 dict 採用 (= Round 2 [Critical 2] 反映、 MappingProxyType 不採用) が key
- [E5] **repr / equality 除外**: `repr(CrossPairResult(...))` に sidecar 起源文字列が含まれない、 `CrossPairResult(...) == CrossPairResult(...)` (= sidecar 内容のみ異なる) で True (= Round 2 [Warning] 反映、 `repr=False` / `compare=False` が key)
- [E6] **GenomeStageResult.cross_pair の sanitize 確認**: `parallel_eval._extract_cross_pair_result(c_result)` の戻り値が sanitize 後の cp_result (= `_shadow_sidecar_inputs == {}`) であること

---

## 6. スコープ外

1. **canonical 5 軸ベース判定** (= LOG_ONLY → FAIL_CLOSED 切替): step 2 以降
2. **stage_bc_evaluator 統合**: B Phase 2 step 2
3. **archive Parquet schema 拡張**: 後続別 step (= per-pair canonical 値の永続化は step 3 cpps_archive 統合と合わせて検討)
4. **cross_pair gate との calibration 解釈**: 別計画 (= run/genome 横断 n>30 後)
5. **canonical 5 metrics の数値妥当性判定**: step 1.8 では「crash なく動く」 + 「rigorous な物理隔離」 のみ確認
6. **case B / case C** (Round 1 で否決済): 案 A' で進行、 case B/C は概念設計上から削除済

---

## 7. リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| dual-path 経路の例外で cross_pair_payload / cp_result を巻き込む | 高 | step 1.5/1.6/1.7 と同型 物理隔離 (= stage_gate.py 内別 try ブロック)、 acceptance D1-D5 で完全防御 |
| per-pair の trades/equity_curve 参照保持で peak RSS が 3GB budget を超過 | 中 | acceptance B2 (= **merge 条件に格上げ**) で smoke 5 Run 実測、 設計時は低リスク仮説 (= base 同等オーダー、 参照保持で deep copy なし)、 超過時は step 1.8 を main merge せず縮小案 (= target のみ観測 = 案 B フォールバック) を再設計 |
| `pair_failure` (= run_backtest 例外) pair で sidecar_inputs が無効値で adapter ValueError | 高 | sidecar_inputs を Optional 戻り値とし、 None pair は dual-path skip (= acceptance C6) |
| `cross_pair_inputs is None` (= cp_evaluator が None) のとき dual-path 行が誤って emit される | 中 | dual-path 配線を `cp_result is not None and not cross_pair_payload["skipped"]` ガードで二重防御、 acceptance C5 で確認 |
| `_log_canonical_dual_path` への `pair_label` 追加で既存 51 caller (= A / B_IS / B_fold / C_base / C_stress) が動作不変か | 中 | optional kwarg + None default で完全 backward-compatible、 既存 51 ケース全 PASS で確認 (= acceptance A5) |
| `CrossPairResult` 新規 field `_shadow_sidecar_inputs` が archive / payload に漏れる | 高 | acceptance E1/E2 で deep snapshot 比較固定 + sanitize 経路 (= `replace(cp_result, _shadow_sidecar_inputs={})`) で payload 内常時空 dict 化 (= Round 2 [Critical 1] 反映)、 leading underscore で ephemeral 命名明示、 transport テスト追加 |
| `CrossPairResult` の新規 field が multiprocessing pickle 経路で TypeError | 致命 | `field(default_factory=dict, repr=False, compare=False)` で通常 dict を採用 (= Round 2 [Critical 2] 反映)、 acceptance E4 で `pickle.dumps` 成功を test 固定。 MappingProxyType / ReadOnlyDict 等 pickle 不可型は使わない |
| `_PairSidecarInputs` を cross_pair.py に定義すると循環依存 (= cross_pair.py が stage_gate.CrossPairResult を import 済) | 高 | `_PairSidecarInputs` を **stage_gate.py の CrossPairResult 近傍に定義** (= Round 2 [Critical 3] 反映)、 cross_pair.py は両方を同 module から import、 単方向経路維持 |
| log volume 増加 (3 entries/genome) で log file 肥大 | 低 | structlog filter で観測 only run / production run で出力レベル切替可能、 acceptance B3 で計測 |

---

## 8. 7 step segmentation 全体俯瞰 (= 進捗反映)

| step | 内容 | 統合先 module | 状態 |
|---|---|---|---|
| step 1 ✨ | canonical_metrics → main flow (= Stage A dual-path) | canonical_metrics | **完了** (commit 9bc6a02) |
| step 1.5 ✨ | Stage B IS + Stage C base dual-path | (stage_gate.py のみ) | **完了** (commit 6276d58) |
| step 1.6 ✨ | Stage B per-fold dual-path | (stage_gate.py のみ) | **完了** (commit 1dadc8b) |
| step 1.7 ✨ | Stage C stress dual-path | (stage_gate.py のみ) | **完了** (commit e3a428b) |
| **step 1.8 (本)** | Stage C cross_pair (ii-lite) dual-path 拡張 | (cross_pair.py + stage_gate.py) | **概念設計 Round 3 APPROVED** (= 案 A' 採用、 Codex Round 1-3 反映済、 Round 3 Warning 3 件 + Suggestion 1 件は文言反映済、 詳細設計フェーズへ進行可) |
| step 2 | stage_bc_evaluator → main flow | stage_bc_evaluator | 後続 |
| step 3-7 | (詳細はハンドオフ § 4) | ... | 後続 |

---

## 9. この設計に効く事実 (= docs/devnotes 要点要約 + Round 2 独立検証成果)

### 9.1 step 1.7 完了 handoff (`devnotes/20260504-0003-B-step1.7-complete-handoff/handoff.md`)
- step 1.7 で 5 系列 (A / B_IS / B_fold / C_base / C_stress) の dual-path 観測点を確立
- § 4.2 推奨判断: 「skeleton 配線 + Protocol 互換性確保 だけ先行する案、 または cross_pair 実装が main flow に来てから配線する案」 = 後者の前提が既に充足
- handoff の「cross_pair_evaluator は通常 None で run」 認識は古く、 着手前調査で否定 (= main flow 配線済)

### 9.2 cross_pair.py 現行構造 (= 着手前調査)
- evaluate_cross_pair: cross_pair.py:214-356 (= 3 backtest + 集約)
- _run_pair_sharpe: cross_pair.py:122-164 (= sharpe のみ抽出、 trades/equity_curve 破棄)
- StageCRunCrossPairEvaluator: cross_pair.py:364-418 (= Protocol 実装 thin adapter)
- ANCHOR_PAIRS: cross_pair.py:63-72 (= target → (anchor1, anchor2) SSOT)
- CrossPairConfig: cross_pair.py:80-114 (= sharpe_target_cross_ratio_min / mean_sharpe_cross_min / min_sharpe_cross_min / aggregator_lambda / mode)、 **案 A' で完全不変**

### 9.3 main flow 配線 (= 着手前調査)
- parallel_eval.py:342-365 — `ctx.cp_inputs is not None` で `cp_evaluator` 作成、 Stage C へ渡す
- swim_lane.py:677 — 同型 配線
- production run で `ctx.cp_inputs` が供給される条件は別 TODO 文脈 (= 通常 cp_inputs は run-config から指定)、 **案 A' では parallel_eval / swim_lane に変更不要**

### 9.4 Round 2 独立検証成果 (= Round 1 [Warning] C1/C4 反映、 詳細設計 round で expansion)

#### (a) `_run_pair_sharpe` の caller 全件
- `cross_pair.py:272-280` (= `evaluate_cross_pair` 内 for-loop の 1 caller のみ)
- 外部からの import / 呼び出しなし (= module-private な `_` prefix の意図通り)
- → 戻り値 3-tuple 拡張は単一 caller の改修で完了

#### (b) `cp_inputs` 構築経路 (= ctx.cp_inputs の origin)
- `parallel_eval.py:147` — `LaneEvalContext.cp_inputs: CrossPairLaneInputs | None = None` field
- `parallel_eval.py:170-176` — 型チェック (CrossPairLaneInputs 必須)
- `parallel_eval.py:344-355` — `ctx.cp_inputs is not None` で cp_evaluator + cp_inputs_dict を作って Stage C 呼出
- `swim_lane.py:677` — 同型配線
- → ctx.cp_inputs は `LaneEvalContext` 構築側 (= run-orchestrator) で供給、 None / non-None の両 path 共に既存配線で対応済

#### (c) payload / archive transport 経路 (= sidecar が漏れない経路の確認)
- `parallel_eval.py:382-399` — `_extract_cross_pair_result(stage_c)` は `stage_c.metrics["payload"]["cross_pair"]["result"]` (= CrossPairResult instance) を返す
- archive `_extract_cross_pair` (別 module、 詳細設計 round で参照): `CrossPairResult.metrics` (= dict) 経由のみ参照 → **`_shadow_sidecar_inputs` は archive に流れない設計が成立**
- → acceptance E1/E2 で deep snapshot 比較固定 (= 詳細設計 round で test 設計)

### 9.5 step 1.6 / 1.7 物理隔離 pattern (= 同型 pattern 参照)
- step 1.5 詳細設計 (`devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md`)
- step 1.6 詳細設計 (`devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md`)
- step 1.7 概念設計・詳細設計 (`devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/`)
- helper シグネチャ拡張 SSOT: `_log_canonical_dual_path(fold_index: int | None = None)` (= step 1.6 で導入、 B_fold で必須 / 他 stage で None) → 本 step で `pair_label: str | None = None` を追加 (= 同型)

### 9.6 git log の関連
- `e3a428b Merge branch 'todo/T085'` (= step 1.7 main commit)
- `1dadc8b Merge branch 'todo/T084'` (= step 1.6 main commit)
- `6276d58 Merge branch 'todo/T083'` (= step 1.5 main commit)
- `9bc6a02` (= step 1 main commit)

---

## 10. 参考資料

- step 1.7 完了 handoff: `devnotes/20260504-0003-B-step1.7-complete-handoff/handoff.md`
- step 1.7 概念設計 (Round 2 APPROVED): `devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/conceptual-design.md`
- step 1.7 詳細設計 (Round 2 APPROVED): `devnotes/20260503-2319-B-phase2-step1.7-stage-c-stress-dual-path/detailed-design.md`
- step 1.5 詳細設計 (Round 4 APPROVED): `devnotes/20260503-1446-B-phase2-step1.5-stage-bc-dual-path/detailed-design.md`
- step 1.6 詳細設計 (Round 2 APPROVED): `devnotes/20260503-2049-B-phase2-step1.6-stage-b-per-fold-dual-path/detailed-design.md`
- canonical_adapter.py (凍結): `src/alpha_factory/canonical_adapter.py`
- cross_pair.py (拡張対象): `src/alpha_factory/cross_pair.py:122-356, 364-418` (= sidecar 保持・返却のみ追加)
- stage_gate.py (拡張対象): `src/alpha_factory/stage_gate.py:170-257 (helper) / 1508-1555 (cross_pair 区画) / CrossPairResult dataclass:544-559`
- 既存 test: `tests/alpha_factory/test_stage_gate_canonical_dual_path.py` (= 51 ケース、 step 1.8 で +n ケース追加予定) and/or `tests/alpha_factory/test_cross_pair*.py`
- docs: `docs/alpha_factory/cross-pair.md` / `docs/alpha_factory/concepts/cross-pair-evaluation-shadow.md`
- Codex Round 1 review: `devnotes/20260504-0010-B-phase2-step1.8-stage-c-cross-pair-dual-path/conceptual-review-round-1.md`
