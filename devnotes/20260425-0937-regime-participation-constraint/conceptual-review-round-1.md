全体判定: CHANGES_REQUESTED

**観察事実 (Fact)**  
- `docs/alpha_factory/README.md` と `config/alpha_factory/default.yaml` の使命は、`live_criteria` 全達成個体の発見。  
- 現行選抜は NSGA-II ではなく、`scripts/alpha_factory/run_ga.py` の `selection_score=(stage_c_pass, stage_b_pass, stage_a_pass, fitness_pen)` を使う辞書式 + tournament。  
- `src/backtest/engine.py` の `BacktestResult` は `trades` と `equity_curve` のみで、提案文の `position 系列` は現行 API にない。  
- Run 9 分析では `trade_count=0` 優位に加え、`trade_count>0 ∧ total_pnl=0` の整合性疑義も残っている。  

**解釈 (Interpretation)**  
- 無取引優位を構造的に下位化する方向性は使命に整合する。  
- ただし、制約定義・期待効果・実装接続点がまだ粗く、このままだと別物を実装するリスクが高い。  

1. 使命との整合性  
- [Warning] `participation_rate` は regime 横断参加には効くが、`live_criteria.trade_count_min=50` への直接条件ではない。bar 参加率は取引回数ではない。  
  修正提案: `cell_entry_count_min` か `cell_trade_count_min` を別途入れるか、「RPC は no-trade 淘汰用」と効果記述を弱める。  
- [Suggestion] 「無取引淘汰」と「regime 横断参加」を別目的として明記する。  

2. 禁止事項違反  
- [Critical] 現定義だと、少数回の長期保有で複数セルを跨ぐ個体が有利になり得る。これは実質的に「取引回数を減らして見かけ成績」を再発させる抜け道。  
  修正提案: 制約対象を保有バー率ではなく「セル内エントリー回数」または「セル内約定回数」に変更する。少なくとも `trade_count_min` 系の下限制約と併用する。  
- [Suggestion] `live_criteria` 緩和ではない点は明確で問題ない。  

3. 実現可能性  
- [Critical] 設計文は「NSGA-II constraint dominance / Pareto 比較」を前提にしているが、現行コードは単一スカラー選抜。実装対象の認識がずれている。  
  修正提案: Phase 1 は現行実装に合わせ、`selection_score` の先頭へ `feasible` / `violation` を足す設計に落とす。NSGA-II 化は別 TODO。  
- [Warning] `position 系列` は現行 `BacktestResult` にない。`trades` だけで足りるか未確定。  
  修正提案: `trades` 由来で十分か、`BacktestResult.position_timeline` 追加が必要かを明記する。  
- [Warning] 変更先として書かれた `src/alpha_factory/ga/operators.py` は現行 repo にない。GA 選抜の実体は `scripts/alpha_factory/run_ga.py`。  
  修正提案: 変更責務を現行ファイル構成に合わせて書き直す。  

4. 期待効果の妥当性  
- [Critical] 「9セル × 各セル5 trade 以上で trade_count=45」は、提案した指標から導けない。事実ではなく未検証の解釈。  
  修正提案: 期待効果は「`trade_count=0` 個体比率の低下」「best が `trade_count=0` になる率の低下」に留める。`trade_count` 増加は検証仮説として扱う。  
- [Warning] セル母数が小さい場合、最低参加率はノイズに支配される。C7/C4 的に各セルの `n_bars` 前提が未検証。  
  修正提案: `min_cell_bars` を設けるか、violation をセル母数で重み付けする。  
- [Suggestion] Run 10 の falsification は `trade_count=0` 比率、`best_no_trade_rate`、`Stage A pass件数` に絞る。  

5. リスク  
- [Critical] `trade_count>0 ∧ total_pnl=0` の別系統不整合が残ったまま制約を足すと、原因分離が難しくなる。  
  修正提案: RPC 前に、少なくとも約定数と PnL の invariant 監査を先に置く。  
- [Warning] 9セル全部を hard feasible にすると、初期世代の大半が infeasible になり、選抜圧が `violation_magnitude` のみへ寄る恐れがある。  
  修正提案: `apply_from_generation` を設けるか、段階導入にする。  

6. スコープの適切さ  
- [Warning] 「新分類器」「集計」「選抜変更」「archive 拡張」「config 拡張」を一度に入れるのは、Run 10 の最小反証実験として広すぎる。  
  修正提案: Phase 1 を「no-trade/infeasible 判定 + 選抜反映 + 最小診断列」に縮め、9セル化や archive 永続化は Phase 2 に分割する。  
- [Suggestion] まず「`trade_count=0` を構造的に不利化すると分布が改善するか」を反証する最小変更に寄せる。  

7. メモリ制約  
- [Warning] `36 bytes` は生配列だけの見積もりで、Python/Arrow のオーバーヘッドを含んでいない。  
  修正提案: 「支配的ではない見込み」に留めるか、固定長配列前提で再見積もる。  
- [Suggestion] 主リスクはメモリより複雑性。  

8. 前提検証 (C4)  
- [Critical] 「Stage 通過率の閾値変更は不要」は未検証。現行選抜は `stage_a_pass` を選抜スコアに含むため、feasibility 追加で通過率分布は変わる。  
  修正提案: 「閾値は直接変更しないが、通過率分布には影響する」に修正する。  
- [Warning] `ATRRegimeGate` の意味再定義は今回提案の直接効果ではなく、将来の設計帰結に近い。  
  修正提案: 直接効果から外す。  

9. Design-first (C1)  
- [Suggestion] `docs/alpha_factory/README.md`、`stage-gates.md`、`concepts/genome-archive-schema.md`、`devnotes/20260425-0931-fx-improve/*`、`git log` は参照済み。レビュー前提は満たしている。  

結論として、方向性は妥当です。ただし現状の RPC は「trade_count を増やす制約」ではなく「露出バーを増やす制約」になりやすく、現行 GA 実装とも接続点がずれています。  
最小修正版は、「`trade_count=0` あるいは `entry_count<k` を infeasible 化し、現行 `selection_score` に feasibility を先頭追加、Run 10 では `trade_count=0` 比率低下を反証する」です。