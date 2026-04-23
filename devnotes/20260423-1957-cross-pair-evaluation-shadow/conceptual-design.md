# 概念設計: cross-pair (ii-lite) evaluation shadow 実装 (T016)

## 1. 目的

`src/alpha_factory/cross_pair.py` を新規作成し、(ii-lite) cross-pair 評価を **Phase 2 では shadow mode (記録のみ)** で実装する。Stage C の interface (`cross_pair_evaluator: CrossPairEvaluator | None`) は T014 で既に確保済みのため、本 TODO ではその Protocol を満たす実装本体と、Stage C へ注入する callable wrapper、config / archive / docs 統合を一括で揃える。

## 2. 仮説

仮説 H1 (主): target ペア単独 Sharpe が高くても、近隣ペア (アンカー 2 本) で同じゲノムを評価すると分散 / 平均 / 最弱値のいずれかで劣化する個体は **過学習・通貨ペア固有のノイズ捕捉** の可能性が高い。集約指標 `F = mean(Sharpe_i) - 0.5 × std(Sharpe_i)` と 3 条件 AND は、これを早期に検知できる。

仮説 H2: shadow mode で archive に記録するだけでも、後段の Phase 4 hard 化に向けた **基準値キャリブレーションのためのデータ蓄積** に十分価値がある。

検証: T016 では「集約・判定が仕様通り動く」「Stage C 通過判定に副作用が無い」「skipped が正しく safe default を返す」までを担保。仮説 H1 自体の検証は run-ga 統合後の実データに委ねる (本 TODO 範囲外)。

## 3. スコープ

### IN

- `src/alpha_factory/cross_pair.py` 新規作成
  - `ANCHOR_PAIRS` マッピング (debate-synthesis.md 6 ペア)
  - `CrossPairConfig` frozen dataclass
  - `evaluate_cross_pair(...)` pure function
  - `StageCRunCrossPairEvaluator` callable adapter (CrossPairEvaluator Protocol 実装)
- 既存 `CrossPairResult` (`src/alpha_factory/stage_gate.py`) との **互換維持**
  (本 TODO で interface を変更しない。本実装が返す `CrossPairResult` は T014 で定義済みのものを使う)
- `config/alpha_factory/default.yaml` に `cross_pair:` セクション追加 (既存 SSOT に従って `ii_lite:` ではなく `cross_pair:` キー名で統一)
- `tests/alpha_factory/test_cross_pair.py` 新規 (集約計算・通過基準・skipped・adapter callable)
- `docs/alpha_factory/cross-pair.md` を実装に合わせて詳細化
- `docs/alpha_factory/terminology.md` に `CrossPairConfig` / `StageCRunCrossPairEvaluator` を追加

### OUT (別 TODO)

- swim-lane / run-ga からの呼び出し統合 (pair_bars 多通貨ロード経路)
- Phase 4 での hard gate 化 (mode='hard' 切替条件決定 + Stage C 失敗 reason 追加)
- aux_pair_bars 経由での RegistryEvaluator pair-specific primitive 連携
- migration-triggers.md の shadow→hard 切替条件具体化

## 4. 主要設計判断

### 4.1 既存 `CrossPairResult` を再利用する

T014 で `src/alpha_factory/stage_gate.py` に `CrossPairResult` が**フィールド固定済み**:

```python
target_pair: str
anchor_pairs: tuple[str, ...]
aggregator_name: str
window: tuple[datetime, datetime]
passed: bool
metrics: Mapping[str, object]
reason_codes: tuple[str, ...]
```

仕様書 (タスク定義) に登場する詳細フィールド (`sharpe_per_pair` / `mean_sharpe` / `std_sharpe` / `min_sharpe` / `aggregate_fitness` / `sharpe_target_cross_ratio` / `pass_criteria` / `skipped` / `skip_reason`) は **`metrics` 辞書のキーとして格納**する (canonical key 集合を本ドキュメント §6 で固定)。これにより:

