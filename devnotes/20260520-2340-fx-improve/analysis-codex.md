## 1. 観察事実（Facts）
- Run 82（seed=67, EUR_JPY, pop=96, gens=60, stage_b_gate=profit_safe_pfr）で `Stage A=2687`, `Stage B=941`, `Stage C=0`, `graduated=0`。
- Stage 通過数は Run81 比で `A +17%`, `B +31%`、ただし `C は 0 のまま`。
- best fitness_pen 個体 `g53_i19` は `fitness_pen=0.489`, `fitness_raw=0.528`, `stage_b_pass=False`, `trade_count=41`, `total_pnl=+43240`。
- graduation 候補評価では `sharpe=2.276(annualized)` と `max_drawdown=1.23%` は閾値通過、`total_pnl=4670<50000` と `trade_count=23<50` は未達（2/4）。
- Stage B 通過群（n=941）の分布は `trade_count median=34`, `total_pnl median=-1950`, `trade_sharpe_stage_c median=-0.038`（NaN 290件）。
- Stage C 不通過 reason の上位は `median_oos_total_pnl<min` と `sum_oos_total_pnl<min` 系が多数。
- A pass 構造分布は `active_clause=1 or 2` のみ、`n_nodes median=3`。
- primitive 出現（A pass sample500）で `P7=586`, `P2=585` と偏在が大きい。
- Run54-82 では mission 達成は Run75 のみ。全 RUN で `DSR proxy pass=0`。

## 2. 解釈・推論（Interpretations, falsification-first）
### 仮説A: ボトルネックは Stage B ではなく「Stage B→C の目的不整合」
- 反証可能性: Stage B 通過群から Stage C へ進んだ個体の `median/sum_oos_total_pnl` が正であれば、この仮説は棄却。
- 現状評価: Stage C 不通過 reason が pnl 系に集中し、C通過0。Bの通過増加がC改善に接続しておらず、仮説は暫定支持。

### 仮説B: `profit_safe_pfr` が「見かけ上」安全でも、実質 OOS 負群を通している
- 反証可能性: Stage B 判定時に使う `median_oos_total_pnl` と集計で見ている `total_pnl` が同一スコープ・同一定義で、かつ通過群で非負が確認できれば棄却。
- 現状評価: B通過群 `total_pnl median=-1950` は gate 名称（profit_safe）と緊張関係。まず「指標スコープ不一致（B判定値と集計値が別物）」の監査が必要。

### 仮説C: 現在の主壁は `total_pnl` と `trade_count`（live_criteria）
- 反証可能性: Stage C 通過個体で `trade_count>=50` かつ `total_pnl>=50000` が一定数出れば棄却。
- 現状評価: 候補例が `trade_count=23`, `total_pnl=4670`。sharpe は通るため、収益量と約定密度不足が主要制約。

### 仮説D: 禁止事項6（取引回数削減で sharpe 稼ぎ）の過選択兆候がある
- 反証可能性: `trade_count` と `sharpe` の関係で、低回数帯が優位でない（もしくは高回数帯でも同等以上）なら棄却。
- 現状評価: live候補が低取引で sharpe 通過・回数未達。過選択の疑いは高いが、因果確定には分位比較が必要。

### 仮説E: P7/P2 偏在 + genome浅さが探索空間を狭め、OOS収益構造を掴めていない
- 反証可能性: primitive 多様化後も Stage C pnl 分布が改善しなければ棄却。
- 現状評価: `active_clause<=2`, `n_nodes median=3`, primitive偏在は「同型解の大量生成」を示唆。探索の実効多様性不足が疑われる。

## 3. 次サイクル候補（閾値緩和なし）
### Critical（1）
1. **Stage B 判定メトリクスと archive 集計メトリクスのスコープ一致監査を最優先で実施**
- 目的: `profit_safe_pfr` が実際に何を通しているかを同一定義で検証。
- 介入: B判定で使った値（fold単位の median/sum pnl, n_fold_effective, pfr）を個体単位で永続化し、report 側で同値を再集計。
- 成功条件: 「B通過=非負OOS pnl」という設計意図の真偽を機械的に判定可能にする。

### Warning（2-3）
1. **低取引sharpe偏重の構造抑制（閾値変更ではなく目的関数の正則化）**
- 例: fitness に「取引密度不足ペナルティ」または「時間帯カバレッジ項」を追加し、23トレード型の過選択を抑える。

2. **探索多様性の構造介入**
- 例: primitive 使用エントロピー監視、同型ゲノム重複抑制、浅い木への集中を防ぐ変異オペレータ（深さ上限緩和ではなく“偏在抑制”）。

3. **Stage C 失敗 reason の反証バッチ**
- 例: reason code 上位（median/sum pnl不足）に対し、失敗個体群で「どの時間帯・方向・コスト控除で崩れているか」を固定フォーマットで分解し、次世代の生成バイアスに反映。

## 4. 全体判定
**CRITICAL_DRIFT**  
- 理由: Stage B 通過の増加が Stage C/mission 達成に全く接続しておらず、目的整合性の崩れが示唆されるため。