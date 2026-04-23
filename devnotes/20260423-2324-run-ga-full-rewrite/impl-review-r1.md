**判定**: NEEDS_REVISION

**コメント**
- [ブロッカー:scripts/alpha_factory/run_ga.py:588] `best/history` は `_safe_finite` 済みですが、`summary.per_generation[*].best_fitness_pen` は未サニタイズです（生成元は 同ファイル:776）。`nan/-inf` がここ経由で `summary.json` に漏れる経路が残っています。
- [契約逸脱:scripts/alpha_factory/run_ga.py:592] 非有限値フォールバックが `"0.0"` になり得ます（`history` も 同ファイル:621）。要求が「`"0"` 固定」なら文字列表現を正規化してください。
- [テスト堅牢性:tests/scripts/test_alpha_factory_run_ga.py:154] DB mock の bars 判定が呼び出し順依存です（同ファイル:159）。stmt 判別ベースにしないと、クエリ順変更で holdout/fallback/missing の3シナリオが壊れます。

**ブロッカー**
1. `summary.per_generation` に非有限値が漏れる経路があり、R1 B2 の「summary/history 非有限値排除」を満たし切れていません。
2. 非有限値フォールバック文字列が `"0"` でなく `"0.0"` になり得るため、指定された既存契約とズレます。
3. smoke test の DB mock が call-order 依存で、R1 指摘対応（stmt 判別での分離）が未達です。
