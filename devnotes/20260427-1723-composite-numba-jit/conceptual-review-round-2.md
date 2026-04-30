**Findings（重要度順）**

- `[Warning]` 概念設計 §3.1 の「Stage A 全体 run_backtest 削減: 15-25%（on_bar が cumtime 22%）」は根拠が不整合です。提示値からは `on_bar/run_backtest = 1.165/3.427 ≈ 34%` なので、`on_bar削減 40-65%` を掛けると理論上は概ね `14-22%` が上限帯です。`25%` は現状の根拠では強すぎます。  
- `[Warning]` 概念設計 §4.2 の kernel 引数 `gate_weights_flat` は、参照実装 B の `compute_gate`（値の積のみ）と整合が曖昧です。将来の実装で誤って gate weight を掛ける回帰リスクがあるため、「未使用である」か「将来拡張用で今回未参照」を明記した方が安全です。  
- `[Warning]` 概念設計 §5.3 は aggregate を `allclose` 契約、T037 を exact `!= 0.0` 契約に分けており方向は正しいですが、近傍ゼロ値で T037 だけ不一致になるケースの受入基準（失敗時にどう扱うか）が未定義です。falsification 観点では「ゼロ近傍ケースで T037 parity を優先判定する」運用ルールを 1 行追加すると閉じます。  

**Round 1 [High] 3件の解消判定**

- H1（Stage B/C 線形主張）: **解消**。Facts/Interpretation 分離と INCONCLUSIVE 維持は妥当です。  
- H2（bars_scale の雑な日数比）: **実質解消**。実 bar 比へ変更し、暫定値を明確に暫定扱いしている点は妥当です。  
- H3（メモリ回帰）: **解消**。`unique_signal_matrix + indirection` で重複排除の不変条件を維持できています。  

**新規 Critical / Warning**

- 新規 **Critical はなし**。  
- 新規 **Warning は上記 3 件**。  

**総合判定**

- **CHANGES_REQUESTED**（軽微修正）。  
- 理由: 実装方針は成立していますが、§3.1 の効果見積り整合と §4.2/§5.3 の契約明確化を先に直すと、詳細設計以降の評価基準ぶれを防げます。