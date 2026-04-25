# 概念設計: broker-snapshot-caching

## 前提表（Verified / Unverified）— C4 準拠

| # | 前提 | 状態 | 根拠 |
|---|---|---|---|
| P1 | `BrokerGateway` は Protocol で、MockBroker が唯一の concrete 実装。OandaBroker / TachibanaBroker は future stub のみ | **Verified** | `src/broker/gateway.py:22` に「MockBroker と将来の OandaBroker / TachibanaBroker が共通に実装する抽象」、`src/broker/__init__.py` は MockBroker のみ export |
| P2 | `PortfolioSnapshot` は `@dataclass(frozen=True)` で immutable | **Verified** | `src/broker/orders.py:46-52` |
| P3 | `Position` は frozen ではない (`@dataclass`)。mutable | **Verified** | `src/broker/orders.py:20-29`（frozen なし） |
| P4 | MockBroker の Position は `_open_position` で生成後、mutation されない（close で `_positions.pop` で dict から削除されるだけ） | **To verify in detailed design** | 詳細設計段階で `_positions` 参照を grep し、Position フィールド書き込みが無いことを確認する |
| P5 | MockBroker 内で snapshot を参照する箇所は `force_close_if_margin_call` / `snapshot()` の 2 系統のみ | **To verify in detailed design** | `grep "_snapshot_at\|self.snapshot()\|broker.snapshot()" src/ tests/` を詳細設計で実施 |
| P6 | `docs/alpha_factory/` に MockBroker / snapshot に関する設計記述は無い（broker は domain detail として明示設計されていない） | **To verify in detailed design** | `docs/alpha_factory/` を ls 済み（runbook / stage-gates / clause-architecture 等があるが broker は無し）。詳細設計で `grep -r "snapshot\|MockBroker" docs/` を実施 |
| P7 | primitive / DslStrategy / run_backtest は snapshot を read-only で参照（書き換えない） | **To verify in detailed design** | `src/dsl/strategy.py:173-191` の snapshot.positions 参照は read-only。engine.py も read-only |
| P8 | 既存 broker tests は `tests/broker/` 以下に分割配置済み | **To verify in detailed design** | ls 確認のみ、内部 structure は詳細設計で確認 |
| P9 | cache key が snapshot 依存変数を十分に識別する（bar 同一時刻・異価格で stale を返さない、id 再利用で偽 hit を起こさない） | **Verified** | Round 2 Critical + Round 3 Critical 対応: cache key は `id(bar)` ではなく **object reference を直接保持** (`self._cached_bar: PriceBar | None`) し、`bar is self._cached_bar` で判定。これにより (a) 同一時刻・異価格 (異なる object) は miss、(b) `id()` 再利用問題は起きない（strong reference を保持しているため cache valid な間は object が生存） |
| P10 | engine.run_backtest は bar loop 内で同一 PriceBar オブジェクトを broker に渡す（`force_close_if_margin_call(bar)` と `broker.mark_to_market(bar)` と `broker.snapshot()` 経由の `self._last_bar` が同一 reference） | **Verified** | `src/backtest/engine.py:115-167` の bar loop は local 変数 `bar` を各呼び出しに渡す。`snapshot()` は `self._last_bar`（前回 `mark_to_market(bar)` で set）を使う。同一 iteration 内で 3 経路すべて同一 reference |

### Design-first 証跡（C1）

- **docs 参照済み**: `docs/alpha_factory/` 直下をリスト確認。対象領域（MockBroker / snapshot）の設計ドキュメントは無く、broker 層は implementation-detail 扱い。`runbook.md` / `stage-gates.md` / `primitives.md` 等、関連ドキュメントは別領域
- **devnotes 参照済み**: `devnotes/20260424-0517-mock-broker-multi-currency/` は Phase 4 の multi-currency 拡張（fx_rate_provider）予約設計、本 TODO と直交。その他 mock.py を変更した devnotes は `devnotes/20260425-0158-broker-snapshot-caching/`（本ディレクトリ）以前には無い
- **git log 参照**: mock.py の `_snapshot_at` 定義経路は T009 spread filter + T019 per-pair home mode の変更履歴。snapshot 計算ロジック自体は初期実装から不変
- **並行経路探索**: `grep -r "snapshot\|PortfolioSnapshot" src/` で `src/broker/mock.py` 以外の書き込み経路なし（consumer は strategy / engine のみ）