- archive (`_extract_cross_pair`) は `isinstance(result_obj, CrossPairResult)` で T014 と互換
- `passed` は本 TODO で「3 条件 AND の結果」を入れ、`reason_codes` で失敗詳細を canonical 化
- shadow mode 制御は呼び出し元 (`stage_c.evaluate_stage_c`) が既に `passed` を判定に使わない設計 (`# Phase 2: shadow only — passed には影響させない`) で担保済み

### 4.2 `CrossPairConfig` は本 TODO で新設

`StageGateConfig` とは独立させる (Stage C は cross_pair の有無に関わらず動作)。

```python
@dataclass(frozen=True)
class CrossPairConfig:
    sharpe_target_cross_ratio_min: float = 0.8
    mean_sharpe_cross_min: float = 0.15
    min_sharpe_cross_min: float = -0.20
    aggregator_lambda: float = 0.5
    mode: Literal["shadow", "hard"] = "shadow"
```

`__post_init__` で軽い不変条件 (lambda >= 0, ratio_min ∈ [0, 1] 等) を検証。

### 4.3 anchor_pairs は dict 定数 + config 上書き可能

```python
ANCHOR_PAIRS: Mapping[str, tuple[str, str]] = MappingProxyType({...})
```

を default としつつ、`StageCRunCrossPairEvaluator(anchor_pairs=...)` で外部 (config 由来) から差し替え可能にする。config loader 整備は別 TODO だが、当 TODO で interface を準備しておく。

### 4.4 `evaluate_cross_pair` の I/O

Stage B / C のような実 backtest を **target + anchor 2 本** で 3 回走らせて Sharpe を集める純粋関数。

- 入力: `genome` / `target` / `sharpe_target_single` / `pair_bars: dict[str, list[PriceBar]]` / `pair_meta: dict[str, InstrumentMeta]` / `backtest_config: BacktestConfig` / `primitive_evaluator` / `cross_pair_config`
- 出力: `CrossPairResult` (T014 の dataclass、`metrics` に詳細キーを格納)

`backtest_config.instrument` は target に合わせて `replace(...)` で書き換える (anchor 走らせる際は anchor の instrument 名)。

#### Skipped ポリシー

以下のいずれかで skipped 扱い:

1. `target` が `ANCHOR_PAIRS` に存在しない (= 評価対象外)
2. `pair_bars[target]` または `pair_bars[anchor]` が欠落
3. `pair_meta[target]` または `pair_meta[anchor]` が欠落

skipped 時の `CrossPairResult`:

- `passed=False` (= shadow mode では Stage C に影響しないため安全)
- `reason_codes = ("skipped",)`
- `metrics["skipped"] = True`、`metrics["skip_reason"] = "..."`
- `metrics["sharpe_per_pair"] = {}` 等は空 dict / NaN

各 backtest が個別失敗した場合 (例外 / no-trade) は当該ペアを Sharpe=0.0 として imputation し、`reason_codes` に `"pair_failure:<pair>"` を追記する。

#### archive `ii_lite_pass` 契約 (skipped → None)

T015 archive 実装 (`_extract_cross_pair`) は **`payload["cross_pair"]["skipped"]` の bool 値**を見て `ii_lite_pass = None` を判定する。一方で T014 の Stage C `evaluate_stage_c` は `cross_pair_evaluator.evaluate(...)` 完了時に `cross_pair_payload["skipped"] = False` を**無条件代入**してしまう。本 TODO ではこのギャップを **adapter 層** (`StageCRunCrossPairEvaluator.evaluate(...)`) と **Stage C hook の最小修正** で埋める:

**Stage C 側の最小パッチ** (`src/alpha_factory/stage_gate.py`):

