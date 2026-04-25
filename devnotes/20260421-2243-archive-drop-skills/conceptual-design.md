# 概念設計: archive-drop-skills

## 参照ソース（C1 Design-first 証跡）

本設計の前提となる参照元（いずれも 2026-04-21 時点で読了）:

1. `AGENTS.md` L108-117: `.claude/` 設定の現状と archive 方針
2. `devnotes/20260421-1850-fx-skill-port/master-plan.md` Phase 0: 7 skill の DROP 退避計画
3. `devnotes/20260421-1850-fx-skill-port/design.md`: skill 移植全体設計
4. `docs/alpha_factory/concepts/archive-drop-skills.md`: 本施策の stub（skill 7 件の依存先一覧）
5. `.claude/settings.local.json`: permissions.allow の内容（対象 7 skill への個別許可エントリなし、2026-04-21 確認）
6. `git log` 最近 5 件: 対象 skill に関する最近の変更履歴なし（OANDA / ingest 関連コミットのみ）

`docs/alpha_factory/` 直下の GA/戦略設計ドキュメントは本施策（運用インフラ整理）と直接関係がないため未参照。skill 検出仕様は Claude Code harness 側の挙動であり、公開 docs でなく実測で確認する方針（詳細設計で手順化）。

---

## 背景・課題

zenigame-fx リポジトリの `.claude/skills/` 配下には、親プロジェクト zenigame（日本株・Alpha Factory）からコピーした skill が多数残存している。
そのうち 7 個は zenigame 固有のインフラ（systemd、Dramatiq、Discord、J-Quants API 等）に強く依存しており、zenigame-fx 環境では**そもそも動作しない**。

放置することで以下の弊害が生じる:

- Claude が誤って FX 文脈で動かない skill を推奨・起動してしまう
- `/` スキル候補リストのノイズが増え、開発者・エージェント双方の認知負荷が上がる
- `AGENTS.md`（L108-117）で既に「実装が進んだ段階で zenigame-* skill は削除するか `.claude/skills/_archived/` に退避する」と明言されているが、未実行

`devnotes/20260421-1850-fx-skill-port/master-plan.md` の **Phase 0** がまさにこのタスクであり、以降の全フェーズ（skill 移植・FX 基盤構築）が Phase 0 完了を前提にしている。

### 本タスクの位置付け（Phase 0-A）

Codex 概念レビュー Round 1 指摘を受け、本タスクを `Phase 0-A: インフラ依存で明確に非機能な 7 件の隔離` と再定義する。残りの zenigame-* skill（流用検討中のものを含む）は `Phase 0-B` 以降（`master-plan.md` Phase 1-3）で個別判定する。

### なぜ 7 件だけを先に退避するのか（選定基準）

以下の**両方**を満たす skill のみ本タスクの対象とする:

1. **インフラ強依存**: systemd / Dramatiq / Discord Webhook / J-Quants のいずれかに**動作そのものが依存**し、代替インフラ未整備時には空振りで終わる
2. **FX 側に代替用途なし（現時点）**: `master-plan.md` Phase 1（RENAME-ONLY）および Phase 3（CONTENT-ADAPT）の対象リストに含まれない

選定から外れる skill（例: `zenigame-alpha-design`, `zenigame-codex-review`, `zenigame-manage-sessions` 等）は `master-plan.md` に基づいて rename / content-adapt で FX 化する計画があるため、本タスクでは触らない。

## 改善アイデア

zenigame-fx 環境で動作しない 7 skill を `.claude/skills/_archived/` 配下へ `git mv` で退避し、退避理由と復活条件を README に記録する。

### 対象 skill（7 個）

| skill 名 | 依存先 | FX での現状 NG 理由 | FX 側で再設計する場合の置換対象 |
|---------|--------|----------------------|-----------------------|
| zenigame-enqueue-task | Dramatiq / Redis ブローカ | zenigame-fx には Dramatiq ワーカー・Redis が無い | 代替キュー（Celery/RQ/asyncio キュー）または直接呼び出しへ切替 |
| zenigame-manage-alert | Discord Webhook + systemd user unit | 通知チャネルおよび systemd サービス未整備 | 通知チャネル（Slack/email/stdout ログ）決定 + サービス管理方式決定 |
| zenigame-manage-timer | systemd user timer | systemd 依存 | macOS/Linux 汎用の scheduler（launchd / cron / Python APScheduler）採用 |
| zenigame-restart-worker | systemd 制御 | systemd 依存 | FX ワーカーの起動方式（プロセス/コンテナ/systemd）決定後に再設計 |
| zenigame-troubleshoot-worker | systemd / Dramatiq ログ | ワーカー基盤未整備 | ワーカー基盤確定後にログ取得経路を定義 |
| zenigame-primitive-ic-eval | J-Quants API + 日本株 primitive | FX では J-Quants を使わず OANDA / FRED 等 | FX データソース・primitive 体系確立後に IC 評価ロジック再設計 |
| zenigame-primitive-ic-sync | J-Quants API | 同上 | FX 用 primitive 同期経路を新規設計 |

## 期待効果

### 使命（live_criteria 達成）への直接寄与

- **直接寄与: なし**。本施策は GA / primitive / gate / live_criteria 指標のいずれにも触れない
- 単独で live_criteria を満たすことはない

