- [Warning] `fitness_raw` が sentinel 化されておらず、Stage A の失敗経路では依然として `None` のまま `payload` に載るため、archive 取り込みで `_required_float(..., default=0.0)` が働き 0.0 に正規化されます。これでは Stage A failure 行と本来の 0.0 実測が区別できず、設計ノートで狙っていた「測定不能を sentinel で可視化する」効果が得られません。`fitness_pen` は修正済みですが、`fitness_raw` も sentinel を入れるか、少なくとも archive 側で別扱いできるようにすることを検討してください。`src/alpha_factory/stage_gate.py:383-412`, `src/alpha_factory/archive.py:212-218`
- [Suggestion] `min_exposure_trade_count < live_criteria.trade_count_min` ガード自体は有効ですが、`live_criteria.trade_count_min=1` のような極小設定を許容したいケースでは不等号が両立せず config 構築に失敗します。もし将来的に低トレード閾値を試す可能性があるなら、`trade_count_min<=1` の場合はガードを緩めるか、エラーメッセージで想定条件を明示すると運用しやすくなりそうです。`src/alpha_factory/stage_gate.py:176-198`

軽い確認事項: sentinel の序列値 (-1e12/-1e9/-1e6) は現行の Sharpe 帯から十分離れており、`calibrate_gate` は `STAGE_A_FITNESS_SENTINELS` の集合一致で除外できていました。`no_trades` → `no_exposure` のリネームもコード／テスト／docs まで反映されており、GA の選択ロジックが禁止事項 #3 を踏み越える変更も見当たりません。

テスト: `uv run pytest`, `uv run ruff check`, `uv run mypy src/` を通過済みとの報告あり。

判定: APPROVED