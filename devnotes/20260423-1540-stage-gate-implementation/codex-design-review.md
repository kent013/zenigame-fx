**前提（C4）**
- 本レビューは、提示された `detailed-design.md` の本文のみを対象に実施しました（ご指定どおりコマンド実行なし）。
- 既存コード実体（`engine/metrics/mock/strategy/ga.complexity`）との実シグネチャ整合は未検証のため、該当箇所は `INCONCLUSIVE` を明示します。

**主要指摘（Falsification-first, Fact / Interpretation 分離）**
1. Fact: Stage C の `new_max = backtest_config.max_spread_bps * Decimal(str(...))` は、`max_spread_bps` が `float` の場合 `TypeError` になり得ます。  
   Interpretation: 実装時にランタイム落ちする穴です。  
   修正: `base = Decimal(str(backtest_config.max_spread_bps))` に正規化してから乗算し、`BacktestConfig` の型に合わせて戻す変換関数を明示してください。

2. Fact: Stage A 判定順が `sharpe_raw is None` → `trade_count < 1` です。  
   Interpretation: no-trade ケースで `metric_unavailable` が先に立ち、`no_trades` が出ない可能性があります（テスト意図とも衝突）。  
   修正: `trade_count < 1` を先に判定するか、優先順位規則を設計に明記してください。

3. Fact: Stage C reason code が `spread_stress.total_pnl<0` / `spread_stress.sharpe<0` になっている一方、判定は `spread_stress_min_*` を使っています。  
   Interpretation: 設定値が 0 以外になったとき reason が事実とズレます。  
   修正: canonical code を `<min` 形式へ統一してください。

4. Fact: `StageGateConfig` は frozen ですが `live_criteria` を `dict` で保持しており、後から可変です。必須キー検証もありません。  
   Interpretation: 実行時に閾値欠落/改変で壊れる可能性があります。  
   修正: `MappingProxyType` 化＋必須キー (`sharpe_min` 等) の `__post_init__` 検証を追加してください。

5. Fact: `make_wf_folds` の docstring は「bars が空なら ValueError」と読める一方、実装仕様とテストは `[]` を返す前提です。  
   Interpretation: 契約不一致です。  
   修正: docstring を `empty -> []` に統一してください。加えて embargo=0 テスト記述の `train_end+1 = test_start` はオフバイワンで、`test_start == train_end` が正です。

6. Fact: `_slice_backtest_config` は `end=sub_bars[-1].bar_time` を使いますが、engine の end 包含/非包含仕様が設計に未定義です。  
   Interpretation: 最終バー欠落の潜在リスクがあります。  
   修正: engine の時刻境界仕様を設計に明記し、必要なら `end` を1バー先へ寄せる等の規約を固定してください。

7. Fact: `cross_pair_inputs: Mapping[str, object]` を直接キーアクセスしています。  
   Interpretation: 型安全が弱く、KeyError/型不整合が実行時化します。  
   修正: `TypedDict`（`target_pair`, `pair_bars_map`, `meta_map`）を導入し、実行時バリデーションも入れてください。

8. Fact: Stage B で fold unavailable は件数記録のみで reason code に反映されません。  
   Interpretation: 失敗原因の監査性が弱いです。  
   修正: `oos_metric_unavailable`（少なくとも `n_fold_unavailable == n_fold` 時）を追加推奨。

**重点確認事項 1-9 の判定**
1. concept→detail 落とし込み: 概ね良好。ただし reason 語彙に `<0` 問題あり（要修正）。  
2. `__post_init__` frozen + defensive copy: 構文自体は妥当。ただし不変性は不十分（要修正）。  
3. `make_wf_folds` 境界: ロジックは概ね妥当。doc/test表現に不整合あり（要修正）。  
4. Stage B `_slice_backtest_config`: 必要性はあり得るが engine 境界仕様未確定で `INCONCLUSIVE`。  
5. Stage C `Decimal × float`: リスクあり（要修正）。  
6. import 循環: 実コード未読のため `INCONCLUSIVE`。  
7. fixture の intraday 制約: 方針は妥当。  
8. `src/ga/complexity.py` API 整合: 手順記載はあるが実体未検証で `INCONCLUSIVE`。  
9. `cross_pair_inputs` 型: TypedDict 化を推奨（要修正）。

**判定**
- **REQUEST_CHANGES**  
- 根本方針の破綻は見えませんが、上記の型安全・契約整合・reason語彙のズレは実装前に潰すべきです。