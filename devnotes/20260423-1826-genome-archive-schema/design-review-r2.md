**Verdict: NEEDS_REVISION**

1. **[重大] 主キー設計が multi-lane 前提と衝突しており、行衝突で archive が破損します。**  
現設計は内部キーを `(generation, individual_name)` に固定しています（[detailed-design.md:250](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:250), [detailed-design.md:257](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:257), [detailed-design.md:280](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:280)）。  
一方で swim-lane は「各 lane が独立して generation を進める」設計です（[swim-lane.md:24](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/swim-lane.md:24), [swim-lane.md:25](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/swim-lane.md:25)）。さらに現行 GA の個体名は `g{gen}_i{idx}` で lane 情報を含みません（[runner.py:169](/Users/ishitoya/repository/zenigame-fx/src/ga/runner.py:169), [runner.py:219](/Users/ishitoya/repository/zenigame-fx/src/ga/runner.py:219)）。  
この組み合わせだと、別 lane の同名個体が同一キーに衝突し、`collect_stage_*` の上書き/逆流 ignore 判定が別個体間で誤発火します。`mark_graduated` も lane を識別できません（[detailed-design.md:387](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:387)）。

2. **[中] `collect_stage_b/c` の `instrument` optional は「新規行作成時」に空文字を永続化しうるため、データ品質が落ちます。**  
`instrument=None` で新規 row を作ると `instrument=""` が保存される設計です（[detailed-design.md:306](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:306), [detailed-design.md:318](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:318), [detailed-design.md:349](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:349), [detailed-design.md:361](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1826-genome-archive-schema/detailed-design.md:361)）。  
仕様上 `instrument` は非 null の意味付き列なので、**新規作成時は必須**にした方が安全です。

**Round 1 指摘の4点（mypy/flushガード/テスト拡張/docs計画）は解消確認できています。**  
ただし上記 1 が blocking なので、このままは `APPROVED` にできません。