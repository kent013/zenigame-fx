判定: NEEDS_REVISION

理由:
- 観測: `settings` をモジュール import 時に読み込み（§2.1）、一方でテストは `monkeypatch.setenv` で後から環境変数を設定（§3.3）。解釈: `BaseSettings` が import 時に確定する実装だと、テストの env 変更が反映されず不安定になります。
- 観測: `run_probe` は `OandaAuthError` のみ exit 1 扱い（§2.4）、`probe_one` の `HTTPStatusError` 分岐は 403/404 以外を `OTHER` に分類（§2.3）。解釈: 401 が `HTTPStatusError` として来た場合に abort せず継続する余地があり、401/403/404/5xx の扱い要件が実装契約に依存し過ぎています。
- 観測: `probed_at` は `datetime` のまま `_write_json` に渡される（§2.4）。解釈: JSON 化時に ISO 文字列化を明示しないと `TypeError` のリスクがあります。
- 観測: 認証失敗テストは 1 instrument のみ（§3.2-5）。解釈: 「途中で 401 が出たら即 abort（後続未実行・ファイル未生成）」の重要挙動を十分に担保できていません。
- 観測: mock 設計に OANDA 実レスポンス形状（特に 200 の `candles` 構造）の具体定義がない（§3）。解釈: `OandaClient` の実パース経路と乖離したテストになる可能性があります。

修正提案（NEEDS_REVISION の場合のみ）:
- ファイル: `scripts/oanda_cfd_probe.py` の §2.1  
  指摘: `settings` の import 時評価と `monkeypatch.setenv` の整合が弱い。  
  提案: `settings` 直参照を減らし、`run_probe` に `account_id/token/base_url` を注入可能にするか、実行時に設定を再解決する設計へ変更。
- ファイル: `scripts/oanda_cfd_probe.py` の §2.3/§2.4  
  指摘: 401 の扱いが `OandaClient` 実装契約に依存。  
  提案: `HTTPStatusError` で `status_code==401` を明示的に fatal 扱い（`OandaAuthError` へ変換または再送出）し、403/404/5xx との優先順を仕様として固定。
- ファイル: `scripts/oanda_cfd_probe.py` の §2.4  
  指摘: `datetime` の JSON serialize 方針が未明示。  
  提案: `_write_json` に渡す前に `probed_at.isoformat()` へ正規化し、dataclass の出力型を `str/int/None` に限定。
- ファイル: `tests/scripts/test_oanda_cfd_probe.py` の §3.2-5  
  指摘: 途中 abort ケース未検証。  
  提案: 「1件目OK、2件目401、3件目未実行」を追加し、exit=1・出力未生成・HTTP 呼び出し回数で abort を検証。
- ファイル: `tests/scripts/test_oanda_cfd_probe.py` の §3 全体  
  指摘: mock の現実整合性が不足。  
  提案: 200 は実 OANDA 形式に合わせた `candles` payload（`time`, `bid/ask`, `complete` 等）を fixture 化し、403/404/401/5xx も実際のエラー JSON 形状に寄せる。
- ファイル: `docs/alpha_factory/runbook.md` と `docs/alpha_factory/cross-pair.md` の §4  
  指摘: 実装仕様との同期条件が未明示。  
  提案: `401=fatal(即終了) / 403=FORBIDDEN / 404=NOT_FOUND / 5xx=OTHER` を明文化し、スクリプト仕様と完全一致させる。