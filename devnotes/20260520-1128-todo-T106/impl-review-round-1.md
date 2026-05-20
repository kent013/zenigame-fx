**指摘（重要度順）**
- [Critical] なし
- [Warning] `yield_per` による「実運用 PostgreSQL/psycopg3 での server-side cursor 発動」がテストで直接検証されていません（現在の追加テストは mock/SQLite 中心）。OOM 対策の主目的に直結するため、1 本は実 DB 検証を入れるのが安全です。  
修正案: PostgreSQL を使う統合テストを追加し、`_stream_bars`/`_stream_aux_pair_bars` 実行時のメモリ増分または cursor streaming 挙動（少なくとも `.all()` しない経路）を確認する。
- [Suggestion] `run_ga.py` と `aux_loader.py` で `_LOAD_BARS_BATCH_SIZE` / 列定義が重複しており、将来ドリフトしやすいです。共通定数化すると保守性が上がります。
- [Suggestion] コメントや docstring のチケット表記が `T108` になっており、今回依頼の `T106` とトレース上ずれます。実装管理上は統一推奨です。

**ファイルごとの判定**
- [APPROVED] [scripts/alpha_factory/run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py)  
`_stream_bars` の `try/finally + result.close()` は妥当。`_construct_price_bar` への全フィールド伝搬も問題なし。`_bar_row_to_price_bar` 互換維持も適切。
- [APPROVED] [src/alpha_factory/aux_loader.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/aux_loader.py)  
V15 duplicate fail-fast を維持しつつ streaming 化できています。`try/finally + result.close()` も正しいです。
- [APPROVED] [src/alpha_factory/bars_digest.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/bars_digest.py)  
順序依存 digest と `Decimal str()` 方針は、桁・表記差分検知の目的に合致。
- [APPROVED] [tests/alpha_factory/test_aux_loader_align.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_aux_loader_align.py) / [tests/alpha_factory/test_bars_digest.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_bars_digest.py) / [tests/scripts/test_alpha_factory_run_ga.py](/Users/ishitoya/repository/zenigame-fx/tests/scripts/test_alpha_factory_run_ga.py)  
close 契約、属性アクセス契約、digest 同値性の検証が入っており妥当。

**Fact**
- `_stream_bars` / `_stream_aux_pair_bars` は `result.close()` を `finally` で保証。
- `_bar_row_to_price_bar` は残存し、内部で `_construct_price_bar` に委譲。
- column-tuple 読み出しは `row.bar_time` 等の属性アクセスのみ。
- `bars_digest` は `Decimal` を `str()` 直列化（trailing zero 差も検出）。
- `psutil` は関数内 import + 例外時 `main_rss_mb=-1.0`/`error_type` ログ。

**Interpretation**
- C-1〜C-4 の実装意図と整合し、identity map 汚染回避・二重保持削減の方向は正しい。
- T087 disjoint 契約や aux V15 fail-fast を壊す差分は見当たりません。
- 禁止事項（criteria 緩和、GA ハック、評価期間延長など）違反は見当たりません。
- ただし「server-side cursor が本番 DB で実際に効いているか」は現状テストでは **INCONCLUSIVE**。

**特に確認したい点への回答**
1. `try/finally + result.close()` は両関数とも正しいです。  
2. `_bar_row_to_price_bar` を残して `_construct_price_bar` 経由にした互換性は妥当です。  
3. SQLAlchemy の `Row` で属性アクセスは通常有効です（本件の列名衝突もなし）。  
4. `Decimal str()` は桁落ち/表記差（特に trailing zero）検出用途として十分です。  
5. `psutil` の関数内 import は任意依存化・障害隔離の観点で妥当です（オーバーヘッドは軽微）。

**全体判定**
- **APPROVED**（コード差分レビューとして）  
- ただし、設計書本文との 1:1 照合と本番 DB での streaming 実効確認は別途実施推奨です。