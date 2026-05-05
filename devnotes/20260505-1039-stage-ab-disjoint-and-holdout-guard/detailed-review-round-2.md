**本分析の前提**
- 提示された Round 2 詳細設計全文のみをレビュー対象とした。検証状態: Verified
- 実コード・docs・git履歴・既存テストの実体照合は未実施。検証状態: Unverified
- Round 1 指摘への設計上の解消可否を主眼に判定する。検証状態: Verified
- 相関・予測性能 claim は今回ほぼ無いため、C3/C7 は主に「該当なし」と扱う。検証状態: Verified

**結論**
- 全体判定: **CHANGES_REQUESTED**
- Round 1 の Critical 2件は、方向性としてはほぼ解消しています。
- ただし Round 2 で新たに「summary-only flag と run report の参照元不整合」「version bump の実装順序」「`n_fold_effective` 型判定」の3点が残っています。
- 大きな設計方針、特に Stage C fallback 廃止は妥当です。guard bypass より fail-closed の方が使命・制約に合います。

**主要指摘**
- [Warning] `stage_b_statistical_inconclusive` を archive 非保持にする方針と、run report の `best_row.get("stage_b_statistical_inconclusive")` が不整合です。  
  Facts: 施策5では archive parquet に列を増やさないと明記しています。一方、施策8では `best_row.get("stage_b_statistical_inconclusive", False)` を参照しています。  
  Interpretation: `best_row` が archive row 由来なら flag は常に存在せず、report 表示が欠落します。  
  修正案: report 側は `stage_b_statistical_inconclusive` が無い場合に `n_fold_effective` から `_is_stage_b_inconclusive()` で導出する、と明記してください。

- [Warning] `STAGE_GATE_VERSION` bump を Step 1 単独 commit にする実装順序は危険です。  
  Facts: Step 1 で version だけ `v4_stage_b_disjoint` に変え、disjoint 化・guard は後続です。  
  Interpretation: 中間状態で GA を実行すると、実態は v3 相当なのに v4 metadata/history が残る可能性があります。  
  修正案: 施策7は施策1〜3と同一 commit、少なくとも disjoint 化と guard 呼び出し後に適用してください。

- [Warning] `_is_stage_b_inconclusive()` の `isinstance(n, int)` は `numpy.integer` を誤って inconclusive 扱いにします。  
  Facts: 前提環境に numpy/pandas があり、parquet/pandas 経由では `np.int64` が入り得ます。  
  Interpretation: `n_fold_effective=3` でも `np.int64(3)` なら True になり、report/summary が保守的すぎる誤判定になります。  
  修正案: `numbers.Integral` を使い、`bool` は除外する実装にしてください。NaN/float/None は True でよいです。

- [Warning] `stage_a_n_bars == len(bars_stage_b_full)` の扱いが設計文とテスト名でズレています。  
  Facts: コード案は `>` で dataset too short を判定し、その後 `bars_stage_b` empty で別 RuntimeError になります。テスト計画は `>= len(full)` で dataset too short と書いています。  
  Interpretation: 挙動は fail-closed ですが、期待エラー種別・メッセージが曖昧です。  
  修正案: `if stage_a_n_bars >= len(bars_stage_b_full):` にして、1箇所で明示的に落としてください。

- [Suggestion] `allow_stage_c_fallback_slice` の grep 対象は `tests/` だけでなく repo 全体に広げるべきです。  
  修正案: C1追加チェックを `git grep -n "allow_stage_c_fallback_slice" -- .` に変更し、`config/`, `docs/`, `.claude/skills/`, `devnotes/` の残存も確認してください。

**確認事項への回答**
- 1. Round 1 Critical 2件: **概ね解消**。fallback 廃止は妥当です。guard bypass は設計負債になるため避けるべきです。
- 2. summary/archive 責務分離: **方針は妥当**。ただし report/consumer は archive row から `n_fold_effective` で再導出する契約に修正が必要です。
- 3. `bars` 据え置き + `bars_dataset_total`: **冗長だが許容**。移行期の明示 key として有効です。
- 4. parquet metadata merge: **pyarrow API 方針は妥当**。ただし metadata 生成を helper 化し、既存 key preservation test を可能にするとよいです。
- 5. APPROVE可能水準: **あと一歩**。上記 Warning 3点を設計に反映すれば APPROVE 可能です。

**施策別判定**
- 施策1 `_load_lane_bars` disjoint化: **REQUEST_CHANGES**。`>=` 判定と holdout missing の順序明確化が必要。
- 施策2 `stage_partition_guard.py`: **APPROVE**。`bar_time is None` 明示チェックと未使用 import 削除は実装時に対応推奨。
- 施策3 guard呼び出し + fallback廃止: **APPROVE**。fail-closed 方針は正しい。
- 施策4 `bars_18m -> bars_stage_b`: **APPROVE**。
- 施策5 summaryフラグ追加: **REQUEST_CHANGES**。`np.integer` 対応と report 参照元の整合が必要。
- 施策6 archive metadata追加: **APPROVE**。helper化するとより安全。
- 施策7 version bump: **REQUEST_CHANGES**。単独先行 commit は避ける。
- 施策8 run report注記: **REQUEST_CHANGES**。summary flag 不在時に `n_fold_effective` から導出すること。
- 施策9 structured log test: **APPROVE**。