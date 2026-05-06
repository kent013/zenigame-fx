**指摘事項（重大度順）**
1. [Critical] `run_ga` フック案は「機能が静かに無効化される」リスクがあります。  
[detailed-design.md:309](/Users/ishitoya/repository/zenigame-fx/devnotes/20260506-1345-fx-improve-c3/detailed-design.md:309) のコードは `pq.read_table(...)` を使いますが、現行 `run_ga.py` には `pyarrow.parquet as pq` import がありません（[run_ga.py:30](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:30) 以降）。さらに外側で `except Exception` を握るため、`NameError` でも fail-open で握りつぶされ、sidecar が永続的に出力されない可能性があります。  
修正案: `run_ga.py` に `import pyarrow.parquet as pq` を明示追加し、外側 `except Exception` は撤去または I/O/Arrow 系に限定（実装バグはテストで落とす）。

2. [Warning] `n_used` の意味が仕様記述と実装案で不一致です。  
仕様は「NaN 除外後件数」（[detailed-design.md:42](/Users/ishitoya/repository/zenigame-fx/devnotes/20260506-1345-fx-improve-c3/detailed-design.md:42)）ですが、実装案は `n_used = len(top)`（[detailed-design.md:70](/Users/ishitoya/repository/zenigame-fx/devnotes/20260506-1345-fx-improve-c3/detailed-design.md:70)）。  
修正案: `n_used` を `n_selected` に改名するか、`fold_sign_n_used` / `pfre_n_used` を別列で持つ。

3. [Warning] `fold_sign_positive_ratio` の定義が Stage B 契約とズレます。  
設計案は `>= 0.0`（[detailed-design.md:45](/Users/ishitoya/repository/zenigame-fx/devnotes/20260506-1345-fx-improve-c3/detailed-design.md:45)）ですが、Stage B は `> 0` で計算（[stage_gate.py:1181](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1181)）。  
修正案: `> 0.0` に合わせるか、列名を `fold_sign_non_negative_ratio` に変更して意味を分離。

4. [Warning] 「analyze-run から直接判定可能」という成功条件に対し、consumer 配線が未定義です。  
現行は `diagnostics_sidecar`（T033）だけを summary/report が読む実装（[run_ga.py:1056](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1056), [generate_run_report.py:671](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py:671), [analyze_run.py:105](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/analyze_run.py:105)）。  
修正案: summary に `diagnostics_stage_a_top_fold` を追加し、少なくとも report か analyze のどちらかで読めるようにする。

5. [Warning] テスト 7 件は基礎として良いですが回帰防止には不足です。  
修正案: `run_ga` 統合テスト（sidecar 生成/`--no-report` で未生成）と「archive 列欠落時の graceful handling」ケースを追加。

6. [Suggestion] `top_n = int(pop_n * 0.20)` は切り捨てなので小標本で意図より小さくなります。`ceil` の方が「上位20%」の意味に忠実です。  
7. [Suggestion] 性能見積りの行数は 5760 ではなく、実装ループ上は `generations+1` で 5856 行です（[run_ga.py:1167](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1167)）。

---

**施策別判定**
1. C1: `REQUEST_CHANGES`  
2. C2: `APPROVE`（調査ノートのみで妥当。`trade_count<50 でも stage_a_pass` は設計上あり得るため、調査価値あり。根拠: Stage A 判定は `min_exposure` と `fitness_pen threshold` で、live_criteria.trade_count_min は Stage C で適用 [stage_gate.py:835](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:835), [stage_gate.py:1492](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py:1492)）

**全体判定**
`CHANGES_REQUESTED`

---

**質問への回答**
1. 設計全体の妥当性: `REQUEST_CHANGES`（C1 の例外設計/配線不足を修正すれば妥当）。  
2. スキーマ18列の過不足: 概ね妥当。ただし `n_used` 定義を明確化すべき。  
3. NaN処理: top 群全員 NaN のとき、現案は集計値 `None` + `nan_ratio=1.0` で良い。ただし `n_used` の意味不一致は修正推奨。  
4. `Exception` 捕捉範囲: writer 側の fail-open は許容。`run_ga` 外側は広すぎるため限定推奨。  
5. テスト網羅性: 7件は不十分。統合2件＋欠落列1件は追加推奨。  
6. cycle3 原則（最小・観察のみ）整合: 整合しています。C1は Structural 介入として妥当。  
7. メタ過学習ガードの Structural 分類: 妥当です（評価ロジック不変更、post-RUN 観測追加のみ）。

---

**収束用（反証可能仮説 + 最小変更）**
1. 仮説: 現案のままだと sidecar が警告のみで未生成となる run が発生し、cycle 4 の反証データが欠落する。  
2. 最小変更: `run_ga` の C1 フックで「`pq` 明示 import + 外側例外捕捉の限定化（または撤去）」を行い、silent skip を防ぐ。