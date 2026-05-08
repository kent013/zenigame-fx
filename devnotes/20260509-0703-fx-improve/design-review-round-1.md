**C9 Falsification-First（本ラウンドで絞る1仮説+1最小変更）**
- 反証仮説: 「`compute_reason_breakdown` は空実質理由（空白/改行のみ）を正しく無視し、`multi_reason` に空キーを作らない」
- 反証結果: 現行擬似コードは `"\n"` や `"   "` で `reasons=[]` になり、`else` 側で `"+".join([])==""` が計上されるため仮説は棄却
- 最小変更: `if len(reasons) == 0: continue` を追加（併せてこのケースのテスト1件追加）

**前提検証（C4）**
- Verified: T091(1-3) は Round5 APPROVED 済み、今回追加は C1.1/C1.2 と Run54 パラメータ。
- Verified: 追加監視キーは JSON の加算変更で、メモリ/保存量は軽微（60世代×3統計）。
- Unverified: `summary.json` consumer（run-report等）が厳密スキーマ検証かどうか、`max_cycle_seconds` 変更時の budget check 実装詳細。

**Fact / Interpretation（C6）**
- Fact: C1.1 擬似コードには `reasons=[]` 時の分岐がない。
- Interpretation: 実運用で空キー混入により失格理由集計が歪み、監視指標の解釈を誤るリスクがある。

---

### 施策別判定

| 施策 | 判定 |
|---|---|
| T091-施策1 (`stage_b_median_oos_sharpe_min` 0.025化) | APPROVE |
| T091-施策2 (`trade_count_full_dataset` 追加と伝搬) | APPROVE |
| T091-施策3 (partition guard + marker整合) | APPROVE |
| C1.1 失格理由分解ログ | REQUEST_CHANGES |
| C1.2 summary 5監視ポイント拡張 | APPROVE |
| Run54 パラメータ更新 | INCONCLUSIVE |

---

### 指摘（Critical/Warning/Suggestion）

- [Critical] C1.1: 空白/改行のみの `stage_b_reason_codes` で `multi_reason[""]` が発生。
  - 修正案: `reasons` 生成後に `if len(reasons) == 0: continue` を追加。
- [Warning] C1.1: `reasons_str.split(";")` は非文字列入力で例外化し得る。
  - 修正案: `isinstance(reasons_str, str)` を先に確認し、非文字列は skip（または明示的に文字列化ポリシーを固定）。
- [Warning] C1.2: `summary.json` の加算キーが strict consumer で後退を起こす可能性。
  - 修正案: consumer を「未知キー許容」に統一、または `summary_schema_version` を付与して分岐。
- [Suggestion] C1.1: `a;a` の重複コードを `set` で正規化すると、single/multi 判定のノイズを抑制可能。

---

### 質問への回答

- A. 流用妥当性: **概ね妥当（APPROVE）**。ただし監視テスト3件は十分ではなく、少なくとも「空白/改行のみ」「非文字列入力」「consumer後方互換」追加が必要。
- B. C1.1エッジケース: **現状不十分（REQUEST_CHANGES）**。NaNは処理できるが、空白/改行のみで空キー混入が起こる。
- C. C1.2命名/保存量/fixture: 命名は snake_case で妥当、保存量も軽微。fixtureは「世代欠損」「0件世代」「未知キー許容consumer」を含めると堅い。
- D. Run54パラメータ: `seed=100` 維持は因果同定の観点で妥当。`max_cycle_seconds` 変更の budget check 影響は実装未確認のため **INCONCLUSIVE**。
- E. 全体判定: **CHANGES_REQUESTED**（C1.1 の Critical 1点を先に是正すれば実装段階へ進行可能）。