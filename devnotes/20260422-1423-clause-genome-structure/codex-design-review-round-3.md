## 各対応への評価（B1, B2, B3, Non-blocking 4/5）
- B1（H1再定義）  
Fact: 目標を「数式非等価」から「戦略挙動の非等価（entry/exit連関・hysteresis・time_stop・session close）」へ変更。  
Interpretation: 妥当です。T007 の目的として成立します。加えて「挙動非等価の受け入れ条件（観測可能な差分ケース）」を1つ明文化すると、後続レビューでブレません。

- B2（`_check_finite`）  
Fact: `SignalConfig.weight`（dir/gate）、`entry/exit_threshold`、`stop_atr/take_atr` に非有限値 reject を追加。  
Interpretation: 改善は大きいですが、**全経路を塞いではいません**。`ClauseConfig.weight` が未検証だと `compute_composite` で `NaN/inf` 伝搬が残ります。ここは Round 2 Blocker の趣旨上、未解消です。  
補足: H3 は「有限入力に限定」で SUPPORTED のままで問題ありません。

- B3（spread/swap 4段伝搬契約）  
Fact: `config -> GaConfig -> BacktestConfig -> MockBroker.submit/mark_to_market`、単位bps、適用時点、欠落時挙動を定義。  
Interpretation: 禁止事項 8 への対応として十分な粒度です。後続TODOで「必須化」の実装チェック項目（未設定時エラー化条件）だけ明示すれば完成度が上がります。

- Non-blocking 4（テスト追加）  
Fact: `θ_off` 等号 long/short、`enforce` 冪等、NaN/inf reject、`--collect-only` を追加。  
Interpretation: H4 は **SUPPORTED** に上げてよいです。

- Non-blocking 5（`params` defensive copy）  
Fact: `__post_init__` で `dict(self.params)` コピー。  
Interpretation: 共有参照対策として有効です（浅いコピーで十分なら妥当）。  

## 残存 Blocker（あれば）
1. **B2未完了**: `ClauseConfig.weight` の非有限値チェックが未記載。  
   - これが残ると `compute_composite` の `num/denom` に `NaN/inf` が入り得るため、Round 2 の「非有限値経路遮断」要件を満たしません。

## 判定: NEEDS_REVISION