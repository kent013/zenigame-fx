# 詳細設計: Run 87 施策 (cycle 5: cross-pair multi-pair shadow 有効化)

## 使命・制約
mission 個体の汎化 (多ペア通用) を観測可能にする。cross-pair を shadow で実走させ ii_lite_pass を計測。**default (anchor 未指定) は現状 skipped で挙動完全不変**。graduation 強制は次サイクル (hard 化は汎化の壁を見てから)。

## 真因 (確定)
graduation=0 は run が単一銘柄で cross-pair 構造スキップ。`run_ga.py:1934` で `GraduationLane(pair_bars={}, pair_meta={})` 空ハードコード → `_build_cross_pair_args` が (None,None) 返す (swim_lane.py:967) → cross-pair skipped。機構は揃うが複数ペアデータ未供給。

## 施策: anchor ペア holdout bars を GraduationLane に供給 (shadow 実走)

### 変更箇所
1. **config / CLI**: `cross_pair_anchors: list[str] = []` (CrossPairConfig or DatasetConfig)。CLI `--cross-pair-anchors USD_JPY,EUR_USD` (カンマ区切り、default 空)。default 空 = 現状 skipped 維持 (挙動不変)。
2. **run_ga.py (1934 付近 GraduationLane 構築)**:
   ```python
   pair_bars: dict[str, list[PriceBar]] = {}
   pair_meta: dict[str, InstrumentMeta] = {}
   anchors = cfg.cross_pair.anchors  # default []
   if anchors:
       # target pair (EUR_JPY) の holdout を含める (cross-pair は target も pair_bars に必要)
       pair_bars[cfg.dataset.instrument] = bundle.bars_holdout
       pair_meta[cfg.dataset.instrument] = bundle.meta
       for anchor in anchors:
           if anchor == cfg.dataset.instrument:
               continue
           a_bundle = _load_lane_bars(anchor, cfg.dataset, cfg.stage_windows)  # 既存loader流用
           pair_bars[anchor] = a_bundle.bars_holdout
           pair_meta[anchor] = a_bundle.meta
   graduation_lane = GraduationLane(lane_id=GRADUATION_LANE_ID, pair_bars=pair_bars, pair_meta=pair_meta)
   cross_pair_mode = "enabled" if graduation_lane.pair_bars else "skipped_single_instrument"
   ```
   - `_load_lane_bars` は Stage A/B/holdout 3 区間ロードするが holdout のみ使用 (anchor は cross-pair holdout 評価のみ必要)。Stage A/B ロードのオーバーヘッドは anchor 数 × 1 回のみ (GA ループ外)。最適化は次段。
3. **cross_pair_config.mode は shadow 維持** (default)。**【解決済】** `_extract_cross_pair_result` (swim_lane.py:980-1004) は mode を参照せず、`cross_pair.skipped==False` かつ result が CrossPairResult なら返す。`graduation_criteria` (402-429) はその `.passed` を見る。∴ **anchor 供給で cross-pair が実走 (skipped=False) すれば、shadow mode のままで graduation = Stage C pass AND cross_pair.passed が自然に機能する** (shadow の意味 = Stage C 自身の passed は cross-pair の影響を受けない、で保たれる)。hard mode は不要。
   - 帰結: anchor 供給だけで (a) ii_lite_pass が None→bool 化し汎化定量化、(b) cross-pair pass 個体があれば graduation>0 が自然に出る。cross-pair pass が 0 なら graduation=0 のままだが ii_lite_pass 分布で壁を定量化。**全面 hard 化不要 = 全滅リスクなし** (Stage C は cross-pair で抑止されない)。

### 波及変更
- config.py (CrossPairConfig or 新 section に anchors)、run_ga.py (CLI + GraduationLane 構築)、AGENTS.md/SKILL.md (CLI 追記)。
- summary.json の cross_pair_runtime_mode が "enabled" になる。

### メモリ
- anchor 1-2 ペア × holdout 60d M1 (~60k bars/pair PriceBar)。GA worker への broadcast (LaneEvalContext immutable) で ×workers。anchor 2 + target = 3 ペア × 60k × 2 worker ≈ 360k PriceBar ≈ 数百MB。24GB 制約下で anchor<=2 に制限。Codex で確認。

