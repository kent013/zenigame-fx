**観察事実（Facts）**
- Run `run_20260425_004002` の最良個体は `trade_count=3`, `total_pnl=18860`, `sharpe=18.49`, `max_drawdown_pct=0.0`。
- `live_criteria` は `sharpe` と `max_drawdown_pct` は達成、`total_pnl` と `trade_count` は未達。
- アーカイブ 5856 行中、`Stage A pass=4291`、`Stage B pass=0`、`Stage C pass=0`。
- `Stage B/C pass=0` は 60 世代を通じて継続。
- 世代進行で `Stage A pass` は `gen0:8 → gen5:47` と増加し、最終 fitness は `18.48`。
- 最良個体の構造は `n_nodes=2`, `active_clause=0`（最小複雑度側）。
- holdout は `37832 bars` あるが、B/C に到達した個体はない。
- `cross_pair` は `runtime=skipped_single_instrument`。

**解釈・推論（Interpretations, C9 falsification-first）**
- 前提（verified）
- `n(trades)=3` は C7 の基準（n<10 の相関/性能主張禁止）に該当。
- B/C 通過個体がゼロなので、B/C での一般化性能は未観測。

- 反証対象H1: 「高Sharpe（18.49）は戦略品質の改善を示す」
- 反証: `trade_count=3`、`total_pnl` 未達、B/C到達ゼロ。
- 判断: H1は棄却。高Sharpeは「低頻度サンプルでの見かけ値」の可能性が高い。

- 反証対象H2: 「GA進化で実運用条件に近づいている」
- 反証: A-pass は増えている一方、B-pass が全世代ゼロで固定。
- 判断: 「A最適化のみ進行、使命（live_criteria同時達成）には非収束」。ゲート間ミスマッチが主因候補。

- 反証対象H3: 「禁止事項違反はない」
- 反証: 直接の閾値緩和証拠は提示なし（この点は INCONCLUSIVE）。ただし `trade_count=3` での高Sharpe追従は禁止事項7の兆候と整合。
- 判断: 明示違反は未確定だが、運用上は「違反予備軍」の挙動。

- Stage B全滅の原因仮説（反証可能性付き）
1. 仮説A: Aの評価軸が「低頻度・低分散個体」を通しすぎる  
   - テスト: A-pass個体の `trade_count` 分布を抽出し、B-failとの対応を確認。
2. 仮説B: B窓（18mo）で regime 非適応（期間依存）  
   - テスト: B窓を分割し、月別/期間別で gross・cost・hit率の崩れ位置を特定。
3. 仮説C: 構造多様性不足（`n_nodes=2`, `active_clause=0` への収束）  
   - テスト: 世代ごとの構文多様度（ユニーク式数、primitive使用エントロピー）と A/B pass の関係を計測。
4. 仮説D: 単一銘柄運用で交差検証圧が不足  
   - テスト: shadow cross-pair を有効化したときの A→B 遷移率変化を比較。

- primitive偏在/多様性について
- `active_clause=0` と最小ノード収束は、「探索が単純式に偏っている」または「複雑式が早期淘汰される選択圧」のサイン。
- 現状データだけでは「単純式が本質的に優位」か「探索空間設計の欠陥」かは未確定（INCONCLUSIVE）。

**次サイクル候補**
- Critical（最優先）
1. `Stage A` に最低取引密度制約を導入（例: A通過条件に `trade_count` 下限、または frequency-aware fitness）し、A→B遷移可能な個体だけを残す。

- Warning
1. B失敗理由を分解ログ化（Sharpe要因、cost要因、trade不足要因を個体単位で保存）し、B全滅の内訳を可視化。
2. 構文多様性維持策（初期集団のprimitiveバランス、淘汰圧の緩和、重複式ペナルティ）を小さく導入。
3. cross_pair の shadow を実行有効化し、単一銘柄過適合の早期検知を追加。

**全体判定**
- `CRITICAL_DRIFT`