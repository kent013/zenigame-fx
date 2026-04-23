**主要所見（Severity順）**

1. **型安全性の不整合が残っています（Must-fix未解消）**  
参照: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-1423-primitives-pair-specific/conceptual-design.md)（L1, L2）  
- Fact: `aux_pair_bars` は `Mapping[str, Sequence[PriceBar]]` と定義しつつ、L2 で stale 時に `aux_pair_bars[k][i] is None` を許容しています。  
- Interpretation: `PriceBar` 配列契約と `None` 混在契約が衝突しており、type-safe 設計という目的に未到達です。  
- Must-fix: `Sequence[PriceBar | None]` へ明示変更するか、`None` を使わず stale を別マスク/メタで表現するかを一本化してください。

2. **欠損・stale時の挙動規約が二重化しています（Must-fix未解消）**  
参照: 同ファイル（L6, L10, テスト戦略）  
- Fact: L6 は directional 欠損時 `warning + 0.0`、L10 は stale 時 `NaN`、テスト戦略には欠損時 `0.0` 検証が中心で stale と整合する期待値が未統一です。  
- Interpretation: 同じ「auxが使えない」状態で `0.0` と `NaN` が混在し、取引回数・fitness への影響が実装依存になります。  
- Must-fix: 「missing key」「stale value」「misalignment」の3状態ごとに戻り値と strict 時挙動を明文化し、テスト期待値を一致させてください。

3. **`strict_aux_required` の検証対象定義が曖昧です（Must-fix未解消）**  
参照: 同ファイル（L6, EvaluationContext 注入経路）  
- Fact: `selected signal の required_data を preflight verify` とありますが、`selected` の確定タイミング/API が未定義です。  
- Interpretation: evaluator 初期化時に何を検証するか曖昧だと、fail-fast が形骸化し `warning + safe default` に戻るリスクがあります。  
- Must-fix: `selected primitive ids` を `RegistryEvaluator` に明示入力する等、preflight の入力境界を設計に追加してください。

---

**解消を確認できた点**

- P10 rename と役割整合（Surprise→Proximity）は妥当。  
- P5 の自然符号を mean-revert に揃えた点は妥当。  
- P7/P11 の staleness cap 必須化は前進。  
- `_REQUIRED_DATA_LITERALS` 同期更新を DoD に明記した点は妥当。  
- `strict_aux_required=True` を production 規約にした方向性は正しい。

---

**前提チェック（C4/C6/C8）**

- Verified: ドキュメント内の仕様整合性レビュー。  
- INCONCLUSIVE: 実コードでの validator 影響、GA実行時の `selected` 決定フロー、実運用での trade_count 影響（データ未提示）。  
- 解釈と事実は上記で分離済み。

**結論: NEEDS_REVISION**