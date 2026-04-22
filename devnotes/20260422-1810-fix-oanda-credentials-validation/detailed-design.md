# 詳細設計: fix-oanda-credentials-validation

## 使命・制約

zenigame-fx 使命への直接寄与なし。テスト健全性の改善（運用基盤）。

## 変更ファイル

- `src/api/oanda/client.py` (L51-53)

## 現行コード（before）

```python
self._account_id = account_id or settings.oanda_account_id
self._base_url = base_url or settings.oanda_base_url
token = token or settings.oanda_api_token
```

## 変更後コード（after）

```python
# 明示的に渡された空文字列を settings へフォールスルーさせない（テストでも空文字を弾けるように）。
self._account_id = account_id if account_id is not None else settings.oanda_account_id
self._base_url = base_url if base_url is not None else settings.oanda_base_url
token = token if token is not None else settings.oanda_api_token
```

## テスト計画

- 既存 `tests/api/test_oanda_credentials.py` の 4 件すべて pass
- `tests/` 全体で regression なし

## リスク

- `OandaClient(token=None)` の呼び出しは引き続き settings から読む（後方互換性維持）
- 既存利用箇所（`scripts/oanda_ping.py` 等）は引数省略で呼んでいるため影響なし

## 完了報告

- 修正コミット: `c291a8e fix(api/oanda): preserve explicit empty-string args instead of falling through to settings`
- テスト結果: 296 passed / 3 skipped (T009 dsl 依存のみ)
- ruff / mypy: クリーン
- Codex 合議: スキップ（trivial fix のため maintenance commit として処理）
