# T071 詳細設計レビュー Round 1

## 0. 本レビューの前提 (C4)
- 前提1: レビュー対象は提示された詳細設計本文のみ（概念設計本文・T065-T068実装本体は未提示）。
- 前提2: 概念設計 Round 2 APPROVED は事実として受領し、詳細設計への展開妥当性を反証優先で確認。
- 前提3: C6準拠のため、各指摘は `Fact`（観察事実）と `Interpretation`（解釈）を同一行で明示。
- 前提4: C8準拠で、外部本文未提示の項目は INCONCLUSIVE として扱う。

## 1. 結論
[NEEDS_REVISION]

## 2. Critical (PR レベルで修正必須)
- [C1] Fact: §1.1 は「9 dataclass + 8関数」だが、§3 には dataclass が 11 個（`FailureMetricStage`/`FailureMetric`/`RunObservabilityReport`含む）、§4 は関数が 9 個（`build_run_observability_report`含む）。 Interpretation: SSOTの実装粒度が自己矛盾しており、DoDの達成判定が不可能。
- [C2] Fact: status契約を持つ3 metric（`ABDivergenceMetric`/`ArchiveChurnMetric`/`SessionEntropyMetric`）で、`status` と他フィールドの整合 invariant が未充足（例: `status!="ok"`時の sentinel強制、`status="ok"`時の必要条件、`n_unique_patterns`上限など）。 Interpretation: 「None排除」は達成しているが「status field方式の完全性」は未達。
- [C3] Fact: `compute_ab_divergence_on_b_evaluated` は `n>=2` で `status="ok"`になり、`recommend_q_force_adjust` がそのまま q_force を変更可能。 Interpretation: C7（小標本相関の扱い）に反し、過小サンプルで制御量を動かす経路が塞がれていない。
- [C4] Fact: `session_pass_pattern` の値契約が未確定（§11 open issue）かつ `compute_session_entropy` は任意文字列を集計。 Interpretation: 8パターン前提（3bit）と不整合の入力で `relative_entropy>1` または `__post_init__` 例外を誘発しうるため、PR即実装可能性を欠く。
- [C5] Fact: F1-F15の1:1対応を掲げる一方、F10/F11/F13/F14/F15は unit test 実体が弱い/不一致（特にF15は「delta適用順序」なのに境界振動テストへすり替わり）。 Interpretation: テスト計画のトレーサビリティが未完成で、欠陥混入時の検出保証が不足。

## 3. Warning (修正推奨)
- [W1] Fact: Pearson/entropy が `math.sqrt`/`math.log2` の float 経由。 Interpretation: 0.30/0.50境界付近で判定ぶれが起こる余地があり、ヒステリシス設計意図を弱める。
- [W2] Fact: hard dependency の検証が grep存在確認中心（§2）。 Interpretation: 「参照している」ことは検証できるが「意味的に正しく使っている」保証にならない（C1/C2観点で弱い）。
- [W3] Fact: fixture helper（`_make_admission` 等）が抽象パラメータ中心。 Interpretation: T065-T068 field rename をテストで早期検知しにくい。
- [W4] Fact: §1.3のPhase2申し送りと§9の8項目に差分がある。 Interpretation: 実施順序・責務境界の誤読リスクが残る。

## 4. Suggestion (詳細で考慮)
- [S1] `status`ごとの invariant を表形式で明文化し、`__post_init__` とテスト名を1:1リンクする。
- [S2] `AB` の actionable 条件を導入（例: `n_pairs < 10` は `insufficient_data` 固定、`n<30` は `warning` 付与）。
- [S3] `session_pass_pattern` を受信時に正規化/検証（3bit固定 or enum化）し、異常値は明示ステータスに落とす。
- [S4] F11用に「field存在」ではなく「抽出関数の期待値一致」テストを追加し、cross-PR伝搬漏れを検出する。

## 5. 強み (継続すべき設計判断)
- `compute_ab_divergence_on_b_evaluated` の命名で conditioning set を明示しており、C3対策の方向性は良い。
- q_forceのヒステリシス境界（`<0.30` raise / `>=0.50` restore）と clamp順序（delta後clamp）が明確。
- synthesis確定値とT071仮説値を定数グループで分離している点は監査可能性が高い。
- Phase 1（library）と Phase 2（run_ga配線）を分離した方針は妥当。

## 6. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- SSOT数（dataclass/関数）とDoD文言を一本化し、実装対象を確定する。
- 3 status metric の invariant を強化し、`status`と値の整合違反を全て `ValueError` 化する。
- AB相関の最小サンプル方針（少なくとも `n<10` 非アクション化）を仕様化し、F系列テストへ反映する。
- `session_pass_pattern` の表現契約をT064/T066と同期し、未定義入力経路を閉じる。
- F1-F15トレーサビリティ表を再作成し、各 failure に対応する unit/integration test_id を厳密に再配置する。