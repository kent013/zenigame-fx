**指摘事項（Falsification-first）**

1. [Critical] fingerprint に false negative があります。  
事実: `_build_clause_fingerprint` は `(sig.name, cache_key)` のフラット列のみで、`directional/local_gate` 境界と `weight` を含みません（[detailed-design.md:219](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0256-strategy-signal-cache-flatten/detailed-design.md:219), [detailed-design.md:232](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0256-strategy-signal-cache-flatten/detailed-design.md:232), [composite.py:37](/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py:37), [composite.py:100](/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py:100)）。  
解釈: `directional↔local_gate` 再配置や `directional/clause weight` 変更を検出できない組合せが残ります。  
修正案: fingerprint を `((clause.weight, directional[(name,weight,key)...], local_gate[(name,weight,key)...]), ...)` に変更し、境界と重みを含めて比較してください。

2. [Critical] `on_bar` 毎の fingerprint 再構築は hot path 最適化と衝突します。  
事実: `on_bar` 冒頭で毎バー `_build_clause_fingerprint(self._genome)` を実行しています（[detailed-design.md:330](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0256-strategy-signal-cache-flatten/detailed-design.md:330)）。  
解釈: O(clause×sig) 走査を再導入し、`_signal_cache_key` 排除メリットを相殺する恐れがあります。  
修正案: hot path は O(1) の `id(self._genome)` チェックにし、重い整合チェックは `prepare()` 時または debug 限定（初回バーのみ）に落としてください。

3. [Warning] `_assert_unique_name` は unprepared 経路を守れていません。  
事実: `evaluate_all_bars` 非対応 evaluator では `prepare` が return し、重複検証が走りません（[detailed-design.md:286](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0256-strategy-signal-cache-flatten/detailed-design.md:286)）。unprepared 側は `vals[sig.name]` 後勝ち上書きです（[detailed-design.md:363](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0256-strategy-signal-cache-flatten/detailed-design.md:363)）。  
修正案: `__init__` で clause 内 name 一意性を必ず検証し、prepare 有無に依存させないでください。

4. [Warning] テスト計画が critical 反証ケースを未カバーです。  
修正案: 少なくとも以下を追加してください。  
- `directional/local_gate` 境界変更で fingerprint mismatch になるテスト  
- `directional weight` / `clause weight` 変更検出テスト  
- `NaN/inf` 入力時の prepared path 挙動回帰テスト

5. [Warning] 新規テスト案は lint 不合格リスクがあります。  
事実: `import numpy as np` 未使用、1行 `def` が複数あります（[detailed-design.md:456](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0256-strategy-signal-cache-flatten/detailed-design.md:456), [detailed-design.md:619](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0256-strategy-signal-cache-flatten/detailed-design.md:619)）。  
修正案: 未使用 import を削除し、1行 `def` を通常ブロックへ分解してください。

6. [Suggestion] registry は global なので新規テストにも isolation fixture を入れる方が安全です。  
修正案: テストファイルに `autouse` で `clear(); ensure_registered(); yield; clear()` を追加してください。

---

**施策ごとの判定**

- 施策1 (`src/dsl/strategy.py`): **REQUEST_CHANGES**  
- 施策2 (`tests/dsl/test_dsl_strategy_flat_cache.py`): **REQUEST_CHANGES**  
- 施策3 (`tests/backtest/test_engine_prepare.py` 追従): **APPROVE**

---

**観点 9-14 を含む要約**

- ルックアヘッドバイアス: **APPROVE**（primitive 未変更。既存 look-ahead テスト群は妥当）  
- メモリ制約: **APPROVE**（配列本体は据え置き、追加は参照構造中心）  
- パフォーマンス: **INCONCLUSIVE**（実測未提示。毎バー fingerprint のままでは悪化リスク）  
- 前提検証(C4): **一部未閉塞**（P11 は実装依存、さらに false negative 対応が必要）  
- 並行計算経路(C2): **Warning**（prepared/unprepared で name 重複防御が非対称）  
- collider bias(C3/C7): **Suggestion**（性能比較は「同一母集団・同一seed」で。n<30 は因果主張禁止）

---

**全体判定**

**CHANGES_REQUESTED**

補足: 実行環境制約（read-only + 実行依存不足）によりテスト/ベンチ実行はしていません。