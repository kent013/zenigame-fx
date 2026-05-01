## 前提
- 本レビューは、スレッド内で提示された要件文と self-report のみを根拠にした。`verified` 根拠: 「コマンド実行・ファイル書き込みは一切行わず」の制約が明示され、一次ソース本文の引用が未提示。
- C1 Design-first の必須一次証跡（設計本文と実装本文の突合）は未完了。`verified` 根拠: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T070-pr1/devnotes/20260430-1810-todo-T070-backtest-engine-extension/detailed-design.md) / [session_block.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T070-pr1/src/backtest/session_block.py) 等の本文をこの場で直接検証していない。
- self-report（test pass / grep網羅）は有用だが二次情報。`verified` 根拠: 実行ログ・差分本文・行番号証跡が未提示。

## Hypothesis 検証結果
H1 (aggregate_session_blocks SSOT 整合): **INCONCLUSIVE**  
根拠: 会計契約（§3.4.0）と実装行の突合が未実施。反証不能・確認不能。

H2 (Trade field 破壊変更なし): **INCONCLUSIVE**  
根拠: `Trade(` 呼び出し網羅は self-report のみ。実コードで全 caller（keyword-only/ラッパ経由含む）を一次確認していない。

H3 (cash 動作不変): **INCONCLUSIVE**  
根拠: `_close_one` 改造前後の cash 更新式と `pnl`/cost 転記経路を実装行で比較できていない。

H4 (transport SSOT): **INCONCLUSIVE**  
根拠: `run_backtest` 末尾呼び出し位置と caller 側再計算禁止の実効性をコード上で検証していない。

H5 (apply_spread_stress 代数): **INCONCLUSIVE**  
根拠: 提示された式そのものは代数的に妥当（multiplier=1で no-op）が、実装での入力検証（NaN/Inf/負値）と実際の return 値構築を未確認。

## 反証で発見された issue
- Critical: 一次証跡未確認のため、5仮説を監査基準（C1/C4）で確証できない。現時点で APPROVED 判定は不可。
- Warning: `apply_spread_stress` は契約上 caller 責務で再集計禁止としても、誤経路混入防止は docstring だけでは弱い可能性がある（型/フラグ/専用型での防御余地）。
- Warning: spread が異常値（負値/NaN/Inf）を取り得る入力源がある場合、会計契約を破る潜在経路になり得る。
- Suggestion: 会計契約と bucket 分割不変条件を property test 化し、`stressed trade を aggregate に渡すと失敗` を明示テスト化する。

## 最終判定
**NEEDS_REVISION**

修正必須項目:
- 一次証跡ベースで再レビュー可能な材料を提示（対象ファイルの該当実装行、または差分本文）。
- H1-H5 各仮説に対し、実装行とテスト行の対応表を提示（少なくとも会計契約・multiplier境界・caller網羅）。