**評価: NEEDS_REVISION**

1. **[重大] `mypy` 想定衝突が残っています（`payload` の型）**  
`StageResult.metrics` は `Mapping[str, object]` 型なのに、設計コードでは `payload.get(...)` / `len(oos)` を直接呼んでいます。`mypy` では `object` に対する `.get` や `len` が通らないため、§10 の「mypy クリーン」前提と矛盾します。  
参照: [detailed-design.md:208](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:208), [detailed-design.md:244](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:244), [detailed-design.md:303](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:303), [stage_gate.py:162](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:162)

2. **[重大] `flush` の last-mile guard 前提が弱いです**  
「schema 不一致キーで `ArrowInvalid`」を guard にしていますが、`pyarrow` は schema 指定時に余剰データを無視する経路があるため、余剰キー検知の保証になりません。`from_pylist` 前に `set(row.keys()) == set(GENOMES_SCHEMA.names)` を明示検証する設計へ修正が必要です。  
参照: [detailed-design.md:399](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:399), [detailed-design.md:334](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:334)

3. **[中] テスト網羅 24 件は不足があります**  
`collect_stage_b/c` の wrong-stage 例外分岐は実装予定にあるのに、テスト一覧は Stage A のみです。`payload` 欠損の defensive get 観点も `cross_pair`/`result` 欠損や型不正のケースが未記載です。  
参照: [detailed-design.md:229](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:229), [detailed-design.md:274](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:274), [detailed-design.md:520](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:520)

4. **[軽微] nullable 整合の明文化が未完です**  
詳細設計では `bootstrap_ci_lower/upper`, `fold_sign_ratio` を nullable にしていますが、現行 schema doc は nullable 明示が不足しています。観点1を満たすため、実装前に doc 側で nullable を明示してください。  
参照: [detailed-design.md:61](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:61), [genome-archive-schema.md:33](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/concepts/genome-archive-schema.md:33)

**観点別クイック判定**
1. △（doc nullable 明示不足）  
2. ○（import-time assert 方針は妥当）  
3. ○（monotonic enrich ロジックは整合）  
4. ○（`stage_gate` payload キーと概ね整合）  
5. ○（`oos_sharpes` からの計算方針は妥当）  
6. ○（`ii_lite_pass` 導出ロジックは整合）  
7. △（API 利用は妥当だが guard 前提を修正要）  
8. △（B/C wrong-stage など不足）  
9. ○（`capture_logs` 利用方針は妥当）  
10. △（key 欠損対応はあるが型不正ケース不足）  
11. ○（placeholder=0 方針は現段階で妥当）  
12. ✕（現案のままでは mypy/ruff 衝突リスクあり）

外部参照: https://arrow.apache.org/docs/python/generated/pyarrow.table.html