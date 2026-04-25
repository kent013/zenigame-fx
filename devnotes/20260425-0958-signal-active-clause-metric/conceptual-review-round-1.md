APPROVED

[Critical] なし

1. 使命との整合性 – [Good]  
   - live_criteria へ直接寄与しない点を明示しつつ、観測精度基盤として他 TODO 群の効果検証を可能にする道筋を説明しており、North Star と矛盾しない。  

2. 定義の明確性 – [Suggestion]  
   - **(b) Runtime fired** を選択した理由は妥当だが、  
     • 取引が 1 回も発生しなかった場合（position != 0 が無い run）でも clause_score が発火し得るかをケース分けしておくと誤解を避けられる。  
     • `compute_clause_score(...) != 0` 判定は float 比較の誤差影響を受けるため、閾値 ε を設けるかドキュメントに注記を追加することを推奨。  

3. 実現可能性 – [Good]  
   - DslStrategy → evaluate_stage_a → collect_stage_a → archive.flush の経路が具体的に示されており、規模も小さく衝突リスクは低い。  

4. 転記漏れチェック – [Warning]  
   - schema 定義・row_template・collect_stage_a までは触れているが、`flush()` 内でデフォルト 0 が残置されたままにならないかの確認手順が書かれていない。設計書に「Run10 以降の flush で payload 値を優先する」旨を明記すると安心。  

5. 副作用チェック – [Good]  
   - fitness／selection 経路に触れないこと、メモリ・速度影響が軽微であることを定量で示しており妥当。  

6. archive 後方互換 – [Warning]  
   - Run7-9 の既存 archive を読むスクリプトが `active_clause` を 0 前提でロジック分岐している可能性に言及してほしい（例: ヒストグラム軸幅固定）。互換性回避策（version flag か null-safe 集計）を一文追加すると良い。  

7. テスト計画 – [Good]  
   - fired/未発火の両ケースをユニットテストで網羅。integration で `collect_stage_a→parquet 出力` まで通す E2E テストを 1 本だけ追加すると信頼性が上がる。  

8. スコープの適切性 – [Good]  
   - Stage A へ限定した理由（まず観測値として有用か確認→将来拡張）は合理的。  

9. 禁止事項遵守 – [Good]  
   - 8 項目すべてに不該当であることを表形式で確認しており問題なし。  

10. リスクの網羅性 – [Suggestion]  
    - 並列 worker が同一 genome を評価する場合に `_active_clause_indices` が thread-local であることをコード側で保証する必要がある（Python マルチプロセスなら問題ないが、共有メモリ化の将来改修を見据えて注意喚起すると良い）。  

総評: 観測精度問題を解くための最小限・低リスクな施策であり、使命と制約を満たしている。上記 Warning／Suggestion は文書補足レベルの修正で済むため、実装着手を許可する。