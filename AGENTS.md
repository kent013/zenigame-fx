# AGENTS.md

常に日本語で返答してください。すべての応答、説明、コメントは日本語で行ってください。

## プロジェクト概要

**zenigame-fx** — FX（外国為替）取引システム。為替レート・経済指標・関連ニュースを収集し、シグナル生成から自動売買までを一貫して実行するシステムを構築する。

### 最終目標

短中期の為替変動を捉え、検証可能な取引ルールに基づく自動売買で継続的に利益を獲得する。

### 短期目標

**現状**: プロジェクトは初期段階。`AGENTS.md` / `CLAUDE.md` / `README.md` と `.claude/` 設定のみ存在し、ソースコード・データ基盤・インフラは未整備。

まず最初のマイルストーンとして、姉妹プロジェクト [zenigame](../zenigame)（日本株予測システム）を参考に、FX 取引を実行する仕組みの骨格を実装する。

### フェーズ構成（予定）

- **Phase1**: 価格・通貨ペアDB・キャッシュ（基盤）← 次のステップ
- **Phase2**: ニュース・経済指標取り込みと分類
- **Phase3**: シグナル生成と評価（改善ループ）
- **Phase4**: 取引ルール込みの検証（バックテスト）
- **Phase5**: 売買実行（段階導入：Paper Trading → Live）

## 参照プロジェクト: zenigame

`/Users/ishitoya/repository/zenigame` に日本株を対象とした姉妹プロジェクトがある。以下が参考になる:

- ディレクトリ構成（`src/`, `scripts/`, `docs/`, `devnotes/`）
- Dramatiq + RabbitMQ ベースのタスクキュー設計
- PostgreSQL + Alembic によるデータベース設計
- キャッシュ戦略（diskcache、URL訪問トラッカー）
- Alpha Factory（GA によるシグナル探索）の設計思想
- 運用（systemd、Discord 通知、ログローテート）

**重要**: zenigame と zenigame-fx の**コード共有はしない**。同じ課題に対する実装パターンの参考にとどめ、それぞれ独立したコードベースとして進化させる。

zenigame 側のファイルは `.claude/settings.local.json` の `additionalDirectories` で参照可能にしてある。

## 思考原則 — 全議論に適用

**まず仮説を立てろ。** 何を検証したいのか、なぜそう考えるのか、どうなれば成功と判断するのかを明確にしてから手を動かせ。仮説なき改善はただの試行錯誤であり、結果から学ぶことができない。

探索空間は広い。今いる場所が正しいのか、もう少し先に進むべきか、横に移動すべきか、戻って別の道を探るべきかは、これまでの試行と観察の蓄積からしか判断できない。

**データに真摯に向き合え。** 成果だけでなく、変化、構造の揺らぎ、想定外のパターン — 全てが判断材料になる。数値を見て即座に閾値を弄るな。何が起きているのかを理解し、なぜそうなったのかを考え、どの方向に進むべきかを判断してから手を動かせ。

**先人の知恵を探せ。** 自分たちだけで登る必要はない。乗るべき巨人の肩があるなら乗れ。zenigame の既存実装は最初の巨人の一つである。

**機能の名前に立ち返れ。** 名前はその機能が果たすべき役割を示している。現在の設計がその役割を果たしているか、常に問え。

**仕組みが機能していない段階で値を弄るな。** 閾値チューニングやフィールド追加は、設計の方向性が正しいと確認できてから行え。方向性が間違っているなら、値をいくら調整しても意味はない。設計そのものを見直せ。成果が出なければ早期に見切り、次の仮説へ進め。

### 監査・レビュー時の discipline

- **C1 Design-first**: コードの bug claim を出す前に、設計ドキュメント・devnotes・git 履歴を必ず先に読む。grep だけで「バグ」判定しない
- **C2 X が無い = バグ 禁止**: 関数 Y に識別子 X が無いだけでは bug ではない。別経路での計算を広く探す
- **C3 Collider bias**: フィルタ連鎖の中間集団で取った相関を因果解釈しない。Conditioning set を必ず明示する
- **C4 前提検証**: 分析 chain の先頭に前提を bullet 化し、各前提が verified であることを明示してから下流に進む
- **C5 並列独立性**: 並列 sub-agent が同じ出発点を共有している場合、independent verification ではなく「同じ誤読の N 倍冗長実行」であることを認識する
- **C6 Fact / Interpretation 分離**: 観察事実と解釈を別セクションで書く
- **C7 Sample size**: n<30 の相関は明示的に因果解釈を避ける。n<10 の相関 claim は禁止
- **C8 INCONCLUSIVE**: データ不足は正当な結論。無理に CONFIRMED/REJECTED に寄せない
- **C9 Falsification-first**: Round 1 は「この仮説の反証を探せ」から始める

