## Verdict
NEEDS_REVISION

## 前提 (C4)
- 本レビュー対象は、提示された「詳細設計本文」断片のみ（`smoke.py` 実装・テスト実コードは未読）。
- Round 1 falsification-first として、まず「概念 Round 4 SSOT と矛盾する/未固定の点」を優先抽出した。
- C1 Design-first: 判定根拠は SSOT 15項目と詳細設計本文の対応関係に限定。
- C6 Fact/Interpretation 分離: 各指摘で事実と解釈を分離して記述。
- C7 Sample size: 統計相関の論点は本レビュー範囲外（n/a）。
- C8 INCONCLUSIVE: 本文に未記載の箇所は「不明」として扱い、断定を避けた。

## Critical
- [C1] Fact: 必須観点 9 の `SmokeOutcomeClassification.overall_severity == aggregate_evidence.severity` の invariant が本文で明示されておらず、対応テストIDも見当たらない。Interpretation: classify結果と集約結果の不整合を実行時に検出できず、SSOT逸脱リスクが高い。
- [C2] Fact: dual-path enforce は「AST + yaml parse + substring match 混在」までで、対象ファイル境界・正規化・parser失敗時動作・allowlist glob の厳密仕様が未固定。Interpretation: 検出漏れ/誤検出が起きると「値伝搬漏れ禁止」に直結するため、現時点では安全性要件を満たしたとは言えない。

## Warning
- [W1] Fact: `change_group_id` regex は `^T075-[a-z_]+-[a-z0-9_]+$` で妥当だが、`{category}` の語彙SSOT（cleanup/config/script 等）が未固定。Interpretation: チーム運用で category がドリフトしやすい。
- [W2] Fact: `InconclusiveReason` 集約 dedup が `source + reason_code` 単位。Interpretation: 異なる `message` が落ちるため、診断情報が痩せる可能性がある。
- [W3] Fact: `review_hint` の「no_blocker_observedでも承認必須」は dataclass docstring 記述のみで、runbook反映/検証テストの所在が不明。Interpretation: “hint only” 運用が将来崩れる余地がある。
- [W4] Fact: Round 4 [S4] の「Round 22 blockers listed」は unit test で直接検証しにくいが、検証方法が詳細化されていない。Interpretation: merge gate が形骸化しやすい。
- [W5] Fact: EvidenceClassifierProtocol conformance は方針良いが、fixtureで「unsupported→inconclusive」をどう強制するかの実装契約（失敗時メッセージ/assert粒度）が未記述。Interpretation: 互換性テストの再現性が落ちる。

## Suggestion
- [S1] `SmokeOutcomeClassification` に `__post_init__` 明記と負ケーステスト（不一致で `ValueError`）を追加。
- [S2] `change_group_id` の `{category}` を `Literal` か定数集合で固定し、regexと二重化して運用事故を防ぐ。
- [S3] dedup 方針を `source+reason_code+message` か、「同キー内 message 複数保持」に変更して監査可能性を確保。
- [S4] dual-path enforce は「対象パス」「allowlist glob」「parser失敗時 fail-closed/fail-open」を表で固定し、境界テストを増やす。
- [S5] [S4] merge条件のうち非コード項目（blockers listed）は CI のメタ検証（PRテンプレ必須項目チェック）に分離。

## test_id 1:1 ギャップ
- F26-F30: `decide_release_action` 優先順位はあるが、`SmokeOutcomeClassification` invariant 不一致検出ケースが未割当。
- F34-F38: dual-path enforce の allowlist 境界（`docs/historical` は許可、`docs/runbook` は警告対象）の厳密な正負ケースが不足気味。
- F31-F33: Phase1防御は十分だが、「将来誤って呼ばれた時の上位ハンドリング方針」テストがない。
- F39-F40: `schema_version/runs count` はあるが、`review_hint` の authority 分離（hint only）を保証するテストが未見。
- （新規追加推奨）F41相当: Round 22 blockers listed を CI/PRメタで機械検証。

## 学術文献 (任意)
- なし（本件は設計整合性レビューであり、因果推論・統計主張なし）。

## 総評
SSOTへの追従度は高く、特に `classify/decide` 分離、`inconclusive` 別軸保持、Phase1での `NotImplementedError` 防御は設計意図と整合しています。一方で、sanity check としては「不整合を機械的に止める invariant」と「dual-path enforce の仕様固定」がまだ弱く、ここが現状の主なリスクです。

したがって判定は `NEEDS_REVISION` です。上記 Critical 2点を先に潰せば、Round 4 APPROVED の内容を詳細設計として実装可能な粒度に落とし込めます。