## 背景・課題

`zenigame-fx-profile-optimize` Cycle 1 のベースラインプロファイル（`profile_20260425_015349`、pop=8 gen=1 seed=42、14 日 EUR_JPY、全体 5.303 秒）で、O(N²) の primitive 評価問題を修正した直後の残存最大 hotspot を特定した。

### プロファイル証拠（Facts）

| 関数 | ncalls | tottime | cumtime |
|---|---|---|---|
| `MockBroker._snapshot_at` (`src/broker/mock.py:371`) | 774972 | 0.750s | 1.465s |
| `MockBroker.snapshot` (`src/broker/mock.py:276`) | 516654 | 0.093s | 1.069s |
| `builtins.sum` | 1550142 | 0.241s | 0.445s |
| `MockBroker._unrealized_pnl` (`src/broker/mock.py:366`) | 147540 | 0.042s | 0.080s |

### Interpretations

- `_snapshot_at` は 258318 bar 処理に対して `774972 = 3 calls/bar`
- 各 `_snapshot_at` 内で 2 つの `sum()`（unrealized + margin_used）が走り `1550142 = 2 × 774972` を説明する
- 全体の ~19.6% が snapshot 関連。本番外挿（pop=40 / gen=15 / 180 日窓、bars 89.9M / profile 258k = 348×）で **~350 秒/RUN** と推定
- **注意（C7）**: 本外挿は n=1 プロファイルからの線形換算。あくまで「このサンプルでの観察値をスケーリングした仮説値」であり、本番で同じ割合が成立するとは断定しない

## 改善アイデア

### Round 1 レビューを受けた scope 縮小

**初回案は per-bar snapshot cache + incremental margin の 2 段階だったが、Codex レビューで以下の懸念が指摘された**:

1. incremental margin は `sum(entry_margin)` の演算順序を変えるため Decimal bit-identical が崩れ得る（Critical）
2. 一度に 2 最適化を投入すると回帰時の切り分けが困難（Warning）
3. position partial close / margin の減算不変条件が未証明（Critical）

→ **本概念設計は per-bar snapshot cache のみ に縮小**。incremental margin / unrealized batching は **follow-up TODO** として分離し、本 TODO 完了・効果計測後に改めて設計する（shadow 値比較テストが前提）。

### per-bar snapshot cache（唯一の施策）

**本質**: `_snapshot_at(bar)` の結果は「同じ bar + 同じ positions 状態 + 同じ cash」で deterministic な純関数。既に計算した値を返すだけなら、**演算順序が一切変わらず bit-identical が構造的に保証される**。

**実装の骨子**:
- `self._cached_snapshot: PortfolioSnapshot | None = None`
- `self._cache_valid: bool = False`
- `self._cached_bar: PriceBar | None = None`  # **object reference を保持**（Round 3 Critical 対応: `id()` 再利用回避）
- `_snapshot_at(bar)` の最初で `cache_valid and bar is self._cached_bar` なら cache hit → cached snapshot を即 return
- cache miss なら既存ロジックで compute し、cache に書き込む（**ロジック本体は完全に不変**）
- 以下の trigger で `_invalidate()`:
  - `_open_position` 末尾
  - `_close_one` 末尾（successful close のみ）
  - `apply_bar_holding_cost` 末尾（cash 変化）
  - `deposit` 末尾（cash 変化）
  - `drop_pending_open` は snapshot に影響しない（pending は snapshot 計算に入らない）ため invalidate 不要

