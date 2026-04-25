# 詳細設計: EconomicEventSnapshot as_of 厳密化

親: `conceptual-design.md`

## 使命・制約（絶対遵守）

- 使命: M4/P10 を production で有効化する前に、未来 schedule 漏洩の可能性をゼロにする
- 制約: 既存 no-op 経路（snapshot 不在時に gate=1.0）は壊さない。strict 化は production toggle 経由
- AGENTS.md C2 遵守: 現状 leak は "起きていない"（no-op）。本 TODO は技術債務整備

## 失敗モード / 因果経路 / 反証 / 成功条件

| 項目 | 内容 |
|------|------|
| failure_mode | M4/P10 が as_of=+∞ で有効化され、未来の経済イベント schedule を bar_time 時点の特徴量に混入させる |
| causal_path | loader 不在 → MVP 仮定（全量 as_of=+∞）→ event_time > bar_time のイベントが gate に影響 → fitness が in-sample で過大評価 |
| falsification | as_of=bar_time 厳密モードと as_of=+∞ MVP モードで M4 出力を比較し、有意差が無ければ leakage 無し（指標性が低いため棄却・別 TODO） |
| success_criterion | (1) M4/P10 単体に対し causality 契約テスト pass、(2) production toggle で strict モード強制可能、(3) backtest run で M4/P10 が有効化された個体の Stage A→B→C 通過率が as_of=+∞ 比で 1.0× を有意に超えない |

## 変更箇所（実装は別フェーズ）

| # | ファイル | 変更内容 | 概要 |
|---|----------|---------|------|
| 1 | `src/alpha_factory/primitives/_base.py` | `EconomicEventSnapshot` に `as_of_strict: bool` フィールド追加、`__post_init__` で as_of tz-aware 強制 | snapshot 自体に厳密性を持たせる |
| 2 | `src/alpha_factory/primitives/_base.py` | `EvaluationContext` に `as_of_per_bar: bool` 追加（compute が bar_time から as_of を導出する場合の許可フラグ） | 二段ガードのスイッチ |
| 3 | `src/alpha_factory/primitives/modulator_generic.py` (M4) | as_of_strict=True かつ `event.event_time > ctx.bars[i].bar_time` のイベントは bar i では除外（既存の `as_of` cap に加えて per-bar gate） | 真の causality 強制 |
| 4 | `src/alpha_factory/primitives/pair_specific.py` (P10) | M4 と同様の per-bar gate | pair_specific 経路にも適用 |
| 5 | `src/alpha_factory/primitives/evaluator.py` | `RegistryEvaluator.__init__` に `event_snapshot_strict: bool` 追加。strict_aux_required と直交 | 起動時の運用切替 |
| 6 | `config/alpha_factory/default.yaml` | `evaluator.event_snapshot_strict: true`（production default）追加 | SSoT |
| 7 | (新規) `src/alpha_factory/event_loader.py` | EconomicCalendar を datetime 範囲で読み込み、`EconomicEventSnapshot` を生成する loader | loader 経路の最低骨格 |
| 8 | `tests/alpha_factory/primitives/test_modulator_generic.py` | M4 causality test（既知 schedule に対し prefix 切り詰め同型検証） | 形式保証 |
| 9 | `tests/alpha_factory/primitives/test_pair_specific.py` | P10 causality test | 同上 |

## アルゴリズム（M4 per-bar gate）

```
for i in range(length):
    bar_t = ctx.bars[i].bar_time.timestamp()
    cap_t = min(as_of_ts, bar_t) if event_snapshot.as_of_strict else as_of_ts
    relevant = bisect-filter events by event_time <= cap_t
    nearest = min(|event_time - bar_t| for event_time in relevant)
    out[i] = 1 - sigmoid((window_min - nearest_min) / (scale_min + eps))
```

bisect 化により O(N log E)。E ~ 1k〜10k で実用十分。

## 波及変更

- AGENTS.md: なし
- skill: なし（loader が完成したら zenigame-fx-run-alpha-factory に DI 経路追加）
- docs: `docs/alpha_factory/primitives.md` の M4/P10 節に causality contract を追記
- config: `default.yaml` に `evaluator.event_snapshot_strict` (default true)

## ルックアヘッドバイアスチェック

- per-bar gate により `event_time <= bar_time[i]` のみ参照 → look-ahead 完全排除
- causality test (#8, #9) で形式検証
- as_of_strict=False の MVP 経路は backtest 過去互換のため温存するが、production
  config では強制 true

## パフォーマンスチェック

- 現状: `compute_all_bars` 内で全 bar に対し event filter loop（O(N×E)）
- 改善後: events を一度ソート → bisect で各 bar O(log E) → O(N log E)
- 60 営業日 × 1440 分/日 ≒ 86k bars × log(10k) ≒ 1.2M ops。負荷無視可

## テスト計画

- M4 causality: 既知 calendar に対し `M4(bars[:i+1], snapshot_at_i)[i] == M4(bars, snapshot)[i]`
- P10 causality: 同上
- 既存 no-op 経路: snapshot=None で warning 出ることを既存テストで保持
- production toggle: `evaluator.event_snapshot_strict=true` で snapshot=None なら起動時 RuntimeError

## リスク

- **M4/P10 を strict 化した瞬間に in-sample fitness が悪化**: leak が実際にあった場合に
  起こりうる挙動。本 TODO の成功指標と一致するため許容
- **loader 整備の依存**: 別 TODO（経済イベント data ingest）と連動。本 TODO 単体では
  `_base.py` / 各 primitive / evaluator の strict 経路だけ整備し、loader は scaffold のみ

## Run 評価（後続）

実装後、A/B run（strict on/off）で M4/P10 個体の Stage A 通過率を比較し、有意差が
あれば leak 量化、無ければ M4/P10 の指標性低を別 TODO 化。

## Codex レビュー

別フェーズで実施（本 TODO 登録時点では設計 round-1 のみ）。
