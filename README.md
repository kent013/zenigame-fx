# zenigame-fx - FX 取引システム

## 概要

FX（外国為替）取引を対象としたデータ収集・シグナル生成・自動売買システム。

姉妹プロジェクト [zenigame](../zenigame)（日本株予測システム）の設計思想を参考に、FX 向けに独立して構築する。コードは共有しない。

## 現状

**初期段階**。ソースコード・データ基盤・インフラはまだ存在しない。現在は以下のみ整備済み:

- `AGENTS.md` — プロジェクト方針・開発ルール
- `CLAUDE.md` — Claude Code 向けエントリポイント（`AGENTS.md` を参照）
- `.claude/` — Claude Code 設定一式（skills は zenigame 由来で未適合。詳細は [AGENTS.md](AGENTS.md)）

## 短期目標

zenigame を参考に、FX 取引を実行する仕組みの骨格を実装する。

## フェーズ構成（予定）

| Phase | 内容 |
|-------|------|
| Phase1 | 価格・通貨ペアDB・キャッシュ（基盤） |
| Phase2 | ニュース・経済指標取り込みと分類 |
| Phase3 | シグナル生成と評価（改善ループ） |
| Phase4 | 取引ルール込みの検証（バックテスト） |
| Phase5 | 売買実行（Paper Trading → Live） |

## 想定技術スタック

- Python 3.11+ / uv
- PostgreSQL（価格・ニュース・メタデータ）
- FX データソース: 未選定（OANDA / MetaTrader5 / Dukascopy / Alpha Vantage 等を比較予定）
- タスクキュー: 未定（zenigame 同様 Dramatiq + RabbitMQ を想定）

実装が進んだ段階で本 README を更新する。

## 次のアクション

最初のマイルストーン候補は [AGENTS.md の「次のアクション候補」](AGENTS.md#次のアクション候補) を参照。
