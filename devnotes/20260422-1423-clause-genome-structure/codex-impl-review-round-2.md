## 各レビュー項目への所見（1〜8、Fact/Interpretation 分離）

1. 実装と詳細設計の乖離  
Fact: `genome/composite/enforce/strategy/serialize` は Clause 構造・合成式・ヒステリシス・整合性適用の流れで一貫しています。  
Interpretation: 詳細設計本文（§2-7）が未提示のため厳密突合は限定的ですが、実装意図は設計要旨と整合していると判断します。

2. テストの完全性  
Fact: `composite/enforce/strategy/genome` の主要境界（空入力、len不一致、clip、swap、NaN/Inf reject、θ_on/θ_off境界、time_stop/session close）は実装済みです。  
Interpretation: 十分に厚いですが、短期保有の「保持領域（例: composite=-0.2）」明示テストは追加余地があります。

3. コード品質  
Fact: Python 3.11+ の型注釈、docstring、責務分離は良好です。`Protocol` 利用も適切です。  
Interpretation: 可読性・保守性は高く、T007スコープとして問題ありません。

4. 既存コードへの影響範囲（`src/ga/fitness.py`）  
Fact: `DslStrategy(genome)` 呼び出しは新シグネチャ（evaluator必須）と不整合で、現状は `except` で失敗fitness返却になります。  
Interpretation: 「最小diffで次TODOへ橋渡し」という意図は理解可能ですが、呼ばれた際に静かに劣化する点は運用リスクです。

5. ヒステリシス実装（`>=` / `<`）  
Fact: `on_bar` は entryで `>=`、exitで `<` を実装し、長短両方の等号境界テストがあります。  
Interpretation: 仕様どおりに動く実装です。

6. `enforce_consistency` の冪等性  
Fact: 正規化処理（abs+clip、dedupe、max1 gate、threshold整形、ATR下限）後に再適用で不変となる構造で、専用テストもあります。  
Interpretation: 有限値入力前提では `f(f(x)) == f(x)` は成立すると判断します。

7. `PrimitiveEvaluator Protocol` の切れ味  
Fact: `runtime_checkable` は付与されていません。実装側は duck typing 前提です。  
Interpretation: 現状用途（静的契約）では妥当です。`isinstance(x, PrimitiveEvaluator)` を将来使うなら付与が必要です。

8. defensive copy（`SignalConfig.__post_init__`）  
Fact: frozen dataclassで `object.__setattr__` + `dict(self.params)` を使っています。  
Interpretation: Pythonの慣用として適切です（外部参照遮断を満たす）。

## Falsification 結果（F1〜F4）

- F1: 反証失敗（= 非冪等ケースは確認できず）。有限値前提では冪等。  
- F2: 反証成功（= 「現実的に1e-9超過」が起きる可能性は低い）。値域・演算回数から `1e-9` は十分保守的。  
- F3: 部分反証。長短の等号境界は両側テスト済みで主要非対称は抑制。ただし短側の保持領域明示テストは未追加。  
- F4: 提示されたgrep結果ベースでは反証成功（残存importなし）。ただし本レビューでは独立再実行は未実施。

## 致命的指摘 (Blockers)

- なし。

## 改善提案 (Non-blocking)

1. `src/ga/fitness.py` は暫定期間だけでも「明示的に未対応をraise」へ変更し、静かな劣化（全個体失敗fitness）を防ぐ。  
2. `tests/dsl/test_strategy.py` に short保持領域（例: `composite=-0.2`）の明示ケースを1本追加。  
3. `tests/dsl/test_enforce.py` に冪等性の追加ケース（複数clause・同率|weight|含む）を増やす。

## 判定

APPROVED_WITH_COMMENTS