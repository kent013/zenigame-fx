```markdown
# analysis-codex.md
# Run 9 Codex独立分析（run_20260425_002330）

## Facts（観察事実）

- 前提（C4）
- `n=120`（6世代 x 20個体）で、`n<30` ではない
- 対象データは `EUR_JPY` 単一銘柄（cross-pair は単独実行条件）
- 参照元は archive parquet と `reports/run-reports/run-9/summary.json`

- ステージ通過
- `stage_a_pass=0/120`
- `stage_b_pass=0/120`
- `stage_c_pass=0/120`
- `graduated=0/120`

- 収益・フィットネス
- `total_pnl` は全120個体で `0.0`（min=max=mean=0.0）
- `fitness_pen` は `max=0.0`, `mean=-8.9138`, `min=-93.1091`
- `fitness_pen=0.0` は 90個体、`fitness_pen<0` は 30個体

- 取引回数
- `trade_count=0` は 90個体（75%）
- `trade_count>0` は 30個体（25%）
- `trade_count<=10` は 94個体
- `trade_count_max=1331` だが、取引した個体の `sharpe` は全て負（min -93.10, max -4.76）

- 世代推移
- 世代平均 `trade_count`: `380.9 -> 100.6 -> 44.7 -> 14.2 -> 22.15 -> 82.1`
- 世代平均 `fitness_pen`: `-25.45 -> -8.39 -> -4.56 -> -3.37 -> -3.95 -> -7.76`
- `summary.ga_config.generations=5` だが実アーカイブは `generation 0..5` の6世代

- 禁止事項関連の観測
- イントラデイ逸脱の直接兆候なし（`time_stop_min` は 8〜189、`>1440` は 0）
- `live_criteria.trade_count_min=50` は維持（緩和の痕跡なし）
- `best` 個体は `trade_count=0` で選抜（`fitness=0`）

- primitive / 多様性
- 出現 primitive は 21種、directional slot 合計291
- 上位シェア: `P7(18.6%), F11(13.4%), P9(12.0%), P5(11.3%)`
- 組合せは初期20種から後半7〜10種へ縮退
- 最頻組合せ `('F11','P5','P7','P9')` が 26/120

- cross-pair shadow
- `cross_pair_config.mode=shadow`, `aggregator_lambda=0.5`
- 実行時は `cross_pair_runtime_mode="skipped_single_instrument"`
- archive列に cross-pair/shadow 実測列は見当たらない

## Interpretations（解釈・推論）

- 仮説1（Stage gateボトルネック）  
  `trade_count=0` 個体の `fitness_pen=0` が、取引する個体（負Sharpe）より相対優位になり、GAが「無取引」へ収束した可能性が高い。  
  反証可能性: `trade_count=0` に明示ペナルティを与えたA/B実験で、`stage_a_pass` と `trade_count` 分布が改善しなければこの仮説は棄却。

- 仮説2（評価一貫性の問題）  
  `trade_count>0` なのに全個体 `total_pnl=0.0` は、PnL集計経路の不整合（丸め/別系列参照/保存欠落）を示唆。  
  反証可能性: 同一個体の約定列・エクイティカーブから `total_pnl` を再計算し一致確認。一致するなら仮説棄却、不一致なら確定。

- 仮説3（禁止事項 #7 の構造的再発）  
  ルールを緩和していなくても、評価関数の形が「取引しないほど有利」を生み、実質的に取引回数削減を誘発している。  
  反証可能性: `trade_count` 下限制約（soft/hard）を入れても依然 `tc=0` 優勢なら、主因は別（シグナル死滅や執行条件）であり本仮説は弱まる。

- cross-pair shadow 妥当性  
  今回は single instrument で shadow がスキップされており、cross-pair 統計の有効性は判定不能（C8: INCONCLUSIVE）。  
  反証可能性: 複数ペア同時RUNで shadow 指標が実際に記録されることを確認する。

## 次サイクル候補

- Critical（1）
- **無取引優位の即時反証実験**  
  `tc=0` へのペナルティ付与 or `trade_count_min` を fitness 側に内生化し、同条件で短縮RUNを2本実施。成功基準は `stage_a_pass>0` かつ `tc=0` 比率の有意低下。

- Warning（2-3）
- **PnL集計監査**  
  `trade_count>0` 個体の `total_pnl=0` 固定の原因を特定（評価系の数値整合テストを追加）。
- **primitive縮退監視**  
  組合せ多様性の世代縮退を監視し、novelty圧または同型抑制の有無を検証。
- **cross-pair shadow の実装妥当性確認**  
  複数通貨ペアRUNで shadow が「実際に」評価へ反映されるかを検証（single instrument skip は仕様として妥当だが、現状は未検証）。

## 全体判定

**CRITICAL_DRIFT**
```

現在の実行環境が read-only のため、`{tmp_dir}/analysis-codex.md` への直接書き込みはできませんでした。上記内容をそのまま保存すれば要求フォーマットを満たします。