**cache key 設計 (Round 2 Critical + Round 3 Critical 対応)**:
- `bar.bar_time` でも `id(bar)` でもなく、**object reference そのもの** を保持（`self._cached_bar: PriceBar | None`）
- 判定は `bar is self._cached_bar`（Python identity 比較）
- **Round 3 Critical 対応**: `id(bar)` は object 解放後に再利用されうる。object reference を保持すれば cache valid な間は strong reference が object を生存させるため、id 再利用問題は根絶
- **Round 2 Critical 対応**: 同一 `bar_time` でも異なる object は miss（本設計は内容同値ではなく**参照同一性**で判定する。PriceBar が frozen であることと合わせて「同一 object = 同一内容」は保証されるが、逆向きの「同一内容 = 同一 object」は要求しない）
- engine loop は同一 iteration 内で 3 経路すべて同一 reference を渡すため（P10）、cache hit は確実に発生する
- 次 iteration で異なる bar object が渡された瞬間に `is` comparison が False になり cache miss

### PortfolioSnapshot 依存マトリクス（Round 1 Critical 対応）

| Snapshot フィールド | 依存ソース | 変化トリガー | cache invalidate 必要 |
|---|---|---|---|
| `cash` | `self._cash` | `deposit` / `apply_bar_holding_cost` / `_close_one`（realized PnL 加算） | **はい** |
| `equity` | `cash + Σ_unrealized_pnl` | 上記 cash 変化 + positions 変化 + **bar 進行**（exit_price が bar.bid.close / ask.close に依存） | **はい** |
| `margin_used` | `Σ p.entry_margin for p in positions` | positions 変化（open / close） | **はい** |
| `margin_level_pct` | `equity / margin_used × 100`（派生） | equity or margin_used 変化 | **はい**（equity 経由で自動） |
| `positions` | `tuple(self._positions.values())` | positions 変化 | **はい** |

**bar 進行の扱い**: cache key に `bar.bar_time` を含めるため、新しい bar で `_snapshot_at(new_bar)` が呼ばれた瞬間に cache miss となる。明示的 invalidate は不要。

**chain close の扱い（Round 1 Critical 対応）**: `force_close_if_margin_call` が同一 bar 内で `_close_all_internal` → `_close_one` × N を実行するシナリオでは、各 `_close_one` が `_invalidate()` を呼ぶため次回の snapshot は再計算される。これを検証する専用テスト `test_snapshot_invalidates_on_chained_close` を必須にする。

### Position mutability の扱い（Round 1 Warning 対応）

- `Position` は frozen でないため、**cache 返却時に positions を後から mutate されると stale になる**リスクが理論的に存在する
- **Facts**: 現行コード（HEAD）で Position フィールドを書き換える箇所は無い（grep で検証予定。P4）
- **mitigation**: 本 TODO では mutation は想定しないが、detailed design で「Position の不変性を invariant として明文化 + 将来の違反を検知する unit test（Position フィールド書き換え検出）」を追加する

### LiveBroker / PaperBroker 影響（Round 1 Warning 対応）

- **P1 Verified**: BrokerGateway Protocol の `snapshot()` シグネチャは不変（`PortfolioSnapshot` を返す契約）
- 本 TODO は **MockBroker の内部実装最適化のみ**。Protocol / 返却契約・意味論は不変
- 将来の OandaBroker / TachibanaBroker は自前の snapshot 戦略を持つ（API 直叩き等）。MockBroker 固有の cache 実装は他ブローカーに波及しない

## 期待効果（Round 1 Warning 対応：仮説レンジに格下げ）

### パフォーマンス仮説

| 指標 | 仮説レンジ | 根拠 | 確信度 |
|---|---|---|---|
| `_snapshot_at` cumtime 削減（単一プロファイル） | 60-75% | 3 calls/bar → 1 call/bar で 2/3 削減、ただし cache hit 判定オーバヘッド分を差し引き | 中 |
| RUN 全体時間削減（単一プロファイル） | 10-20% | `_snapshot_at` + `snapshot` + sum 合計 cumtime ~19.6% のうち 60-75% 削減 | 中 |
| 本番推定削減 | 120-220 秒/RUN | 上記の本番外挿（348× scale factor）。**C7: n=1 のため複数 seed/pair で検証予定** | 低 |
| Selection outcome invariance | 100% | 構造的に bit-identical（cache miss 時に既存ロジック実行、hit 時に同値返却） | **高** |