```python
if cross_pair_evaluator is not None:
    if cross_pair_inputs is None:
        raise ValueError(...)
    validated = _validate_cross_pair_inputs(cross_pair_inputs)
    try:
        cp_result = cross_pair_evaluator.evaluate(...)  # 例外隔離
    except Exception as exc:
        logger.warning("stage_c.cross_pair_failure", ...)
        cp_result = None
        cross_pair_payload["skipped"] = True   # ← failure → skipped 扱い
    if cp_result is not None:
        # ★ skipped 判定を CrossPairResult.metrics["skipped"] から伝搬
        cp_skipped = bool(cp_result.metrics.get("skipped", False))
        cross_pair_payload["skipped"] = cp_skipped
        cross_pair_payload["result"] = cp_result if not cp_skipped else None
    # Phase 2: shadow only — cross_pair_payload は passed に影響しない
```

これにより:
- `evaluate_cross_pair` が skipped 時に `metrics["skipped"]=True` で返す → archive `ii_lite_pass = None`
- 例外伝播時も同等に `payload.skipped=True` → `ii_lite_pass = None`
- 通常完了時は `metrics["skipped"]=False` で `ii_lite_pass = bool(cp_result.passed)`

**Stage C は本 TODO で signature 変更しない** (`cross_pair_evaluator: CrossPairEvaluator | None`、`cross_pair_inputs` は既存の TypedDict)。修正は内部実装の hook ロジックのみ。

### 4.5 `StageCRunCrossPairEvaluator` adapter (CrossPairEvaluator Protocol 実装)

T014 `CrossPairEvaluator` Protocol:

```python
def evaluate(
    self, genome, target_pair, pair_bars_map, meta_map, backtest_config,
) -> CrossPairResult: ...
```

を実装するクラス。constructor で `(primitive_evaluator, cross_pair_config, anchor_pairs=None, sharpe_target_single_provider=None)` を受け取り、`evaluate(...)` 内で `evaluate_cross_pair(...)` を呼ぶ thin wrapper。

#### `sharpe_target_single` の取得経路 (実行順序整合)

**問題**: T014 Stage C は `base_sharpe` を計算してから cross-pair hook を呼ぶ実行順序になっているが、現行 Protocol の `evaluate` には `base_sharpe` を渡す引数が無い (`metrics_envelope` は cross-pair hook の後で構築される)。

**解決方針**: T014 Protocol を本 TODO で拡張せず、**adapter constructor の `sharpe_target_single_provider: Callable[[], float | None] | None` 経由で取得**する。Stage C runner 側 (本 TODO 内で hook ロジックの最小パッチ範囲) で、`base_sharpe` 算出後に provider を bind する **2 段構成**:

1. Stage C 内で `base_sharpe` 算出後、`current_base_sharpe = base_sharpe` というローカル変数に保持
2. cross_pair hook の前で `if hasattr(cross_pair_evaluator, "_set_base_sharpe"): cross_pair_evaluator._set_base_sharpe(current_base_sharpe)` を呼ぶ (Protocol 拡張ではなく optional duck-typing)
3. `StageCRunCrossPairEvaluator._set_base_sharpe(value)` で内部 state を更新、`evaluate(...)` 内で参照

**ただし**、Protocol との純粋な契約だけを守る簡潔な代替案もある:

**代替方針 (Phase 2 ratio skip)**: provider を結束しないまま動かし、本 TODO では **ratio 判定を未実装扱い** とする。具体的には `cross_pair_config.sharpe_target_cross_ratio_min` を **monitor only** にし、`metrics["sharpe_target_cross_ratio"] = None`、`metrics["pass_criteria"]["sharpe_ratio"] = None` を返す。3 条件 AND は `mean` と `min` の 2 条件 AND に縮退 (Phase 4 で hard 化時に拡張)。

**本 TODO の決定**: **代替方針 (Phase 2 ratio skip)** を採用する。理由:
- T014 Protocol を破らず、本 TODO 範囲を最小化できる
- swim-lane / run-ga 統合 TODO で interface を増やす際に、`base_sharpe` を kwarg として追加する自然な拡張点を残せる
- shadow mode で記録されるのは「mean / min / std / aggregate」と「2 条件部分判定」となるが、それでも Phase 4 hard 化前のキャリブレーションには十分

