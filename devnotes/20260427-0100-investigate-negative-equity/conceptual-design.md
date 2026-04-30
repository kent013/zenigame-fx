# 概念設計: negative equity warnings 調査 + ストップアウト logic

**起点監査**: [audit-codex.md §2 (7)](../20260427-0050-bug-hunt-audit/audit-codex.md) — P1 候補 INCONCLUSIVE

## 仮説

Run 19 で `trade_return.invalid_equity_at_entry equity_at_entry=-3,082,830` warning が 10,165/14,107 件発生。leverage 25x + units 10000 + 短期間多取引で margin 完全壊滅し equity が大幅 negative になっている。MockBroker / backtest engine にストップアウト logic が無い、または有っても発火していない。

## 検証済み事実

- Run 19 ログで invalid_equity_at_entry 警告 10k+ 件
- [backtest/metrics.py:67-90](../../src/backtest/metrics.py#L67-L90), [broker/mock.py:199-224](../../src/broker/mock.py#L199-L224) で equity 計算
- production live では絶対に許容できない (= 破産)、bug 候補 P1

## 解決方針

調査:
1. Run 19 ログから invalid_equity_at_entry の trade_position_id を抽出
2. 該当 trade の (entry_price, units, equity_before, margin) を再現
3. 25x レバレッジで cash 1M JPY、units 10000 EUR_JPY (≈ 1.65M position value) → margin = 1.65M / 25 = 66k
4. cash > margin であれば理論上 OK。しかし position 同時保有 100+ 件で破産?
5. MockBroker / backtest engine のストップアウト logic の有無を line-by-line 確認

修正方針:
- ストップアウト logic 不在 → 追加 (margin level 100% 割れで強制 close)
- 有るが発火していない → 修正

## 成功判定

- negative equity が発生する条件を特定
- production GA で同事象が再発しない設計
- 既存テスト全 pass + ストップアウト発火テスト追加