### 検証計画（Round 1 Warning 対応）

1. **selection invariance 検証**: 修正前後で同一 seed・同一 config・同一 window の GA RUN を実行し、`best_genome.fitness_pen` / Stage A/B/C pass rate が bit-identical であることを確認（自動テストに組み込み）
2. **複数シード/ペアでのパフォーマンス再計測**: `profile_optimize` Phase 7 で少なくとも 2 ペア（EUR_JPY / USD_JPY）× 2 seed で再プロファイルして平均改善率を取る
3. **単位時間指標**: RUN 全体 / 1 bar あたり / 1 genome あたりの 3 指標を並列で報告

### live_criteria への寄与

- 直接的ではなく **間接的**（壁時計時間短縮 → 同予算での探索量増加）
- 成功基準は **selection outcome 完全一致**を最優先、performance 改善は副次成功指標

## 実装方針（概要）

### 変更コンポーネント

1. `src/broker/mock.py::MockBroker`
   - `__init__`: `_cached_snapshot` / `_cache_valid` / `_cached_bar` 追加
   - `_snapshot_at(bar)`: cache hit path（早期 return）+ 既存 compute + cache 書き込み
   - `_invalidate()`: private helper（`_cache_valid = False` のみ）
   - `_open_position` / `_close_one` / `apply_bar_holding_cost` / `deposit` の末尾に `self._invalidate()` を追加
   - **既存の計算ロジック（sum, _unrealized_pnl, PortfolioSnapshot 生成）は完全に不変**

2. 新規 tests（必須）
   - `tests/broker/test_mock_snapshot_cache.py`（新規）
     - `test_snapshot_cache_hit_returns_identical_object`: 同一 bar で複数回呼んで identity（`is` 比較）で同じ PortfolioSnapshot が返る
     - `test_snapshot_cache_miss_on_new_bar`: 新しい bar で自動的に cache miss
     - `test_snapshot_invalidates_on_position_open`: `_open_position` 後に cache miss
     - `test_snapshot_invalidates_on_position_close`: `_close_one` 後に cache miss
     - `test_snapshot_invalidates_on_holding_cost`: `apply_bar_holding_cost` で cache miss
     - `test_snapshot_invalidates_on_deposit`: `deposit` で cache miss
     - `test_snapshot_invalidates_on_chained_close` (Round 1 Critical): `_close_all_internal` で複数 close した直後の snapshot が、毎回再計算された結果と一致
     - `test_snapshot_values_bit_identical_cache_vs_no_cache`: snapshot を 100 bar 分 record し、cache disable 状態（手動で `_cache_valid = False` 固定）と enable 状態で equity / margin_used / margin_level_pct / positions が完全一致
     - **`test_snapshot_duplicate_timestamp_different_prices` (Round 2 Critical)**: 同一 `bar_time` を持つ異なる `PriceBar` オブジェクトを連続で渡した際に cache miss が発生して異なる snapshot を返すこと（`bar is self._cached_bar` cache key の invariance）
     - **`test_snapshot_object_reference_identity` (Round 3 Critical)**: 同一 bar_time + 同一内容だが異なる object の PriceBar を渡して、cache miss が発生することを `is` 比較で確認（`id()` 再利用を模擬した test）
   - `tests/broker/test_mock_snapshot_invariance.py`（新規）
     - **Position mutation ガード**（P4 verification）: Position.entry_price / entry_margin / units を書き換えるコードを grep で検出しない static check（簡易 import-based check）
     - **ランタイム identity invariance (Round 2 Warning)**: `broker.snapshot().positions` が `broker._positions.values()` と参照同一（同じ Position オブジェクト）であることを `is` で検証。将来 Position の copy 化等の仕様変更を即座に検出