ただし、`StageCRunCrossPairEvaluator` constructor には将来の拡張用に `sharpe_target_single_provider` 引数を残しておき、provider が non-None なら ratio を計算する **opt-in 経路** を準備する (本 TODO のテストでは provider 注入経路もカバー)。

### 4.6 集約関数 / 通過基準

主目的:
```
F = mean(Sharpe_i) - λ × std(Sharpe_i)   (λ = config.aggregator_lambda, default 0.5)
```

`std` は **母標準偏差 `ddof=0`** を使う (`statistics.pstdev`)。N=3 固定で標本/母の差は実用的に無視できるが、テストとの整合のため明示的に固定する。

監査値:
- `min_sharpe = min(Sharpe_i)`
- `liquidity_weighted_mean` は **本 TODO 範囲外** (流動性データソースが Phase 2H 時点で未確定。metrics 辞書の `liquidity_weighted_mean: None` 予約のみ)

通過基準 (本 TODO Phase 2 では **2 条件 AND**、Phase 4 で `sharpe_ratio` を加えて 3 条件 AND に拡張):

1. (Phase 4 で有効化) `sharpe_target_cross_ratio >= sharpe_target_cross_ratio_min`
2. `mean_sharpe >= mean_sharpe_cross_min`
3. `min_sharpe >= min_sharpe_cross_min`

Phase 2 では `pass_criteria["sharpe_ratio"]` は provider が non-None のときのみ計算 (= opt-in)。provider 未注入 / `sharpe_target_single in {None, 0}` / `< 0` の場合は `None`。
- `pass_criteria["all"]` の AND 計算は **None を「未確認 = 評価対象外」として除外**してから AND を取る。例: `{sharpe_ratio: None, mean: True, min: True}` → `all = True`
- 全条件 None なら `all = False` (保守的)

`sharpe_target_cross_ratio` の定義: `Sharpe_target_cross / Sharpe_target_single`。
- `Sharpe_target_single == 0 or None`: ratio = None、`pass_criteria.sharpe_ratio = None`
- `Sharpe_target_single < 0`: ratio = None (符号反転で意味が無いため safe-skip)、`pass_criteria.sharpe_ratio = None`

### 4.7 mode (shadow / hard)

`CrossPairConfig.mode = "shadow"` (Phase 2 default) では、本実装の戻り値 `passed` は archive に記録されるのみで Stage C `evaluate_stage_c` の最終 `passed` 判定には影響しない (T014 の `# Phase 2: shadow only` コメント参照)。

`mode = "hard"` への切替は **本 TODO 範囲外** だが、`CrossPairConfig.mode` フィールドを今期点で準備しておくことで、Phase 4 で Stage C 側に「mode == 'hard' なら reason に追加」ロジックを足す際のフックを提供する。

### 4.8 cross-pair 例外の隔離 (shadow 制御フロー無副作用)

T014 Stage C は `cross_pair_evaluator.evaluate(...)` を try/except で包んでいない。本 TODO で **Stage C hook の最小修正** として例外隔離を導入する (§4.4 末尾の Stage C 側パッチ参照):

```python
try:
    cp_result = cross_pair_evaluator.evaluate(...)
except Exception as exc:
    logger.warning("stage_c.cross_pair_failure", genome=genome.name, error=str(exc))
    cp_result = None
    cross_pair_payload["skipped"] = True
```

これで:
- shadow mode では「Stage C `passed` への副作用無し」+「Stage C 制御フロー停止無し」の両方を担保
- archive 側は `payload.skipped=True` → `ii_lite_pass=None` で safe default

### 4.9 cross-pair の実行条件 (Stage C 通過後 vs 全観測)

概念元 doc は「Stage C 通過後に必ず実行」と書くが、本 TODO では **Phase 2 は Stage C 実行個体すべてを観測対象とする** に統一する。理由:

