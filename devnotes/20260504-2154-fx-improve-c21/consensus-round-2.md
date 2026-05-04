**結論（先に）**
- `仮説H` は棄却で妥当です。
- 現時点の主因は「`Stage B` と `Stage C` の評価スケール不整合（期間・必要trade数・Sharpe可用条件の差）」で、`g8_i33/g12_i17` の `stage_c_pass=False` は少なくとも `trade_count<50` が直接原因です。
- ただし `g8_i33/g12_i17` の厳密な `reason_codes` は archive に永続化されておらず、個体別の最終確定は **INCONCLUSIVE**（コード上の強い推定）。

**Fact**
- `Stage C` は `trade_count_min=50` を厳密に AND 判定しています。  
  [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1467)  
  [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1478)
- `Stage C` は `trade_sharpe_raw` が `None` だと `sharpe<min` 側に倒れます（annualized前提でも `None` のまま）。  
  [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1404)  
  [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1462)
- `g8_i33/g12_i17` の archive `trade_count=16/17`・`stage_c_pass=false` は run-32 診断に出ています。  
  [stage_b_judgment_audit.json](/Users/ishitoya/repository/zenigame-fx/reports/run-reports/run-32/diagnostics/stage_b_judgment_audit.json:37)
- `Stage C reason_codes` は archive に保存されていません（`stage_b_reason_codes` はあるが `stage_c_reason_codes` はない）。  
  [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:124)  
  [archive.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py:576)

**Q1**
- (a)(b)(c) の反証設計は正しいです。  
- 追加で重要点: 現行は `oos_sharpes` は持つが fold別 `trade_count` は持たないため、Iの反証には fold trade数の観測追加が必要です。  
  [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1197)

**Q2（cycle 21 を1つに絞る）**
- 推奨: **案X**（ただし最小化版）  
- 理由: 仮説Iを直接 falsify でき、しきい値変更なしで C9 に沿うため。  
- 実装最小化: archive schema拡張ではなく、まず `diagnostics` sidecar に `stage_b_fold_trade_counts` を追加して観測する。

**Q3（Stage C fail reason）**
- コード上、`trade_count=16/17` なら `live_criteria.trade_count<min` は必ず reason に入ります。  
  [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1478)
- `trade_sharpe_stage_c=None` なので `live_criteria.sharpe<min` も入る可能性が高いです。  
  [stage_gate.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1472)
- ただし個体別 reasonの最終確定は、現状の保存設計ではできません（INCONCLUSIVE）。

**Q4（全体結論 + cycle 22予告）**
- 全体結論:  
  1) Hは棄却。  
  2) 主因は B/C スケール不整合（Bで通るがC 60日+LCで落ちる）。  
  3) 次は「反証用の観測」を先に入れるべき。
- cycle 22 予告（cycle21結果分岐）:  
  1) time-concentrated が確認された場合: B→C接続制約（例: B pass候補に holdout換算の最低trade密度ガード）を設計。  
  2) 均一低密度だった場合: `holdout_days` と `live_criteria.trade_count_min` の整合再設計（Yを本格実施）。