1. 最も情報量が高い次手は **B（`70k + seed70`）** です。  
同一 seed で `74k→70k` の反実仮想を取れるため、**閾値効果を直接同定**できます。A（`74k + seed71`）は seed と gate が同時に変わり、解像度が落ちます。

2. `74k` が複数 seed で `StageC≈0` なら、`70k` への revert は「緩和禁止」違反ではありません。  
これは「達成済み frontier の後退」ではなく、**未検証な引き上げ案の棄却（構造的到達不能帯からの撤退）**で、cycle13 precedent と整合します。  
運用ルールとして「引き上げ採用は独立2seed以上で再現」を明文化するとブレません。

3. `ii_lite_pass 0→188` は、現時点では **手がかりだが目的KPIの代替には不可** です。  
解釈は「探索 basin が変わったシグナル」。ただし StageC=0 なので、今は **mission と逆相関の可能性** も高いです。shadow観測は継続、selection 反映は保留が妥当です。

4. R98（反証可能な基準）  
`config`: R97から `total_pnl_min` だけ `74000→70000`、`seed=70` 固定。  
成功（仮説「74k過大」を支持）:  
- `StageC_pass > 0`  
- `mission_candidate >= 10`  
- `holdout total_pnl median` が R97比で明確回復（目安 `>=45k`）  
失敗（仮説を棄却）:  
- `StageC_pass = 0` かつ `mission_candidate < 10` が継続

全体判定: **R98は `70k + seed70` を1本実行して、threshold因果を先に切り分ける。**