- 「Stage C 通過個体だけ評価」だと、shadow mode で得られる **不通過個体の cross-pair 性能データ** が捨てられる。Phase 4 hard 化時の閾値キャリブレーション (= 「どの cross-pair Sharpe レベルなら本当に意味があるか」) に必要なデータが得られない
- 概念元 doc の表現は **Phase 4 hard 化後の運用** を意図したものとして再解釈できる (cross-pair が hard gate になれば論理的に「Stage C 通過後」と同義)
- Phase 2 では archive に `stage_c_pass` と `ii_lite_pass` の両方が記録されるため、後段分析で `stage_c_pass=True` 個体の `ii_lite_pass` 分布を別途集計可能 (= データを失わない設計)

→ 概念元 doc の該当文を本 TODO 内で「Phase 4 以降」に明示修正する。

### 4.10 命名 SSOT (cross_pair vs ii_lite)

概念元 doc では `ii_lite:` キー、本設計では `cross_pair:` キーを使う混在状態を解消する。

**本 TODO の決定**: **`cross_pair:`** を SSOT とする。理由:
- `src/alpha_factory/cross_pair.py` (本実装ファイル名) と一貫
- terminology.md の `(ii-lite)` は概念名として残しつつ、実装識別子は `cross_pair` に統一
- archive カラム名の `ii_lite_pass` だけは既存 T015 schema との互換性のため維持 (rename は別 TODO)

→ `default.yaml` キー、`CrossPairConfig` クラス名、概念元 doc の YAML サンプルすべてを `cross_pair` で統一。

## 5. 失敗モード分析

| モード | 検出 | 対処 |
|--------|------|------|
| 全 anchor bars 欠落 | `pair_bars[anchor]` 欠落 | skipped (`reason_codes=("skipped",)`、`passed=False`) |
| 一部 anchor bars 欠落 | 同上 | skipped (全体 skip / 部分計算は不可。理由: 集約に N=3 を前提するため) |
| anchor backtest 例外 | `run_backtest` raises | 当該 pair Sharpe=0.0 imputation、`reason_codes` に `"pair_failure:<pair>"`、**fail-fast: `pair_failures != [] → passed=False`** (集約値が信頼できないため) |
| Sharpe = None | `compute_metrics().sharpe is None` (no trades 等) | 0.0 imputation (Stage B と同じポリシー) |
| target single Sharpe <= 0 / None | provider が返す | ratio = None、`pass_criteria.sharpe_ratio = None`、`pass_criteria.all` は mean+min の 2 条件 AND で算出 (None 除外) |
| metrics envelope 不整合 | archive `_extract_cross_pair` | 既存 archive ガードで detection (本 TODO 変更不要) |

## 6. metrics 辞書 canonical key

`CrossPairResult.metrics` に格納する canonical key 集合 (archive consumer がパースしやすいよう固定):

```
sharpe_per_pair: dict[str, float]      # {target: x, anchor1: y, anchor2: z}
mean_sharpe: float | None
std_sharpe: float | None
min_sharpe: float | None
aggregate_fitness: float | None        # mean - λ*std
aggregator_lambda: float
sharpe_target_single: float | None
sharpe_target_cross: float | None
sharpe_target_cross_ratio: float | None
liquidity_weighted_mean: None          # 予約 (本 TODO 範囲外)
pass_criteria: dict[str, bool | None]  # {sharpe_ratio, mean, min, all}
skipped: bool
skip_reason: str
mode: Literal["shadow", "hard"]
```

`pass_criteria["all"]` は 3 条件 AND の結果。skipped 時は全 None と False/all=False。

## 7. テスト設計 (概要)

`tests/alpha_factory/test_cross_pair.py`:

