## Verdict
NEEDS_REVISION

## 主要論点
- P1/P2/P3 を明文化した点と、`fx_rate_provider` を Phase 4 拡張点として命名予約した点は妥当です。
- ただし、追加予定の `scale sanity test` が現在の記述だと「スケール不変性」の反証テストになっていません（`nonzero/finite` と符号整合だけでは不足）。

## 必須修正（NEEDS_REVISION 時のみ）
- §9 受け入れ基準 2 の `scale sanity test` を、**同一 pair・同一価格系列**での Sharpe 不変性を直接検証する形に変更してください。  
  例: `initial_cash` を `C` と `k*C` に変えて実行し、`abs(sharpe_C - sharpe_kC) < ε` を assert（margin 制約が発火しないシナリオで）。
- 可能なら同テスト内で `units` も `U` と `k*U` で比較し、同様に Sharpe 不変性を確認してください（こちらも margin 非拘束条件を明示）。

## 推奨修正（任意）
- §8 に、Phase 4 時の契約を 1 行追加すると後退防止が強くなります。  
  例: `home_currency != quote_currency` かつ `fx_rate_provider is None` の場合は fail-fast を維持。

## 根拠
- Fact: 現在の追記検証は「Sharpe が有限であること」「P&L 符号が価格方向と一致すること」で、尺度変更時の同値性を直接検証していません。
- Interpretation: 論点 1 の必須修正（scale 不変性の明文化と検証追加）を満たすには、**尺度を実際に変えて Sharpe が不変であることを assert する**必要があります。
- Fact: `fx_rate_provider` の命名予約は将来拡張の入口として十分に有効です。