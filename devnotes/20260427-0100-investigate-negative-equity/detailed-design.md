# 詳細設計: negative equity / ストップアウト logic 調査

親: [conceptual-design.md](conceptual-design.md)

## 変更箇所

| ファイル | 変更 |
|---------|------|
| `scripts/alpha_factory/inspect_negative_equity.py` | 新規 CLI |
| `src/broker/mock.py` | ストップアウト logic 追加 (発見次第) |
| `src/backtest/engine.py` | margin level 監視を追加 (発見次第) |
| `tests/broker/test_mock.py` | ストップアウト発火テスト |
| `tests/backtest/test_engine.py` | margin call テスト |

## 調査手順

1. Run 19 ログ from `.cache/alpha_factory/runs/run_*.log` の invalid_equity_at_entry を集計
2. 該当 trade の position_id / entry_price / units / equity を再現
3. backtest engine と MockBroker の margin level 計算を trace
4. ストップアウト logic の存在 / 発火条件を verify

## DoD

- [ ] negative equity の物理的説明を特定
- [ ] bug の場合: ストップアウト logic 追加 + テスト
- [ ] production GA で再発しないことを Run 監視で確認
- [ ] Codex impl-review APPROVED