---

## 開発ルール

### 基本原則

- 冗長な記述より簡潔な記述
- 明確な指示がない限り、設計は概念レベル・方針決定レベルで行う
- 出力は最小限に（大量の出力は避ける）
- ファイルの削除・コピーはコマンドで解決
- dev サーバーは立ち上げない（ブラウザ確認はユーザーが行う）
- 了承を得ない限り、キャッシュは絶対に消してはいけない

### 設計ファイル管理

- 設計時は `devnotes/YYYYMMDD-HHMM-{topic}/` 以下にフォルダを作成して md ファイルを保存
- 新要件が与えられた時は極力同じファイルを修正（別ファイルの場合は元ファイルにリンク）
- 不必要な設計ファイルは削除し、常に最新の設計を維持
- ファイル名に「final」をつけるのは禁止
- タイムスタンプは日本時間（JST）
- **devnotes は必ずコミットすること** — 未コミットの設計ノートを残さない

### 実装

- **uv 必須**: `uv run python script.py`, `uv pip install pkg`
- **外部 API・ライブラリを使う前に必ず MCP で公式ドキュメントを確認**
  - **Context7 MCP**: Python/JavaScript ライブラリのドキュメント検索に使用
  - WebFetch や WebSearch ではなく、MCP サーバーを優先的に使用すること
- 新規スクリプトは `devnotes/` に配置 → 本番確定後に `scripts/` へ移動

### テスト

- pytest 形式で実装
- 外部通信（API、クローラー、LLM）は必ずモック化
- fixtures を活用して共通セットアップをまとめる
- テスト名は**振る舞いを説明する汎用的な名前**にする（日付・セッション固有の識別子を含めない）
- テストは対象モジュールに対応するテストファイルに配置

---

## aux データ pipeline と preflight 運用 (T057 Phase 2)

本番 RUN 前に **`scripts/fetch_aux_data.sh`** を実行して aux データを取得する。wrapper は FRED 10 series (VIXCLS, DTWEXBGS, DGS10, DGS2, T10YIE, GOLDPMGBD228NLBM, DCOILWTICO, PCOPPUSDM, PALLFNFINDEXM, SP500) + EUR_USD/USD_JPY M1 bars + economic events scaffold を一括取得する。

`run_ga.py` 起動時に preflight check が走り、**HARD_REQUIRED** (VIXCLS / DTWEXBGS / EUR_USD_M1 / USD_JPY_M1) が不足すると fail-closed (override: `--allow-aux-missing`)。**SOFT_REQUIRED** (Gold / WTI / Copper / commodity / SP500) は WARN log のみで safe default 経路に落ちる。

look-ahead bias 防止: `macro_index_daily.effective_from_utc` 契約 (daily +24h / 月次 +35d) で、`bar.bar_time >= effective_from_utc` を満たす obs しか forward-fill しない。詳細: `docs/alpha_factory/runbook.md` § 6 / `devnotes/20260427-2234-aux-data-loader-phase2/`。

---

## calibrate-gate と state file 経由の自動適用 (T054)

`scripts/alpha_factory/calibrate_gate.py` は Stage A threshold 決定時に以下を実行:
1. `config/alpha_factory/default.yaml` の `stage_gate.stage_a.threshold` を atomic 書き戻し
2. `reports/calibrate-gate/history.jsonl` に cross-run contamination guard 用 metadata 付き record を append (`schema_version=1`, `base_config_hash`, `full_config_hash`, `dataset_span`, `instrument`, `stage_gate_version`, `applied_from_run_id`)

`run_ga.py` 起動時、優先順位 `CLI > history > yaml` で effective threshold を確定:
- CLI: `--stage-a-threshold X` (明示指定、最優先) → `source="cli"`
- history: 最新適用可能 record (`base_config_hash` 一致 + `decision in (tighten, loosen)` + isfinite + range 内) → `source="history"`
- yaml: `default.yaml` の値 (initial seed) → `source="config"`