3. 既存テストの回帰確認
   - `tests/broker/` 全件
   - `tests/backtest/test_engine*.py`
   - `tests/alpha_factory/test_stage_gate.py`
   - `tests/dsl/`
   - **期待: 全件 PASS（挙動は構造的に不変）**

### スコープ外（follow-up TODO で扱う）

- `margin_used` incremental maintenance（shadow 値比較テスト必須）
- `_unrealized_pnl` の batching / Decimal 最適化
- `PortfolioSnapshot` の dataclass 設計変更
- engine.py の bar loop 構造変更
- OandaBroker / TachibanaBroker への同様最適化（そもそも実装されていない）

## 制約・前提

### FX 絶対制約（不変）
- **イントラデイ**: engine の session_close_utc_hours / EOD 強制クローズはいじらない（broker 側は無関係）
- **ロング・ショート両方向**: `_open_position` のロジックは変更しない（末尾に invalidate 追加のみ）
- **swap・spread 反映**: `apply_bar_holding_cost` / `_last_close_spread_bps` の挙動を変えない

### Stage A/B/C 通過判定の不変性（最優先成功基準）
- PortfolioSnapshot の数値は **bit-identical**（cache hit は同一オブジェクトを return、cache miss は既存ロジック）
- `_close_one` の realized PnL 計算を変えない
- **selection outcome invariance** を最優先指標とする（performance 改善は副次）

### メモリ制約
- 24GB × 6 worker、1 worker ~3GB
- cache サイズ: broker インスタンスあたり PortfolioSnapshot 1 個（~80 bytes Decimal 参照 + tuple）+ bar_time 1 個 + bool 1 個 ≈ **< 200 bytes**
- broker インスタンス数: 1 backtest につき 1（Stage A + Stage B fold + Stage C でそれぞれ新規）。並列 worker 上限 6 でも **追加メモリ < 2KB**
- メモリ面の懸念は事実上ゼロ

### Look-ahead bias
- 本変更は broker 層の最適化であり primitive / 指標計算ではない → 該当なし

## 成功基準（Round 1 Warning 対応：selection invariance を最優先に）

### 実装開始条件チェックリスト（Round 2/3 Warning 対応）

実装フェーズに入る前に、以下のすべてが **Verified** であること:

- [ ] P4 Verified: `grep -rn "\._positions\[" src/` で Position フィールド書き換えが無いことを確認
- [ ] P5 Verified: `grep -n "_snapshot_at\|self\.snapshot()" src/broker/mock.py` で内部 call site が `force_close_if_margin_call` と `snapshot()` のみであることを確認
- [ ] P6 Verified: `grep -rn "snapshot\|MockBroker" docs/` で MockBroker / snapshot に関する設計記述が無いことを確認
- [ ] P7 Verified: `src/dsl/strategy.py` / `src/backtest/engine.py` で snapshot.positions に対する書き込みが無いことを確認
- [ ] P8 Verified: `ls tests/broker/` で既存 test ファイル分割を確認
- [ ] P9 Verified: `src/domain/price.py` で `PriceBar` が frozen dataclass であることを確認
- [ ] P10 Verified: `src/backtest/engine.py:115-167` の bar loop で同一 PriceBar reference が渡されることを確認

#### invalidate 網羅性チェック（Round 3 Warning 対応）

MockBroker 内で `self._cash` / `self._positions` を変更する全経路を列挙し、**各経路の末尾に `self._invalidate()` が配置される** ことを verify:

- [ ] **`self._cash` 変更経路**: `grep -n "self\._cash" src/broker/mock.py` で全代入・加減算を列挙。想定: `__init__`（初期化, invalidate 不要）/ `deposit`（+=） / `apply_bar_holding_cost`（-=） / `_close_one`（+= raw_pnl）
- [ ] **`self._positions` 変更経路**: `grep -n "self\._positions\[" src/broker/mock.py` で代入・`pop`・dict 操作を列挙。想定: `_open_position`（追加）/ `_close_one`（pop で削除）/ `_close_all_internal`（_close_one ループ経由、個別 invalidate は `_close_one` が担う）
- [ ] 各経路の末尾に `self._invalidate()` が配置されていることを詳細設計のコードで確認
- [ ] 該当経路外での cash / positions 書き込みが無いことを `grep` で 2 重チェック（tests/ は除外）

