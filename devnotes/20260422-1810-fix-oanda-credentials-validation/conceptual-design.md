# 概念設計: fix-oanda-credentials-validation

## 背景・課題

audit-cycle-5（`devnotes/20260422-1308-audit-cycle-5/`）で `tests/api/test_oanda_credentials.py` の 2 件失敗を検出:
- `test_empty_api_token_raises`: 空文字列 token で ValueError が発生せず
- `test_empty_account_id_raises`: 空文字列 account_id で ValueError が発生せず

原因: `OandaClient.__init__` で `account_id or settings.oanda_account_id` という `or` パターンを使用しており、空文字 (`""`) は falsy なため `settings` の実値（`.env` から）にフォールスルーしていた。

## 改善アイデア

`X or fallback` を `X if X is not None else fallback` に変更し、明示的に渡された空文字を保持する。バリデーションロジック（`if not (X or "").strip()`）は変更せず、入力側で正しく空文字を伝播させる。

## 期待効果

- 既存 2 fail テストが通る
- 動作上のセマンティクスは「設定不在で 401 になる前に明示エラー」で変わらない
- live_criteria への直接的影響はないが、テスト網羅率が向上し開発信頼性に寄与

## スコープ外

- Settings 全体のバリデーション強化（field_validator 追加等）は別 TODO

## 補足

本 TODO は autopilot サイクル 9 (T009 backtest 統合) と並行して実施した小規模 fix（src/api/oanda/client.py のみ、3 行変更）。autopilot の正規 cycle ではなく maintenance commit として直接コミット。

- 修正コミット: `c291a8e`
- 検証: 296 passed / 3 skipped (T009 で解除予定の dsl 関連 3 件のみ)
