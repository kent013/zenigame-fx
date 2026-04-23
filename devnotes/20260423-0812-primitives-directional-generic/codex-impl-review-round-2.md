Must-fix
- なし（提示コードの範囲では、ルックアヘッド混入を示す決定的な欠陥は確認できませんでした）

Should-consider
1. F14 の下限 `0.0` を明示検証する専用アサートを追加  
`test_output_bounded` は全 primitive を `[-1, +1]` で検証しており、F14 要件 `[0, +1]` の下限は未固定です（退行検知力を上げるため）。
2. `compute == compute_all_bars[idx]` の index 網羅を拡張  
14 primitive 網羅は満たしていますが、現在は `idx=(50,80,119)` の固定3点です。境界 (`warmup終端`, `最終-1`, `最終`) やランダム複数点を追加すると契約検証がより堅くなります。
3. F13 の lag 方向を直接検証する決定論テストを1本追加  
現状でも `test_no_lookahead_property` で逆方向 shift は実質検知可能ですが、`y[i]=r[i-lag]` を期待値で直接確認するテストがあると、意図がさらに明確になります。

Nit
- `test_no_lookahead_property` の `k` を単一点（60）から複数点化すると、将来の実装変更に対する感度が上がります。

判定: **APPROVED**

確認結果（依頼5項目）
1. 未来非参照: **OK**（rolling系、Wilder recurrence、F6、F13 とも提示実装は過去方向）  
2. `compute` 一致 14 primitive 網羅: **OK**（primitive網羅は成立。index網羅は改善余地あり）  
3. F6/F13 時間方向テスト: **OK**（F6専用あり、F13は lookahead 性質検証あり）  
4. 境界テスト全 primitive 適用: **概ねOK**（`[-1,+1]` は全体適用。F14 `[0,+1]` は専用化推奨）  
5. `ensure_registered` atomic 冪等性: **OK**（`register_if_absent` の lock 保護で成立）