### 合否判定基準

1. **[最優先] Selection outcome invariance**: 同一 seed / config / window の GA RUN で `best_genome.name` / `best_genome.fitness_pen` / `Stage A/B/C pass counts` が **bit-identical**
2. `tests/broker/` / `tests/backtest/` / `tests/alpha_factory/` / `tests/dsl/` が全合格（現状 680+ cases、新規 test 9 件追加で ~689+）
3. 新規 test 全合格（cache hit/miss invariance、chain close、bit-identical snapshot、duplicate timestamp、runtime identity）
4. Profile 再計測で `_snapshot_at` cumtime が **60% 以上削減**（target）
5. RUN 全体時間が **10% 以上短縮**（単一プロファイル、target）
6. 複数 seed/pair での performance 再検証（Phase 7 責務）

### INCONCLUSIVE 判定ルール（Round 2 Suggestion 対応、C8 準拠）

以下の状況では **INCONCLUSIVE** を正当な結論として許容する（失敗扱いしない）:

- Selection invariance が満たされた上で、performance 改善が target 未達 + 再測定 n<3 の場合 → 結論 **INCONCLUSIVE**、Phase 7 で n を増やして再判定
- Selection invariance が壊れた場合は **無条件 FAIL**（revert 対象）
- Selection invariance OK + performance 改善が target 達成 → **PASS**

## 参考文献・引用

- López de Prado, M. (2018). _Advances in Financial Machine Learning_, Ch.12 (Backtesting Overfitting) — backtest 計算コストと過適合のトレードオフ
- Brooks, F. P. (1995). _The Mythical Man-Month_ — 段階的な最適化投入の重要性（一度に複数変更しない）
- Knuth, D. E. (1974). "Structured Programming with go to Statements" — "premature optimization is the root of all evil" の原典。本 TODO は cProfile 由来の measured optimization であり、この原則には違反しない

## Round 1 Codex レビュー対応マップ

| Round 1 指摘 | 分類 | 対応 |
|---|---|---|
| C1: invalidation 契約の網羅性 | Critical | PortfolioSnapshot 依存マトリクスを追加、invalidate トリガー 5 点を明示 |
| C2: chained close で stale snapshot | Critical | 専用 test `test_snapshot_invalidates_on_chained_close` を必須化 |
| C3: Decimal order-of-operations 不変性 | Critical | **per-bar cache のみに scope 縮小**（cache hit は同一オブジェクト return で演算順序変化なし） |
| C4: entry_margin 減算不変条件 | Critical | **incremental margin をスコープ外に退避**（本 TODO では扱わない） |
| C5: C4 前提 verified ラベル | Critical | 前提表を追加（P1-P8、Verified / To verify in detailed design） |
| C6: C1 design-first 証跡 | Critical | docs 参照済・devnotes 参照済・git log 参照済・並行経路探索結果を明記 |
| W1: 使命寄与が間接 | Warning | Selection invariance を最優先成功基準に格上げ、performance は副次に降格 |
| W2: Position mutable 参照 | Warning | P3/P4 で明示、mutation ガード test を追加 |
| W3: 70-80% 主張強度 | Warning | 仮説レンジ 60-75% (_snapshot_at) / 10-20% (RUN) に格下げ、n=1 警告を明記 |
| W4: LiveBroker 影響調査 | Warning | P1 Verified で MockBroker のみ concrete 実装と明示、Protocol 契約不変 |
| W5: 同時 2 最適化の切り分け困難 | Warning | **per-bar cache のみに縮小**、incremental margin は follow-up TODO |
| W6: effect 指標の分解 | Suggestion | RUN 全体 / 1 bar / 1 genome の 3 指標並列報告を検証計画に明記 |
