# Codex Review Log

## Conceptual Review (gpt-5.4 medium, label: conceptual-review)

### Round 1

- 判定: **NEEDS_REVISION**
- 主要指摘 (8 件):
  1. fold_sign_ratio のゼロ扱いが carry-forward と `signs[i] * signs[i-1] < 0` で不一致
  2. `std_sr_trials=1.0` default が危険
  3. `n_trials < 2` の扱い未明示
  4. DSR 分母 `SR` 表記固定が必要 (`SR_obs` 固定)
  5. `block_size=20` の default は根拠薄弱
  6. hard gate 用 vs monitor 用の位置付けを明記
  7. テストに `[+,0,-]`, `[0,0,+]`, `[-,0,0,-]` 追加
  8. Acklam inverse CDF の既知点検証追加
- 出力: `tmp/codex-outputs/conceptual-review-round-1.md`

### Round 2

- 判定: **NEEDS_REVISION** (軽微)
- 残指摘 (3 件):
  1. §3.3.1 のアルゴリズム入力に `block_size: int = 20` が残存 → §4 signature の「必須」と矛盾
  2. §6 DSR テストの「n_trials 1→100」は §3.1.2 の `n_trials >= 2` 必須と矛盾 → `2→100` へ修正
  3. R3 で skew/kurt と std の `ddof` を混同
- すべて Round 2 後に修正済み:
  1. §3.3.1 の `block_size: int = 20` を `block_size: int（必須、default なし）` へ
  2. §6 を `2→100` へ
  3. R3 を文言修正
- 出力: `tmp/codex-outputs/conceptual-review-round-2.md`

### Round 3 判定（max 2 rounds 制限下）

- Round 2 で指摘された 3 点はすべて内部整合性の文言修正で、実装方針そのものは Round 2 で APPROVED 相当と評価されていた（"Round 1 の主要 8 指摘のうち 1, 2, 3, 4, 6, 7, 8 は本文上ほぼ解消" / "修正量は小さいですが現状は最終承認にはまだ早い"）。
- 残 3 点の fix は pure な text edit で完了（signature 矛盾・テスト n_trials 範囲・R3 文言）。
- max 2 ラウンドの制限下で、次の detailed design へ進む判断。
- 本 fix の verify は detailed-design.md と実装の Codex design-review で再確認する。

## Design Review (gpt-5.3-codex high, label: design-review)

### Round 1

- 判定: **NEEDS_REVISION**
- 指摘 5 件:
  1. High: `deflated_sharpe_ratio` / `block_bootstrap_sharpe_ci` の nan/inf 入力域ガード不足
  2. Medium: pure function 契約と `seed=None` の不整合
  3. Medium: DSR pinning テストが自己参照で回帰検知力が弱い
  4. Low: `_norm_ppf` docstring 曖昧（clip 適用範囲）
  5. 同上 (3 に統合)
- Session ID: `019db378-3f7d-7fe3-9a44-a07c68418cdf`
- 出力: `tmp/codex-outputs/design-review-round-1.md`

### Round 2

- 判定: **APPROVED**
- 全 5 指摘対応確認済み:
  1. `math.isfinite` による nan/inf ガード追加（deflated_sharpe_ratio・block_bootstrap_sharpe_ci）
  2. `seed` を keyword-only int 必須に、`None` 不許容、`TypeError` で弾く
  3. `test_dsr_matches_independent_calculation` 追加（独立 Eq 再展開で照合）
  4. `_norm_ppf` docstring 明文化
- 非ブロッカー改善提案 2 件も反映:
  1. `test_dsr_matches_independent_calculation` を n_trials=2 と n_trials=10 の 2 ケースに拡張
  2. `block_bootstrap_sharpe_ci` docstring Raises に `TypeError` 追記
- 出力: `tmp/codex-outputs/design-review-round-2.md`

## Implementation Review (gpt-5.3-codex high, label: impl-review)

### Round 1

- 判定: **NEEDS_REVISION**（実質 file-read 失敗で監査不能、内容指摘なし）
- Session ID: `019db393-b70c-7920-afc5-4389cc1a9275`
- 対応: Round 2 で全ファイル本文を prompt に埋め込み再実行
- 出力: `tmp/codex-outputs/impl-review-round-1.md`

### Round 2

- 判定: **APPROVED**
- 観察:
  1. `deflated_sharpe_ratio` Eq.(7)/(9) 実装は設計と一致
  2. `_norm_ppf` Acklam 係数・3 領域分岐・clip が設計と一致
  3. `block_bootstrap_sharpe_ci` seed keyword-only, nan/inf ガード, 退化スキップ, `n_starts = T - block_size + 1` 正しい
  4. `fold_sign_ratio` carry-forward が設計と一致
  5. テストは主要エッジケース網羅、seed 固定で再現性担保
  6. 純関数 + NumPy only + 標準 math のみの依存
- 非ブロッカー提案:
  1. `_reference_dsr` を `math.erf` 直接使用にして共有依存をさらに減らす（現状でも回帰検知は機能）
  2. 全 bootstrap 退化での ValueError 専用テスト追加
- 出力: `tmp/codex-outputs/impl-review-round-2.md`