### テスト計画
- [ ] anchors=[] (default) で GraduationLane.pair_bars 空 = cross_pair skipped = 現状挙動不変 (既存テスト pass)。
- [ ] anchors=["USD_JPY"] で pair_bars に target+anchor が入り cross_pair_runtime_mode=enabled。
- [ ] _build_cross_pair_args が anchors 指定時に evaluator を返す (None でない)。
- [ ] cross-pair shadow 実走で ii_lite_pass が None でなく bool になる (integration、小規模 bars fixture)。
- [ ] anchor == target の重複除外。anchor の bars ロード失敗時の fail 挙動 (fail-closed か skip か Codex で決定)。

### リスク
- 中-大: データロード (anchor M1)、メモリ (worker broadcast)、Phase 2 統合 (T102) との重複可能性。R87 は multi-pair で更に低速化 (holdout cross-pair 評価が pair 数分)。
- shadow→graduation 反映経路が要検証 (上記)。最悪 shadow では graduation 効かず ii_lite_pass 計測のみ → それでも汎化定量化の価値あり (次サイクルで hard 化)。

## Run 87 実行パラメータ
| パラメータ | 値 |
|-----------|-----|
| instrument | EUR_JPY |
| **cross-pair-anchors** | **USD_JPY** (まず1 anchor で軽量検証) |
| warmstart-ratio | 0.1 (R85 motif、mission個体で cross-pair 評価母集団確保) |
| warmstart-motif-archive | .cache/.../genomes_run_20260520_202321.parquet (R85) |
| seed | 68 |
| pop/gen | 96/60 |

> R87 で cross_pair_runtime_mode=enabled、ii_lite_pass が True/False 分布を持ち、warmstart mission 個体が USD_JPY でも通用するか (汎化) を定量化。

## Codex design-review Round 1: CHANGES_REQUESTED → 改訂 (Round 2 で確認予定)

Round 1 [Critical/Warning] 反映で設計を以下に改訂:

### ★ Critical 1: 本番 parallel 経路 (LaneEvalContext.cp_inputs) への配線必須
本番は `GenomeEvaluator` (parallel_eval.py) 経路で、`run_ga.py:2011` が `LaneEvalContext(cp_inputs=None)` をハードコード。`evaluate_genome` は `cp_inputs is not None` 時のみ cross-pair 実行 (parallel_eval.py:344)。
→ **anchor 指定時は GraduationLane.pair_bars だけでなく `LaneEvalContext.cp_inputs` にも `{target_pair, pair_bars_map, meta_map}` を配線**する (これが本線)。GraduationLane.pair_bars は lane-manager 逐次経路用 (両方供給)。

### ★ Critical 2: cross_pair は target ごとに固定 2 anchor 必須
cross_pair.py:63/285-287: 各 target は `ANCHOR_PAIRS[target]` の 2 ペア (EUR_JPY → EUR_USD + USD_JPY) が必要。不足は `missing_bars` で skipped。
→ **`--cross-pair-anchors` は廃止し、anchor は `cross_pair.ANCHOR_PAIRS[target]` を自動採用** (2 ペア)。CLI は `--cross-pair-enable` フラグ (or cross_pair_config に enable bool) のみ。default OFF (空 = 現状 skipped 不変)。
- R87: `--cross-pair-enable` で EUR_JPY の anchor=EUR_USD+USD_JPY を自動ロード。

### Warning 1: cross_pair_runtime_mode は cp_inputs 基準
`cross_pair_mode = "enabled" if lane_ctx.cp_inputs else "skipped_single_instrument"` に変更 (graduation_lane.pair_bars でなく)。

### Warning 2: anchor は holdout-only loader
`_load_lane_bars` は Stage A/B も無駄ロード。anchor 用に holdout-only の軽量 loader (`_stream_bars` を holdout 区間のみで呼ぶ) を分離。

