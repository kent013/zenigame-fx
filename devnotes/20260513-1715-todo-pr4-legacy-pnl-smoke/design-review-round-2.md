1. **Critical / Warning の判定**  
`APPROVED` です。Round 1 の `[Critical] 2件` と `[Warning] 2件` は、設計書上で解消されています。  
確認根拠:
- sentinel不変性契約の明文化: [detailed-design.md:268](/Users/ishitoya/repository/zenigame-fx/devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/detailed-design.md:268)
- 境界等号仕様のSSOT化: [detailed-design.md:296](/Users/ishitoya/repository/zenigame-fx/devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/detailed-design.md:296)
- baseline median定義の明確化: [detailed-design.md:698](/Users/ishitoya/repository/zenigame-fx/devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/detailed-design.md:698)
- payload監査項目7 fields化: [detailed-design.md:320](/Users/ishitoya/repository/zenigame-fx/devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/detailed-design.md:320)

2. **追加で見落としがないか（新規Critical有無）**  
新規 `Critical` はありません。  
非blockingの整合メモのみ2点あります。
- 概念設計側の smoke 文言が旧表現のままです（`baseline=直近RUN` と読める）: [conceptual-design.md:182](/Users/ishitoya/repository/zenigame-fx/devnotes/20260513-1715-todo-pr4-legacy-pnl-smoke/conceptual-design.md:182)  
  詳細設計の5 RUN median定義と揃えると運用解釈がぶれません。
- 設計文では `--fitness-mode legacy_pnl_smoke` 実行を想定していますが、現行CLIには当該引数が未定義です: [run_ga.py:300](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:300)  
  （`--stage-a-threshold` はあるが `--fitness-mode` は未実装）

3. **PR4実装着手可否**  
着手可です。`GO` 判定です。  
上の2点は実装ブロッカーではないため、PR4本体と同時修正か次PRでの追随で問題ありません。