1. **ANCHOR_PAIRS 整合性**: 6 ペア、各 anchor が 2 本、自己参照禁止
2. **CrossPairConfig 不変条件**: 不正値で ValueError
3. **集約計算**: synthetic Sharpe (例: [0.8, 0.6, 0.4]) → mean=0.6, pstdev=0.163, F = 0.6 - 0.5*0.163 = 0.518 (allclose 1e-6、`statistics.pstdev` 使用)
4. **通過基準境界 (Phase 2 = mean / min の 2 条件)**: 各境界 ±epsilon
5. **2 条件 AND**: 1 条件落ちで `pass_criteria.all=False`、両通過で `True`
6. **target single = 0 / None / 負 (provider 注入時)**: ratio=None、`pass_criteria.sharpe_ratio=None`
7. **provider 未注入 (default)**: `pass_criteria.sharpe_ratio=None`、`pass_criteria.all` は mean+min の AND
8. **provider 注入かつ valid**: `sharpe_target_cross_ratio` 数値、3 条件 AND
9. **skipped (anchor pair_bars 欠落)**: `reason_codes=("skipped",)`、`passed=False`、`metrics.skipped=True`
10. **skipped (target 未登録)**: 同上
11. **pair backtest 例外**: 0.0 imputation、`reason_codes` に `"pair_failure:..."` 追加
12. **StageCRunCrossPairEvaluator が CrossPairEvaluator Protocol 実装**: `isinstance(adapter, CrossPairEvaluator)` 相当の duck-typing チェック (Protocol は runtime_checkable でない場合 hasattr で確認)
13. **Stage C 統合 (例外隔離)**: adapter が例外を投げる stub の場合、`stage_c.passed` が cross-pair 例外で fail にならず、`payload.cross_pair.skipped=True` になること
14. **Stage C 統合 (skipped 伝搬)**: adapter が skipped Result を返す場合、`payload.cross_pair.skipped=True` になり archive `ii_lite_pass=None`
15. **Stage C 統合 (通常完了)**: `payload.cross_pair.skipped=False` かつ `result` が CrossPairResult、`stage_c.passed` は **本実装結果に左右されない** (= Stage C base 判定のみで決まる)
16. **archive ii_lite_pass 連動**: `GenomeArchive.collect_stage_c` 後
    - skipped → `ii_lite_pass=None`
    - 通常完了 → `ii_lite_pass = bool(result.passed)`

## 8. 設定統合

`config/alpha_factory/default.yaml` に追記:

```yaml
cross_pair:
  mode: shadow                                # shadow | hard (Phase 4 で hard 化)
  aggregator_lambda: 0.5                       # F = mean - λ*std
  pass_criteria:
    sharpe_target_cross_ratio_min: 0.8
    mean_sharpe_cross_min: 0.15
    min_sharpe_cross_min: -0.20
  anchors:
    EUR_JPY: [EUR_USD, USD_JPY]
    USD_JPY: [USD_CAD, EUR_JPY]
    EUR_USD: [EUR_JPY, USD_CAD]
    AUD_JPY: [USD_JPY, EUR_USD]
    USD_CAD: [USD_JPY, EUR_USD]
    USD_ZAR: [USD_CAD, USD_JPY]
```

YAML loader は本 TODO では追加しない (StageGateConfig と同様、別 TODO で run-ga 統合時にまとめて実装)。SSOT としての記載のみ。

## 9. 関連ドキュメント

- `docs/alpha_factory/cross-pair.md` (本実装で詳細化)
- `docs/alpha_factory/terminology.md` (CrossPairConfig / StageCRunCrossPairEvaluator 追加)
- `docs/alpha_factory/stage-gates.md` (Phase 4 で hard 化時に reason 追記、本 TODO は変更しない)
- `docs/alpha_factory/concepts/cross-pair-evaluation-shadow.md` (本概念設計の origin)

## 10. 残課題 (本 TODO 範囲外、別 TODO に積む想定)

1. **swim-lane / run-ga 統合**: 多通貨ペアの bars / meta を 1 generation でロードする経路と、`StageCRunCrossPairEvaluator` への注入
2. **liquidity_weighted_mean 実装**: 流動性データソース (volume / spread) 確定後
3. **Phase 4 hard 化**: `mode='hard'` で Stage C `passed` への AND 合成、reason 語彙追加
4. **migration-triggers.md**: shadow → hard の具体的閾値 / 観測 N の決定
5. **aux_pair_bars 経由での pair-specific primitive 連携**: RegistryEvaluator が `aux_series` で他通貨ペアの状態を参照する経路
