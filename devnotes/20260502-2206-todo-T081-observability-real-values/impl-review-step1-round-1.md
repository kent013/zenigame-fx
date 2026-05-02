**全体判定: CHANGES_REQUESTED**

[Critical] はありません。  
ただし、要件で明示された検証観点に対してテスト網羅の不足があるため `CHANGES_REQUESTED` です。

## 主要指摘（重大度順）

- [Warning] preflight不変性テストが「archive + diagnostics 両方」を検証できていません。  
  対象: [tests/alpha_factory/test_swim_lane.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_swim_lane.py)  
  `test_swim_lane_preflight_underfilled_does_not_skip_archive_collect_or_diagnostics_record` は `archive.collect_stage_b` の call count は見ていますが、`diagnostics.record_stage_b` 呼び出し確認がありません（テスト名・レビュー観点3とのズレ）。

- [Warning] `numbers.Real + bool除外` の実装はありますが、`bool`/`numpy scalar` の明示テストが不足しています。  
  対象: [tests/alpha_factory/test_swim_lane.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_swim_lane.py)  
  要件4で明示された `numpy.float32 / numpy.int64 / bool除外` の「テストでの担保」が不足。

- [Suggestion] `_aggregate_ab_summary` 側の防御は `isinstance(x, (int, float))` なので `bool` を通します。producer側で除外済みでも、consumer防御としては `and not isinstance(x, bool)` を揃えるとより堅牢です。  
  対象: [scripts/alpha_factory/run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py)

---

## ファイルごとの判定（Fact / Interpretation 分離）

### 1) [src/alpha_factory/observability/__init__.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/observability/__init__.py)
- 判定: **APPROVE**
- Fact:
  - `build_default_*` 9関数を import/export に追加。
- Interpretation:
  - 公開API拡張として設計意図（stub分解）と整合。循環 import を誘発する変更は見えない。

### 2) [src/alpha_factory/observability/run_metrics.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/observability/run_metrics.py)
- 判定: **APPROVE**
- Fact:
  - monolithic stub構築を9個の `build_default_*` に分離。
  - `build_stub_run_observability_report` はそれらを合成。
- Interpretation:
  - 設計§3.4.3（DRY化 + 互換維持）に整合。テスト（stub等価/JSON byte等価）も追加済み。

### 3) [src/alpha_factory/swim_lane.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/swim_lane.py)
- 判定: **APPROVE**
- Fact:
  - legacy / via_evaluator / noop の3経路すべてで必須4キーを返却。
  - preflight個体は `ab_excluded_preflight_count` 加算、AB pair収集のみskip。
  - `_collect_ab_pair` は `numbers.Real` + `bool除外` + `isfinite`。
- Interpretation:
  - 必須4キー伝搬、preflight不変性、NaN/Inf防御は実装として妥当。

### 4) [scripts/alpha_factory/run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py)
- 判定: **APPROVE**
- Fact:
  - `_aggregate_ab_summary` で run内集約（pairs/count/source）。
  - source mixing を `RuntimeError` fail-fast。
  - `Decimal(repr(...))` で A/B を分解し `compute_ab_divergence_on_b_evaluated` に入力。
  - `ab_score_source` は `"noop"` を固定化しない実装。
- Interpretation:
  - 設計§3.4.3の主要求件（list集約・mixing検出・実値配線）を満たす。
  - 追加のconsumer防御（bool拒否）は改善余地。

### 5) [tests/alpha_factory/test_swim_lane.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_swim_lane.py)
- 判定: **REQUEST_CHANGES**
- Fact:
  - 必須4キー、legacy/via parity、noop、preflight、numeric guard、NaN除外のテストは追加。
  - preflightテスト内で diagnostics 呼び出し確認が見当たらない。
- Interpretation:
  - 「archive collect / diagnostics record 不変性」のうち diagnostics 側の回帰検知が未担保。

### 6) [tests/alpha_factory/observability/test_run_metrics.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/observability/test_run_metrics.py)
- 判定: **APPROVE**
- Fact:
  - dataclass equality と JSON byte-for-byte equality の2テスト追加。
- Interpretation:
  - 設計上の互換性契約を直接検証しており適切。

### 7) [tests/alpha_factory/test_run_ga_observability_ab_divergence.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_run_ga_observability_ab_divergence.py)
- 判定: **APPROVE**
- Fact:
  - 集約helperに対して13ケース（mixing fail-fast, list衝突回避, n境界, zero variance 等）。
- Interpretation:
  - run_ga側のstep1要件をほぼ網羅。helper単体化のテスト戦略も妥当。

---

## 依頼10項目への回答

1. 設計一致性: **概ねYes**（提示サマリーとの整合は取れている）  
2. 必須4キー3経路一致: **Yes**  
3. preflight不変性: **実装はYes / テストは部分不足**（diagnostics検証欠落）  
4. numbers.Real + bool除外: **実装Yes / テスト不足**（bool・numpy明示不足）  
5. mixing RuntimeError + noop非固定: **Yes**  
6. stub byte-for-byte equality: **Yes**（追加テストあり）  
7. Decimal変換: **Yes**（`Decimal(repr(a))`）  
8. import経路/循環: **問題は見当たらず**  
9. regression 0: **提示結果ベースではYes**（本レビューでは再実行なし）  
10. 17ケース網羅: **概ね達成、ただし要件3/4の検証観点に補強余地あり**  

修正提案は2点です。  
1. preflightテストで `diagnostics.record_stage_b` の呼び出しをspyで明示検証。  
2. `bool` と `numpy.float32 / numpy.int64` のAB pair収集可否テストを追加。