### 改訂後の変更箇所
1. config: `cross_pair.enable: bool = False` (default OFF=挙動不変)。CLI `--cross-pair-enable`。
2. run_ga.py: enable 時、`ANCHOR_PAIRS[target]` の holdout bars を holdout-only loader でロード → `pair_bars/pair_meta` 構築 → (a) `LaneEvalContext.cp_inputs={target_pair, pair_bars_map, meta_map}` (本線)、(b) `GraduationLane(pair_bars, pair_meta)` (逐次経路)、(c) cross_pair_runtime_mode を cp_inputs 基準に。
3. cross_pair_config.mode=shadow 維持。
4. テスト: enable=False で cp_inputs=None=現状不変 / enable=True で cp_inputs に target+2anchor、cross_pair_runtime_mode=enabled、ii_lite_pass bool 化 (integration)。

### 調査完了 (Round 2 用、具体化)
- `cross_pair.ANCHOR_PAIRS` (cross_pair.py:63-71): 全 6 target 対応。EUR_JPY→(EUR_USD, USD_JPY)。`MappingProxyType`。
- `parallel_eval.CrossPairLaneInputs` (parallel_eval.py:82): `target_pair: str`, `pair_bars_map: Mapping[str, tuple[PriceBar,...]]`, `meta_map`。frozen、defensive copy + tuple 化 + pickle 対応済 (worker broadcast 安全)。
- `parallel_eval.py:344-365`: `ctx.cp_inputs is not None` 時に cp_inputs_dict 構築し `cross_pair_inputs=` で評価へ。
- `run_ga.py:2004-2013`: `LaneEvalContext(..., cp_inputs=None, ...)` を構築。

### 具体実装 (run_ga.py:2004 付近)
```python
cp_inputs = None
if cfg.cross_pair.enable:
    from src.alpha_factory.cross_pair import ANCHOR_PAIRS
    from src.alpha_factory.parallel_eval import CrossPairLaneInputs
    tgt = cfg.dataset.instrument
    anchors = ANCHOR_PAIRS.get(tgt)  # (a1, a2) or None
    if anchors:
        pbm = {tgt: tuple(bundle.bars_holdout)}
        mm = {tgt: bundle.meta}
        for a in anchors:
            a_holdout, a_meta = _load_holdout_only(a, cfg.dataset, cfg.stage_windows)  # 新 holdout-only loader
            pbm[a] = tuple(a_holdout); mm[a] = a_meta
        cp_inputs = CrossPairLaneInputs(target_pair=tgt, pair_bars_map=pbm, meta_map=mm)
        # GraduationLane にも供給 (逐次経路): pair_bars={k:list(v)...}, pair_meta=mm
lane_ctx = LaneEvalContext(..., cp_inputs=cp_inputs, ...)
cross_pair_mode = "enabled" if cp_inputs is not None else "skipped_single_instrument"
```
- `_load_holdout_only(instrument, dataset, stage_windows)`: 新規軽量 loader。`_stream_bars` を holdout 区間 `[dataset.end, dataset.end + holdout_days)` のみで呼び (bars, meta) を返す。Stage A/B はロードしない。
- default `cfg.cross_pair.enable=False` → cp_inputs=None → 現状と完全同一 (skipped)。
- anchor が ANCHOR_PAIRS に無い target は cp_inputs=None (skip、warning)。anchor bars ロード失敗は fail-closed (RuntimeError) で run 中断 (cross-pair 検証が目的のため部分実行は無意味)。

### Codex Round 2 [Warning] 反映 (実装で対応)
1. **cross_pair_runtime_mode 細分化** (観測性): `enable=False → "skipped_disabled"` / `enable=True かつ target not in ANCHOR_PAIRS → "skipped_target_not_configured"` / `cp_inputs is not None → "enabled"`。summary/log で「enable したが未設定で skip」を識別可能に。
2. **_load_holdout_only の coverage fail-closed**: non-empty だけでなく、target と同じ `[dataset.end, dataset.end + holdout_days)` 窓で先頭・末尾・単調性・重複なし・span カバレッジを検証。短い anchor holdout で ii_lite_pass が誤って bool 化し観測解釈が壊れるのを防ぐ。

## Codex design-review: APPROVED (Round 2)
