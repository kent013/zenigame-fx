**前提検証 (C4)**
- **Fact**: `cash/positions` の明示更新経路に `_invalidate` を入れる設計は妥当です（`deposit`, `apply_bar_holding_cost`, `_open_position`, `_close_one`）。
- **Fact**: `bar is self._cached_bar` は `self._cached_snapshot is not None` との複合条件なので `None` 比較の誤判定は起きにくいです。
- **Fact**: ルックアヘッドバイアスは本変更範囲（broker snapshot cache）では実質 `N/A` です。
- **Interpretation**: ただし `Position` が mutable なまま参照共有を維持する設計は、cache 一貫性の将来リスクを固定化します。

**指摘（Falsification-first, 重大度順）**
1. [Critical] `Position` 参照共有 + cache により stale snapshot が発生しうる  
該当: [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py), [orders.py](/Users/ishitoya/repository/zenigame-fx/src/broker/orders.py), [test_mock_snapshot_invariance.py](/Users/ishitoya/repository/zenigame-fx/tests/broker/test_mock_snapshot_invariance.py)  
- `snapshot.positions=tuple(self._positions.values())` は mutable `Position` を保持します。  
- その後に `Position` が in-place 変更されると、`positions` は更新される一方で `equity/margin_used` は cache 値のままになり不整合化します。  
- 修正案: `Position` を `frozen=True` にするか、`snapshot.positions` を不変コピー（値オブジェクト）に変更し、`open_positions` も防御的コピーにする。少なくとも「外部から Position mutate 不可」をコードで強制してください。

2. [Warning] 施策3のテストが危険な契約を固定化している  
該当: [test_mock_snapshot_invariance.py](/Users/ishitoya/repository/zenigame-fx/tests/broker/test_mock_snapshot_invariance.py)  
- `sp is bp` を要求すると、将来の安全な防御コピー/不変化リファクタを阻害します。  
- 修正案: identity ではなく「値一致」と「mutation 不可（または mutation 時に cache 無効化される）」を検証するテストに差し替える。

3. [Warning] cache 書き込みの原子性が弱い（例外時の整合性）  
該当: [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py)  
- 2変数 (`_cached_snapshot`, `_cached_bar`) を分離更新しており、極小確率でも中間状態を作りえます。  
- 修正案: `self._snapshot_cache: tuple[PriceBar, PortfolioSnapshot] | None` の単一スロットにし、1回代入で更新・`None` で invalidate に統一。

4. [Warning] 施策2の網羅性不足（制約観点）  
該当: [test_mock_snapshot_cache.py](/Users/ishitoya/repository/zenigame-fx/tests/broker/test_mock_snapshot_cache.py)  
- 長短両方向（long/short）の同値性検証が不足。  
- 修正案: `open_long/open_short` を `parametrize` し、`cash/equity/margin_used/margin_level_pct` の一致を両方向で確認。

5. [Suggestion] invalidate 漏れ再発防止のため更新経路を集約  
該当: [mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py)  
- 将来変更で呼び忘れが起きやすいです。  
- 提案: `_mutate_cash(...)`, `_add_position(...)`, `_remove_position(...)` を作り invalidate を内部集中化。

**施策ごとの判定**
1. MockBroker per-bar cache 追加: **REQUEST_CHANGES**  
2. cache invariance/invalidation テスト: **REQUEST_CHANGES**  
3. runtime identity invariance テスト: **REQUEST_CHANGES**  
4. selection outcome invariance テスト: **INCONCLUSIVE**（実装詳細が未確定）

**全体判定**
- **CHANGES_REQUESTED**

**C3/C7（Collider bias / Sample size）**
- 本設計レビュー範囲で相関・予測の因果主張は見当たらず `N/A`。  
- Phase 7 の性能評価は `n` を増やして分散確認しない限り、改善率判定は **INCONCLUSIVE** 扱いが妥当です。