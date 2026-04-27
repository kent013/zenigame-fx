入力には 2 件のレビュー対象が混在しているため、別件として分けてレビューします。Round 1 は C9 に従い、まず反証可能性を優先して見ています。

**レビュー 1**
対象: `composite per-bar 計算の Numba JIT 化`

**本レビューの前提**
- `verified`: profile 抜粋上、`evaluate_stage_a` 16 回に対して [`run_backtest`](#/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py) 16 回、`on_bar` 229,616 回、1 backtest あたり 14,351 bars という観測は成立している。
- `verified`: [`strategy.py`](#/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py) 抜粋の prepared path は、per-bar に clause ごとの `dict` を再構築し、その後 [`compute_composite`](#/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py) と観測用 `compute_clause_score` を別々に呼んでいる。
- `verified`: [`composite.py`](#/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py) の pure Python 実装は clause/signal を順方向に畳み込み、空 clause や長さ不一致では `ValueError` を送出する。
- `verified`: `default.yaml` 抜粋では現行 default は `population_size=40`, `generations=15`, `stage_a.window_days=60`, `stage_b.window_months=18`, `stage_c.holdout_days=60`。
- `unverified`: profile 実行時の Stage A が「14 日 dataset 全体をそのまま backtest」していたかの厳密な経路。観測値は強く示唆するが、`stage_gate.py` 実装は未提示。
- `unverified`: 実運用の Python / NumPy / Numba 組み合わせ、worker start method、JIT cache 競合挙動。
- `unverified`: genome あたりの directional / gate signal 数の上限、duplicate signal の実分布、worst-case メモリ。

全体判定: `CHANGES_REQUESTED`

**Fact**
- profile から言えるのは「prepared path の Python オーバーヘッドが十分大きい」「composite 経路は on_bar の有力候補」までで、`0.69s` 差分の全量が dict/hashing だとはまだ断定できない。
- 設計文は「bit-identical を保証」と「`np.allclose(atol=1e-6)` で検証」を同時に置いており、数値契約が内部で矛盾している。
- 提案メモリ見積りは `dir_value_arrs` のみで、`gate_value_arrs`、duplicate signal の複製、2D stack 化の一時/常駐コスト、6 worker 同時実行を含んでいない。

**Interpretation**
- 方向性自体は妥当だが、現状のままでは「期待効果」と「不変性保証」を言い切りすぎている。
- block しているのは方針ではなく、前提検証と受け入れ基準の精度不足。

1. 使命との整合性: `[Suggestion]` 速度改善として使命整合はある。これは live criteria の数値を触らない改善であり方向は問題ない。
2. 禁止事項違反: `[Suggestion]` 明示的な禁止事項違反は見当たらない。ただし「bit-identical 保証」を前提に pass 不変まで言い切ると、安全性主張だけが先行する。
3. 実現可能性: `[Critical]` Numba 導入そのものは可能性が高いが、環境互換と worker 下の cold/warm 差が未検証。修正提案: 導入前提を「対応 Python/NumPy/Numba 組み合わせを CI で固定し、`--max-workers 1/6` の cold/warm 実測を追加」に落とす。
4. 期待効果の妥当性: `[Critical]` `bars_scale_a = 60/14 = 4.29` は「calendar day 比」であり、実際に効くのは `bar count 比`。14,351 bars が観測できている以上、外挿は `target_stage_a_bars / 14,351` に置き換えるべき。修正提案: 60 日実 bars を 1 回実測し、その比で再計算する。
5. リスク: `[Critical]` `fastmath=False` は pure Python との bit-identical を保証しない。設計文の「保証」は下げるべき。修正提案: 契約を「loop order を維持した float64 実装で、主要実数値は tolerance 比較、pass/count 等の離散値は exact 比較」に分離する。
6. スコープの適切さ: `[Suggestion]` broker/mock や indicator 最適化を外した点は妥当。加えて feature flag か fallback switch を残すと切り戻しが容易になる。
7. メモリ制約: `[Critical]` 現見積りは過少。特に 2D `value_arrs` への stack は、現行 `arrays` cache が持つ duplicate 共有を壊す可能性がある。修正提案: `flat weight array + signal index indirection` にして、値配列自体は unique signal 単位で保持する案を比較対象に入れる。
8. 前提検証: `[Critical]` 「profile の Stage A は 14 日で走っていた」は強く示唆されるが未証明。修正提案: `evaluate_stage_a` が `run_backtest` に渡す bars 長を 1 回ログ/テストで固定化し、前提 verified 化してから外挿を書く。
9. Design-first: `[Warning]` reference 実装と hot path は読めているが、Stage B/C 線形効果の主張は広すぎる。修正提案: 「同じ `on_bar` 成分には効くが、total runtime speedup は stage ごとに再計測」と書き換える。

追加の個別論点への回答:
- 論点 1: `4.29x` は「たぶん近い」が、現時点では `bar count 比` に直すべき。
- 論点 2: 差分 `~0.69s` を dict allocation と断定するのは不可。`math.isfinite`, `float()`, list append, set add, loop 制御も含む。
- 論点 3: hidden cost は実在しうる。特に per-worker 初回 call と cache reuse の実測が必要。
- 論点 4: `fastmath=False` だけで完全一致保証は不可。ここは設計文の修正が必要。
- 論点 5: T037 の semantics 再現は可能だが、`NaN/inf/-0.0/zero-weight` を含む専用同値性テストが必要。
- 論点 6: Stage B/C を `INCONCLUSIVE` とした姿勢は妥当。ただし「線形に効く」は component-level に限定すべき。
- 論点 7: メモリ見積りは incomplete。worst-case signal 数と duplicate 率を入れた再見積りが必要。

**レビュー 2**
対象: `backtest per-bar info ログの throttle（DEBUG 降格 + 集計サマリ化）`

**本レビューの前提**
- `verified`: [`engine.py`](#/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py) 抜粋には `backtest.session_close.drop_pending` と `backtest.session_close.drop_open_from_strategy` の per-bar `logger.info` がある。
- `verified`: [`mock.py`](#/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py) 抜粋には `broker.drop_pending_open` の `logger.info` がある。
- `verified`: `backtest.finished` は backtest 完了時 1 回の info ログとして存在する。
- `verified`: 添付ログ観測では per-bar info が大量に出ている。
- `unverified`: 既存 consumer が `backtest.finished` の追加 fields を完全に無視できること。
- `unverified`: 本番 wall-clock への改善幅。
- `unverified`: 運用者が DEBUG 切替手順を既に共有していること。

全体判定: `APPROVED`

**Fact**
- 提案は observability の粒度調整であり、売買ロジックや数値計算そのものには触れていない。
- 集計カウンタは `run_backtest` の local state であり、multiprocessing 下でも共有副作用を持たない。
- wall-clock 改善は plausible だが、提示情報だけでは定量化できない。

**Interpretation**
- 反証を探しても、現時点では blocking defect は見当たらない。
- ただし「性能改善」を前面に出すより、「INFO ノイズ削減とサマリ維持」を主目的として扱うのが正確。

1. 使命との整合性: `[Suggestion]` 本番 RUN の可観測性改善として整合している。戦略ロジックをいじらない点も良い。
2. 禁止事項違反: `[Suggestion]` 数値操作・評価期間操作・見せ方の偽装には当たらない。
3. 実現可能性: `[Suggestion]` 実装は局所的で、失敗モードも限定的。
4. 期待効果の妥当性: `[Warning]` wall-clock 改善は `INCONCLUSIVE` のままでよい。修正提案: 合格基準はまず「INFO 行数削減」とし、速度は before/after 実測の参考指標に下げる。
5. リスク: `[Warning]` DEBUG 降格により運用者が bar 単位の時系列を即座に見失う可能性がある。修正提案: `backtest.finished` に count だけでなく、必要なら `first_drop_open_bar_time` のような最小限の補助 field を追加するか、運用手順に DEBUG 切替方法を明記する。
6. スコープの適切さ: `[Suggestion]` structlog 全体の再設計まで広げていない点は適切。
7. メモリ制約: `[Suggestion]` 追加カウンタ 2 個で実質リスクなし。
8. 前提検証: `[Warning]` 「既存 consumer は追加 fields を ignore できる」は未検証。修正提案: report/archive 系の consumer に対して 1 本でも回帰テストを置くか、少なくとも manual check 項目に追加する。
9. Design-first: `[Suggestion]` 提示された code excerpt と runtime observation に基づいており、設計先行として十分。

追加の個別論点への回答:
- 検証ポイント 1: `INCONCLUSIVE` のままでよい。ここを無理に性能改善と断定しない方が健全。
- 検証ポイント 2: デバッグ性低下は warning だが、DEBUG 切替手順か補助 field を 1 つ足せば十分吸収可能。
- 検証ポイント 3: local counter なので multiprocessing 副作用は実質ない。
- 検証ポイント 4: `backtest.finished` schema 拡張の consumer 影響だけは未検証で、ここが唯一の要確認点。

要約すると、Numba JIT 化案は方向は良いものの、外挿・数値契約・メモリモデルの 3 点を詰め直すまで `CHANGES_REQUESTED`、ログ throttle 案は consumer 互換だけ確認すれば `APPROVED` です。