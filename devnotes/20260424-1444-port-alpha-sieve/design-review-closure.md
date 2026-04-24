# Detailed Design Review Closure (Round 2 → 残対応)

## Round 2 NEEDS_REVISION 残対応マトリクス

| Round 2 指摘 | 対応内容 |
|--------------|----------|
| §5「既存モジュール再利用一覧」の DSR 行を Phase 2 方針に合わせて更新 | ✅ DSR (best-effort) 行を削除、`_compute_dsr_safe -> None` 固定の Phase 2 stub 行と、Phase 4 `deflated_sharpe_ratio` 接続経路の行に置換。YAML loader 行も追加 (`load_config + BacktestSectionConfig`) |
| §3.3 モック方針を §3.2 ケース14 (real backtest) と整合 | ✅ §3.3 を全面書き換え。各テストケースの方針を明示（ケース 14 は実 backtest 1 ケース実施、15 は早期 return、16 は DSR placeholder 直呼び、17-18 は tmp YAML + summary fixture） |

## 推奨事項

- `--strict-config-match` 引数による fail-fast オプション → 本 TODO スコープ外（Phase 4 で監査機構に組み込む別 TODO）。Phase 2 では WARN ログ + 実装記録のみ。

## 判定

**APPROVED-with-closure**: Round 2 で指摘された 2 修正要求はすべて反映済み。
本 closure 文書は監査可能性のため残し、実装フェーズへ進む。

## トレーサビリティ

- Round 1 結果: `codex-design-review-round-1.md` (NEEDS_REVISION × 2 修正)
- Round 1 → Round 2 対応: `.codex-prompt-design-review-round-2.md`
- Round 2 結果: `codex-design-review-round-2.md` (NEEDS_REVISION × 2 残整合)
- Round 2 → 本 closure: 本ファイル
