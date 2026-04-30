**前提（C4、verified / unverified）**
- `verified`: `on_bar` がホットパスであること（`229,616` call / cumtime `1.165s`）は提示 profile と一致。[strategy.py:259](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py:259)
- `verified`: 現行 `fill_pending`/`_open_position` に equity 非正・非有限の open 抑止がない。[mock.py:175](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py:175) [mock.py:312](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py:312)
- `verified`: `compute_composite` は clause 空で `ValueError` 契約を持つ。[composite.py:74](/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py:74)
- `unverified`: Stage A が profile 時に「14日全体」をそのまま評価窓として使っているか（実行時 window 切り詰め実装の確証は未提示）。
- `unverified`: 既存コードに `except ValueError` の広域 catcher がどれだけあるか（`InsufficientEquityError(ValueError)` の副作用評価に必要）。
- `unverified`: 本番 worker 起動方式（fork/spawn）と Numba cache 競合実態。

**C9 反証結果（先に反証）**
- 「`bars_scale_a=4.29` は妥当」を反証可能。暦日比でなく実 bars 比で再算定すべき。
- 「`fastmath=False` なら bit-identical」を反証可能。`allclose` は bit-identical の証明にならない。
- 「on_bar 60-75%短縮→Stage A全体 25-35%短縮」は算術的に上振れ（前提次第で 16-25%程度）。

**主要指摘（重い順）**
1. [Critical] 外挿倍率が暦日比固定で、評価窓の実 bars を反映していません。`60/14` ではなく `stage_a_actual_bars_prod / 14351` を使うべきです。  
修正提案: Stage A 実行時の `bars=len(bars_list)` を 60d データで1回採取し、倍率を置換。

2. [Critical] 効果見積りが一部不整合です。`on_bar` が全体22%なら 75%削減でも全体寄与は約16.5%が上限。  
修正提案: 分母を「全体」「run_backtest」「stage_a path」で分けて3系統で再提示。

3. [Critical] 「bit-identical（atol=1e-6）」は定義矛盾です。  
修正提案: 要件を `bitwise_equal` と `allclose` に分離。`active_clause_indices` は厳密一致で検証。

4. [Critical] `dir_value_arrs[total_dir, n_bars]` 方式は、同一 signal の clause 間重複を複製しメモリ見積りを過小化するリスクがあります。  
修正提案: `unique_signal_matrix + index indirection` 方式で共有化。

5. [Critical] `InsufficientEquityError(ValueError)` は既存の広域 `except ValueError` に誤捕捉され得ます。  
修正提案: `Exception` 直系の domain 例外へ変更し、`fill_pending` でのみ明示捕捉。

6. [Warning] L1 を spread filter 後に置く設計だと、drop 件数の意味が「negative equity 起因のみ」に限定されます。  
修正提案: runbook とテストに counter 定義（集計母集団）を明記。

7. [Warning] テスト計画に `close_all` 非ドロップ検証、`spread reject + negative equity` 同時発生時の件数整合検証が不足。  
修正提案: 2ケース追加。

---

**論点1-7 判定（Numba設計）**
1. 外挿 bars_scale 妥当性: `REQUEST_CHANGES`  
2. `on_bar` 差分の原因推定: `INCONCLUSIVE`（方向は妥当、定量が不足）  
3. Numba 隠れコスト: `REQUEST_CHANGES`  
4. 数値同値性主張: `REQUEST_CHANGES`  
5. T037 不変性: `REQUEST_CHANGES`  
6. Stage B/C 線形波及主張: `INCONCLUSIVE`  
7. メモリ概算: `REQUEST_CHANGES`

**施策1-4 判定（negative equity 詳細設計）**
1. 多層防御: `REQUEST_CHANGES`（例外型とテスト補強が必要）  
2. engine 集計: `APPROVE`  
3. テスト整備: `REQUEST_CHANGES`（2ケース追加推奨）  
4. OANDA spec 文書化: `APPROVE`

**全体判定**
- `REQUEST_CHANGES`  
設計方針は妥当ですが、外挿の根拠・数値同値性定義・例外契約・メモリ見積りの4点を固めないと、実装後の検証で再差し戻しになる可能性が高いです。

**Fact / Interpretation 分離**
- `Fact`: 現行 hot path は `on_bar`、現行 broker は negative/NaN equity open を抑止していない、Stage B/C 実測は未取得。  
- `Interpretation`: Numba fused kernel と L1+L2 防御は有効な方向だが、現状の見積りと契約定義は過信が混ざっており、事前に検証条件を再定義すべき。