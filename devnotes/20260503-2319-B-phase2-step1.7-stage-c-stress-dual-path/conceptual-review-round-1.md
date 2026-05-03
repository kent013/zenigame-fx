**全体判定**

**CHANGES_REQUESTED**

**前提検証 (C4)**

- Verified:
  現行 `Stage C stress` の legacy 判定は `evaluate_stage_c` 内で `stress_payload` と `reasons` を更新し、`max_spread_bps is None` と stress 例外時は `spread_stress_skipped` に落ちます。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1385) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1442)
- Verified:
  canonical helper は `live_criteria` と `window_days` から threshold を組み、`bars` / `trades` / `equity_curve` を入力にします。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L68) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L112)
- Verified:
  dual-path log helper は `legacy.sharpe` を出し、`pnl_diff` / `trade_count_diff` は「同一 stage 内の legacy vs canonical 差分」です。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L170) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L232) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L247)
- Unverified:
  `C_stress` を `fold_index=None` で SSOT 上正式に扱うこと。現行 helper docstring には `C_stress` がまだ入っていません。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L181)

**1. 使命との整合性**

- [Critical]
  `C_stress` の dual-path を「step 2 判定切替の calibration 充足に近づく観測」と置いている点は、現行 helper 契約とズレています。  
  Fact: canonical helper は `live_criteria` ベースの threshold を使います。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L68)  
  Fact: 現行 stress hard gate は `spread_stress_min_total_pnl` / `spread_stress_min_sharpe` / `trade_count_min` を使い、`max_drawdown` と `trade_count_max` は見ていません。また stress payload の sharpe は `trade_sharpe_raw` 系です。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1413) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1427) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1430) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1512)  
  Interpretation: `C_stress` dual-path は「stress hard gate の shadow」ではなく、60d `live_criteria` ベースの別ゲート観測です。本文 1.2 / 3.2 / 5.1 の「step 2 calibration 完成度」表現は強すぎます。  
  修正案:
  `step 1.7` の目的を「Stage C stress の canonical metric 観測追加」に下げ、`gate_pass` を stress hard gate calibration 根拠に使わないことを本文と acceptance に明記してください。stress gate との対応付けは `step 2` か別 step で扱うべきです。
- [Warning]
  使命への直接寄与なし、LOG_ONLY 維持、live_criteria 不変という方針自体は整合しています。
- [Suggestion]
  本文 1.5 に加えて、「`C_stress canonical_gate_pass` は mission 判定にも切替判定にも使わない」を acceptance に 1 行追加した方が安全です。

**2. 禁止事項違反**

- [Critical] なし
- [Warning]
  数値見せかけ改善や live_criteria 緩和には当たりませんが、上の semantic mismatch を放置すると将来の「見せかけ calibration」に繋がります。修正案:
  `C_stress` を descriptive observation に限定する文言へ統一してください。
- [Suggestion]
  `step 1.7` の期待効果から「calibration 不完全の解消」「完全充足に近づく」と読める表現は削った方がよいです。

**3. 実現可能性**

- [Critical] なし
- [Warning]
  物理隔離案そのものは実装可能です。`stress_payload` / `reasons` の更新を legacy try に閉じ込め、dual-path 側で local snapshot だけ読む設計は妥当です。現行 `C_base` は helper raise を outer try が拾う非対称形ですが、今回の `C_stress` 案はそこを改善しています。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1315) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1342)
  修正案:
  acceptance D3 を最重要に据え、`stage_label=="C_stress"` 限定 raise で disabled baseline と deep comparison する方針を本文前半にも昇格してください。
- [Suggestion]
  `D4 dual-path ブロック内では write しない` は runtime test だけでは証明しづらいので、実質契約は D1/D3 の snapshot 比較で担保すると明文化した方が現実的です。

**4. 期待効果の妥当性 (C3 / C7)**

- [Critical]
  「C_base diff と C_stress diff の比較データが取れる」「sharpe_degradation / pnl_degradation の canonical 版が観測できる」は、そのままだと事実と一致しません。  
  Fact: `_log_canonical_dual_path` が出す diff は同一 stage 内の `legacy - canonical` だけで、`C_base` 対 `C_stress` の cross-stage diff は出しません。sharpe diff も出していません。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L247)  
  Interpretation: step 1.7 単独で得られるのは `C_stress` の単独観測であり、`C_base` との比較は後段 join を要します。  
  修正案:
  本文 1.2 / 3.1 の表現を「後段集計で `(genome, stage)` を join すれば比較可能」に下げ、`canonical版 sharpe_degradation` という表現は削除してください。