yaml を chore commit で reset しても history が新しければ history 値が effective になる (cross-run 一貫性)。startup 時に必ず `stage_gate.effective_threshold stage_a_threshold=X source={config|history|cli}` log を出力する。

詳細: `docs/alpha_factory/stage-gates.md` § "T054: state file 経由の自動適用".

---

## Stage A/B disjoint 化と Stage Partition Guard (T087)

`run_ga.py` は dataset を以下の 3 区間に時系列上 disjoint に分割する:

- Stage A: `[dataset.end - stage_a_window, dataset.end)` (GA fitness 評価対象、 末尾固定)
- Stage B: `[dataset.start, dataset.end - stage_a_window)` (fold WF + IS monitor、 Stage A 期間を除外)
- Stage C holdout: `[dataset.end, dataset.end + stage_c_holdout_days)`

起動時 `stage_partition_guard.validate_stage_partition` が以下を fail-closed で検証 (escape hatch なし):

- B-0 入力健全性 (non_empty / UTC tz / not null / monotonic / unique-within-stage)
- B-1 partition 整合性 (chronological order 3 条件 + exact timestamp disjoint 3 条件)

旧 `stage_windows.allow_stage_c_fallback_slice` は廃止。 holdout が DB から取得できない場合は常に RuntimeError。test fixture で synthetic holdout が必要な場合は test-only helper で `LaneBarsBundle` を直接構築する。

`STAGE_GATE_VERSION` は `v4_stage_b_disjoint` に bump 済み (旧 `v3_stage_b_fold_min_trade_count` 期の calibrate-gate history は cross-run guard で誤適用されない)。

詳細: `docs/alpha_factory/stage-gates.md` § "Stage A/B disjoint 契約 (T087)" / `docs/alpha_factory/runbook.md` § 4-1。

---

## .claude/ 設定の現状

`.claude/skills/` 配下は以下の三層構成:

1. **`zenigame-fx-*`**（移植・新設済み）: zenigame-fx 環境で動く正式 skill 群（autopilot, codex-vscode, codex-review, alpha-design, todo-add, todo-close, implement, update-docs, improve-cycle [full Phase 2 architecture orchestrator], analyze-run, run-report, run-alpha-factory, plan-and-design 他）
2. **`zenigame-*`**（流用そのまま）: zenigame 由来でまだ移植中・参考保持の skill 群。zenigame-fx 用 inflastructure 整備後に zenigame-fx-* 版へ順次置き換える
3. **`_archived/zenigame-*`**（退避済み）: zenigame 固有インフラ（Dramatiq, systemd, Discord, J-Quants）依存で zenigame-fx では動作しないため `_archived/` プレフィックス配下に退避し、Claude Code の skill 候補一覧から除外（実地検証済み: 2026-04-21）

退避済み 7 件:
- `zenigame-enqueue-task`, `zenigame-manage-alert`, `zenigame-manage-timer`, `zenigame-restart-worker`, `zenigame-troubleshoot-worker`, `zenigame-primitive-ic-eval`, `zenigame-primitive-ic-sync`

復活条件・退避理由は `.claude/skills/_archived/README.md` を参照。

方針:
- 新設の zenigame-fx-* は `zenigame-fx-codex-review` の使命・禁止事項を継承する
- zenigame-* 残存分は zenigame-fx-* 版を整備したタイミングで削除 or `_archived/` 退避
- `.claude/hooks/bash-permissions.py` は汎用的なので残す
- 移植進捗は `devnotes/20260421-1850-fx-skill-port/master-plan.md` を参照

---

## 次のアクション候補

このドキュメントを読んだ時点でインフラはまだ無い。最初のマイルストーンとしては以下のいずれかを想定:

1. **データソース調査**: FX データ取得元の選定（OANDA API、MetaTrader5、Dukascopy、Alpha Vantage 等）
2. **ディレクトリ骨格構築**: `src/` `scripts/` `tests/` `docs/` `devnotes/` と `pyproject.toml`、基本設定ファイル
3. **最小限の価格取得パイプライン**: 1 通貨ペアのヒストリカルデータを取得し PostgreSQL に格納する
4. **バックテスト基盤の設計**: zenigame の alpha_factory を参考にした FX 版 GA / 評価フローの概念設計

進める際は、まず 1 件を `devnotes/YYYYMMDD-HHMM-{topic}/` で概念設計するところから始める。