### 開発オペレーション健全化への寄与（間接）

- **認知ノイズ削減**: 誤起動リスクが下がる（ただし skill 検出仕様の未確認仮説に依存、後述）
- **master-plan Phase 0 の完了**: `devnotes/20260421-1850-fx-skill-port/master-plan.md` Phase 1–6 着手が解禁
- **可逆性確保**: `git mv` + README で後続エージェントに意図を引き継げる
- **Phase 1 以降の使命達成サイクルを動かすための前提整備**

### Fact / Interpretation 分離

- **Fact**: 本施策は運用インフラ整理であり、GA / primitive / gate / live_criteria 指標のいずれにも直接触れない
- **Interpretation**: 優先度 High の論拠は「戦略性能改善」ではなく「開発導線の正常化 = Phase 1 以降の着手解禁」である

## 実装方針（概要）

1. **予備検証**（必須・詳細設計で手順化）: 現状の skill 候補一覧を取得 → `_archived/` 配下の skill が検出対象になるか実測確認
2. `.claude/skills/_archived/` ディレクトリを新規作成
3. 対象 7 skill ディレクトリを `git mv` で `_archived/` 配下へ移動（履歴保持）
4. `.claude/skills/_archived/README.md` を新規作成し、以下を記載:
   - archive の背景・目的
   - 各 skill の archive 理由と復活条件（上記表の各行を展開）
   - 復活手順（`git mv` で元に戻す + 依存インフラ整備チェックリスト）
   - 参照: `AGENTS.md` L108-117 / `devnotes/20260421-1850-fx-skill-port/master-plan.md`
5. **事後検証**: skill 候補一覧を再取得 → 対象 7 件が候補から消えたことを確認
6. **検証成功後**に `AGENTS.md` L110-115 付近を更新（「退避する予定」→「退避済み（`.claude/skills/_archived/`）」+ README 参照）
7. 失敗時のフォールバック（検証で非表示化されない場合）を詳細設計で定義（後述）

### skill 検出が `_archived/` で止まらなかった場合のフォールバック

詳細設計で以下 3 案を手順化し、検出実測の結果に応じて選択:

- **案 A**: ディレクトリ名を `_archived` ではなく、Claude Code harness が既知で無視する規約名（確認のうえ採用）に変更
- **案 B**: `SKILL.md` / `skill.md` を `SKILL.md.archived` 等にリネームしてスキル発見ロジックから外す
- **案 C**: 該当 skill ディレクトリ自体を `.claude/skills/` 配下から `.claude/_archived-skills/` 等へ出して検出対象外にする

**完了条件**: 上記いずれかの方法で「対象 7 skill が実行可能な skill 候補一覧に出現しない」ことを実測で確認する。

## 制約・前提

### 前提の三分類（verified / unverified / exit-blocker）

#### verified（確認済み）

- 対象 7 skill のディレクトリは全て `/Users/ishitoya/repository/zenigame-fx/.claude/skills/` 配下に実在する（2026-04-21 時点）
- `AGENTS.md` L110-117 に archive 方針が明文化されている
- `.claude/settings.local.json` の allow リストに対象 7 skill への個別 Edit 許可エントリは**存在しない**（`zenigame-run-alpha-factory` / `zenigame-profile-optimize` / `zenigame-run-report` は別 skill で本施策の対象外）
- `master-plan.md` Phase 0 とスコープが一致

#### unverified（task exit 時点でも完全確証が得られない可能性あり）

- `git mv` 後の履歴保持: `git log --follow` で追えることはほぼ確実だが、ディレクトリ renames の扱いは Git バージョン依存で一部ログ表示が劣化する可能性あり

#### exit-blocker（task exit までに必ず潰すべき仮説）

- **`_archived/` 配下は skill 候補として自動検出されない**: これが満たされないと施策の主目的（誤起動防止）が未達。詳細設計で実測手順と失敗時のフォールバックを必ず定義する
- 権限（`.claude/settings.local.json`）確認と候補検出は別問題であり、両方検証する

### その他制約

- `git mv` による履歴保持を必須とする（`rm` + `add` は不可）
- 退避は可逆的でなければならない（将来の復活を想定した README 記述）
- `AGENTS.md` の更新順序: **実移動 → 候補非表示検証 → AGENTS.md 更新** の順（Round 1 指摘 #4 に対応）。検証前に AGENTS.md を「退避済み」に書き換えない

## スコープ外

- **FX 用 skill の新設・既存 skill のリネーム**: `master-plan.md` Phase 1 以降（Phase 0-B）で扱う
- **zenigame-* skill の完全削除**: 復活可能性を残すため削除はしない
- **対象 7 個以外の zenigame-* skill の棚卸し結果に基づく移動判断**: `master-plan.md` の分類に従って別タスクで扱う
- **`.claude/hooks/` 配下の整理**: `bash-permissions.py` は汎用として残す方針（AGENTS.md L117）
- **live_criteria 指標・GA 設定・primitive コードへの変更**: 本施策は運用インフラのみ

## 優先度・テーマ

- **Priority**: High（後続 Phase 1-6 全ての前提、master-plan 通り）
- **Mode**: incremental（単発で閉じ、他 TODO との競合なし）
- **Theme**: skill-port