- [Warning]
  collider bias への注意書きは妥当です。ただし sample size guard は「解釈禁止条件」であって、「比較可能性の定義」ではありません。
  修正案:
  `同一 holdout・異なる trades なので cross-stage comparison は descriptive join のみ` を acceptance に追加してください。
- [Suggestion]
  `C_stress` の log 読み取り規約を 1 行だけ足し、`legacy_sharpe` は `BacktestMetrics.sharpe`、stress payload の `sharpe` は `trade_sharpe_raw` で別物だと明示すると誤読を防げます。[metrics.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py#L36) [metrics.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py#L42)

**5. リスク**

- [Critical] なし
- [Warning]
  `C_stress` の skip 経路一致について、設計意図は良いですが、検証対象は `dual_path` だけでなく `canonical_five.skipped` も含めるべきです。helper 自体が呼ばれていないなら、`stage=C_stress` の skipped log も出てはいけません。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L160)
  修正案:
  acceptance C5 を「`stage=C_stress` の `dual_path` と `canonical_five.skipped` の両 event が非出力」に強化してください。
- [Suggestion]
  stress backtest 例外時の独立性は、`stage_c.stress_failure` が出ても `stage=C_stress` の log が 0 件であることを明示 assert すると監査しやすいです。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1435)

**6. スコープの適切さ**

- [Critical] なし
- [Warning]
  `cross_pair` を切り出す判断は妥当です。ただしその代わり `step 1.7` の位置付けは「step 2 前の有益な観測拡張」に留めるべきで、`Stage C side calibration data が base + stress まで充実` という言い方はやや過大です。
  修正案:
  「partial 拡充」に統一してください。
- [Suggestion]
  本文 1.3 と 3.2 を、`step 2 を block しない optional observability step` へさらに寄せると筋が通ります。

**7. メモリ制約 (24GB / 6 worker / 1 worker 3GB)**

- [Critical] なし
- [Warning]
  追加メモリは低リスクですが、概算はやや粗いです。60d M1 は単純計算で 60,000 本より 86,400 本寄りで、helper は `trade_to_trade_record` / `equity_curve_to_bar_equity_series` / `business_day_universe` の派生オブジェクトも作ります。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L150) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L152)
  修正案:
  メモリ記述は「上限保証ではなく低リスク仮説」に留め、B2 実測を本判断に使う形へ寄せてください。
- [Suggestion]
  この step では数値精度より、「base と同等オーダーで 3GB/worker を大きく下回る見込み」と書く方が安全です。

**8. 前提検証 (C4)**

- [Critical] なし
- [Warning]
  前提表の `"_log_canonical_dual_path(fold_index=None) で C_stress 出力可能"` を Verified に置くのは早いです。現行 helper docstring の stage 列挙は `C_stress` を含みません。[stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L181)
  修正案:
  これは `To Verify in step 1.7` に落とし、acceptance に `C_stress` no-fold log 契約を追加してください。
- [Suggestion]
  `Verified` は「既にコードかテストで固定済」のみに限定し、今回のような推論は `Inferred` か `To Verify` に分けた方が C4 に忠実です。

**9. Design-first 原則 (C1)**

- [Critical] なし
- [Warning]
  設計参照と現行コードの読み合わせはできています。ただし sharpe の意味系が 3 種類ある点を本文が十分切り分けていません。  
  Fact: `legacy_sharpe` は `BacktestMetrics.sharpe`、stress payload の sharpe は `trade_sharpe_raw`、base live_criteria 判定は annualized trade sharpe です。[metrics.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py#L36) [metrics.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py#L42) [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L1134)  
  修正案:
  本文 2.4 か 5.1 に「sharpe 読み替え表」を短く追加してください。
- [Suggestion]
  `C_stress` の review/analysis 用 SSOT を 1 行でよいので作るべきです。
  例: `stress_payload.sharpe = trade_sharpe_raw`, `dual_path legacy_sharpe = bar-level annualized`, `canonical_* = canonical five output`.

**結論**

反証優先で見ると、実装パターン自体は成立しそうですが、「何を観測できる step なのか」の意味付けが 2 点で過大です。  
1. `C_stress canonical` は現行 stress hard gate の shadow ではない。  
2. step 1.7 単独では `C_base` 対 `C_stress` の canonical degradation は直接は得られない。  

この 2 点を設計本文と acceptance で引き下げれば、物理隔離・skip 整合・後方互換の方針自体は前に進められます。