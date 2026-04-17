# zenigame-fx - FX 取引システム

## 概要

FX（外国為替）取引を対象としたデータ収集・シグナル生成・自動売買システム。

姉妹プロジェクト [zenigame](../zenigame)（日本株予測システム）の設計思想を参考に、FX 向けに独立して構築する。コードは共有しない。

## 現状

Phase 0〜4g 実装済み。OANDA demo 口座のクレデンシャル到着後に稼働検証を予定。

| Phase | 内容 | 状態 |
|-------|------|------|
| 0 | プロジェクト骨格（uv / PostgreSQL / Alembic / OANDA client skeleton） | ✓ |
| 1 | OANDA ヒストリカル/インクリメンタル取得 + diskcache | ✓ |
| 2 | MockBroker + 単一戦略バックテスト + MD/JSON レポート | ✓ |
| 3 | Paper Trading orchestrator（Replay / Live） + graceful shutdown | ✓ |
| 4a | Strategy Registry + 3 戦略追加 + Grid Search | ✓ |
| 4b | Walk-Forward validation | ✓ |
| 4c | Sharpe / Sortino / Calmar / trade duration | ✓ |
| 4d | Strategy ensemble + correlation | ✓ |
| 4e | 経済指標カレンダー基盤 + EventAware wrapper | ✓ |
| 4f | DSL expression trees + DslStrategy | ✓ |
| 4g | 最小 GA（DSL ゲノム進化） | ✓ |

**テスト**: 104/104 pass / **Lint**: ruff clean / **型**: mypy（warning only）

詳細は [docs/runbook.md](docs/runbook.md) を参照。

## クイックスタート

```bash
# 1. 初期セットアップ
bash scripts/init.sh

# 2. .env に OANDA の認証情報をセット
cp .env.example .env
$EDITOR .env
# OANDA_ACCOUNT_ID / OANDA_API_TOKEN を記入

# 3. 疎通確認 + USD_JPY を DB に投入
uv run python scripts/oanda_ping.py

# 4. ヒストリカル取得（1 日分で疎通確認）
uv run python scripts/fetch_historical.py --instrument USD_JPY --days 1

# 5. バックテスト
uv run python scripts/backtest_run.py \
    --instrument USD_JPY \
    --from 2026-04-01 --to 2026-04-15 \
    --leverage 10 --strategy bollinger
```

## 短期目標

zenigame を参考に、FX 取引を実行する仕組みの骨格を実装する（達成）。

## 技術スタック

- Python 3.11+ / uv
- PostgreSQL 16（価格・ニュース・メタデータ）
- SQLAlchemy 2.0 + Alembic
- httpx + tenacity（OANDA v20 API クライアント）
- pydantic v2 + pydantic-settings
- diskcache（HTTP レスポンス）
- structlog
- pytest + respx + testcontainers

## フェーズ構成（今後の予定）

| Phase | 内容 |
|-------|------|
| 5 | Live Trading（実ブローカー接続・リスクガード・監視） |
| 4h+ | NSGA-II 多目的、ゲノムアーカイブ、Stage Gate、LLM 変異（必要に応じて） |

## ディレクトリ構成

```
src/
├── api/             # OANDA v20 クライアント + HTTP キャッシュ
├── backtest/        # エンジン / Grid Search / Walk-Forward / Ensemble / 指標 / レポート
├── broker/          # BrokerGateway Protocol / MockBroker / 証拠金ロジック
├── db/              # SQLAlchemy モデル + Alembic マイグレーション
├── domain/          # 通貨ペア / PriceBar
├── dsl/             # 式木 AST / evaluator / Genome / DslStrategy
├── events/          # 経済指標カレンダー
├── ga/              # ランダム生成 / crossover / mutation / GA ループ
├── ingest/          # OANDA データ取り込み
├── paper_trading/   # Orchestrator / BarFeed / EventLogger
├── strategy/        # Bollinger / MA Crossover / RSI / Donchian / EventAware
└── utils/           # 時刻ユーティリティ
scripts/             # CLI ランナー一式
tests/               # pytest
devnotes/            # 設計文書（各 phase の詳細設計）
reports/             # 実行結果の出力先（.gitignore）
```

## ドキュメント

- [AGENTS.md](AGENTS.md): プロジェクト方針・開発ルール
- [docs/runbook.md](docs/runbook.md): CLI コマンド一覧・推奨フロー
- [devnotes/](devnotes/): 各 Phase の詳細設計
