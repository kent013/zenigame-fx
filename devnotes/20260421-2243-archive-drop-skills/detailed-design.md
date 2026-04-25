# 詳細設計: archive-drop-skills

## 使命・制約（絶対遵守）

### zenigame-fx Alpha Factory 使命
live_criteria 全指標同時充足 + (ii-lite) 通過で使命達成。
絶対制約: イントラデイ / ロング・ショート両方向 / スワップ・スプレッド反映。

### 禁止事項
1. A・B・C 評価期間を根拠なしに延長
2. 見た目の数値改善
3. GA ハック
4. live_criteria 緩和
5. 過度な複雑化
6. 取引回数削減で成績を見せる
7. オーバーナイト保有前提

### コーディングルール
- **バグ修正はテストファースト**: 再現最小テスト → FAIL 確認 → 修正 → PASS
- **全施策にテスト必須**（テストなしは実装完了としない）
- **テスト命名**: 振る舞いを説明する汎用的な名前（Run 名・日付・セッション固有の識別子 NG）
- **テスト配置**: 対象モジュールに対応するテストファイル
- **uv 必須**: `uv run pytest tests/alpha_factory/`
- **ruff / mypy 通過**: `uv run ruff check src/ tests/` / `uv run mypy src/`
- Python 3.13 + numpy + pandas 環境

本施策は運用インフラ整理（ディレクトリ移動・README 作成・AGENTS.md 更新）であり、Python コードおよび GA / primitive 実装は一切変更しない。そのためルックアヘッドバイアス・メモリ制約・compute_all_bars 等のチェックは「該当なし」だが、テスト方針・検証ログ方針は別途定義する（後述）。

## 概念設計リファレンス

`devnotes/20260421-2243-archive-drop-skills/conceptual-design.md`（Codex 概念レビュー APPROVED / Round 2）

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|
| 1 | 予備検証: `_archived/` 配下 skill が候補検出されるかダミーで確認 | なし（検証ログを devnotes に残す） | High |
| 2 | `.claude/skills/_archived/` 作成 + 7 skill を `git mv` で退避 | `.claude/skills/{対象7件}/**` → `.claude/skills/_archived/{対象7件}/**` | High |
| 3 | `.claude/skills/_archived/README.md` 作成 | `.claude/skills/_archived/README.md` (新規) | High |
| 4 | 事後検証: skill 候補一覧で対象 7 件が消えたことを確認 | なし（検証ログを devnotes に残す） | High |
| 5 | `AGENTS.md` の archive 方針セクション更新 | `AGENTS.md` L108-117 | High |
| 6 | `.claude/settings.local.json` allow リスト整理（該当なし確認） | 変更なし（確認のみ、検証ログに残す） | Medium |

## 施策 1: 予備検証（`_archived/` プレフィックス検証）

### 目的
「`.claude/skills/_archived/` 配下に配置した skill ディレクトリは Claude Code の skill 候補に現れない」という **exit-blocker 仮説** を実装前に反証可能な形で検証する。

### 変更箇所
- コード・設定の変更なし（ダミー skill を一時作成 → 検証後に削除）
- 検証ログ保存先: `devnotes/20260421-2243-archive-drop-skills/verification-log.md`

### 波及変更
- `AGENTS.md`: なし
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- `config/alpha_factory/default.yaml`: なし
- `docs/alpha_factory/*.md`: なし

### 手順
1. 現状の skill 候補一覧を取得（Claude Code セッション内で available skill を列挙、出力を `verification-log.md` に "before-dummy" として保存）
2. ダミー skill を作成:
   ```
   .claude/skills/_archived/zenigame-fx-dummy-probe/SKILL.md
   ```
   最小構成（frontmatter + 短い description のみ）
3. Claude Code セッションを再起動し（または新セッションで）、skill 候補一覧を再取得
4. ダミー skill `zenigame-fx-dummy-probe` が候補に**出ないこと**を確認、出力を "after-dummy" として `verification-log.md` に記録
5. ダミー skill を削除

### 失敗時の分岐
- ダミー skill が候補に**出てしまった**場合: 施策 2 に進まず、設計フォールバック案（A/B/C）を採用する。
  - **案 A**: `_archived` ディレクトリ名を harness が確実に無視する名前に変更。実装前に Claude Code ドキュメントを `.claude` 設定ガイド等で確認。無ければ案 C へ。
  - **案 B**: `SKILL.md` / `skill.md` を `SKILL.md.archived` にリネーム（frontmatter 消失で検出から外れる想定）。ただし frontmatter 解析失敗が候補列挙エラーを出す可能性があるため、ダミーで追加検証が必要。
  - **案 C**: `.claude/skills/` 配下から完全に外し、`.claude/_archived-skills/` へ移動。最も確実だが `AGENTS.md` の「`.claude/skills/_archived/` に退避」記述と矛盾するため、AGENTS.md 側の記述を「`.claude/_archived-skills/` に退避」に合わせて修正する。
- 採用案を `verification-log.md` に記録し、施策 2 以降の対象パスを差し替える。

### テスト計画
- コード変更なしのため pytest 実行なし
- 検証ログが `verification-log.md` に残されていること、before/after の skill 候補一覧が含まれていることを目視レビューで確認（レビュアー: 次フェーズの implement スキルまたはユーザー）

### リスク
- Claude Code のセッション再起動なしでは新規 skill が認識されない可能性（検証不能リスク）。その場合は implement 実施者が手動で再起動する旨を手順に明記
- 施策全体が検証結果に依存しているため、検証失敗時はただちに implement を停止する

---

## 施策 2: `.claude/skills/_archived/` 作成 + 7 skill の git mv

### 変更箇所
対象 7 skill ディレクトリを `git mv` で移動（施策 1 で案 A/B/C 分岐した場合は、それに応じたパスへ変更）:

```
.claude/skills/zenigame-enqueue-task/          → .claude/skills/_archived/zenigame-enqueue-task/
.claude/skills/zenigame-manage-alert/          → .claude/skills/_archived/zenigame-manage-alert/
.claude/skills/zenigame-manage-timer/          → .claude/skills/_archived/zenigame-manage-timer/
.claude/skills/zenigame-restart-worker/        → .claude/skills/_archived/zenigame-restart-worker/
.claude/skills/zenigame-troubleshoot-worker/   → .claude/skills/_archived/zenigame-troubleshoot-worker/
.claude/skills/zenigame-primitive-ic-eval/     → .claude/skills/_archived/zenigame-primitive-ic-eval/
.claude/skills/zenigame-primitive-ic-sync/     → .claude/skills/_archived/zenigame-primitive-ic-sync/
```

### 波及変更
- `AGENTS.md`: L108-117 の記述を **施策 5 で** 更新（本施策内では触らない。検証完了まで「退避予定」状態を保持）
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし（FX namespace の skill は対象 7 件に含まれない）
- `config/alpha_factory/default.yaml`: なし（GA 設定には影響しない）
- `docs/alpha_factory/*.md`: なし（`docs/alpha_factory/concepts/archive-drop-skills.md` stub は履歴として残し、本タスクでは更新しない）
- `.claude/settings.local.json`: 確認結果として変更なし（施策 6 で明示）

### 現行コマンド（実行コマンドの例）
```bash
# 施策 1 で「ダミーが候補に出ない」ことが確認された前提
mkdir -p .claude/skills/_archived
git mv .claude/skills/zenigame-enqueue-task .claude/skills/_archived/zenigame-enqueue-task
git mv .claude/skills/zenigame-manage-alert .claude/skills/_archived/zenigame-manage-alert
git mv .claude/skills/zenigame-manage-timer .claude/skills/_archived/zenigame-manage-timer
git mv .claude/skills/zenigame-restart-worker .claude/skills/_archived/zenigame-restart-worker
git mv .claude/skills/zenigame-troubleshoot-worker .claude/skills/_archived/zenigame-troubleshoot-worker
git mv .claude/skills/zenigame-primitive-ic-eval .claude/skills/_archived/zenigame-primitive-ic-eval
git mv .claude/skills/zenigame-primitive-ic-sync .claude/skills/_archived/zenigame-primitive-ic-sync
```

### 実行順序の論理
- ディレクトリ作成 → 7 件の移動 → `git status` で全件が rename 扱いになっていることを確認 → 1 コミットにまとめる
- rename が検出されない（delete + add になる）ケースがあれば `git mv` が正しく使えたかを再確認

### テスト計画
- 実装後に `git log --follow .claude/skills/_archived/zenigame-enqueue-task/SKILL.md` で元ディレクトリの履歴が追えることを確認（1 件スポットチェック）
- `git diff --stat HEAD^` で 7 件すべての rename / または rename-like (similarity ≥ 90%) が表示されていることを確認

### リスク
- Git の rename 検出が効かない場合、履歴追跡が劣化する（skill 内部のファイル変更を含まない単純移動であるため、通常は rename 扱いになる想定）
- コミット前に `git status` を必ず確認し、rename 扱いでないファイルがあれば内容の空改行等で差分が出ている可能性があるため調査する

---

## 施策 3: `.claude/skills/_archived/README.md` 作成

### 変更箇所
- 新規ファイル: `.claude/skills/_archived/README.md`

### 波及変更
- `AGENTS.md`: 施策 5 でこの README への参照を追加
- その他: なし

### 構成
以下の章立てで記述:

1. **目的**: なぜ archive するか（zenigame-fx 環境で動作しない 7 skill の退避、master-plan Phase 0-A 対応）
2. **archive 実施日・コミット ハッシュ**: 施策 5 コミット完了後に記入
3. **対象 skill 一覧**: 7 件それぞれに以下を記載
   - skill 名
   - 元パス / archive 後パス
   - 依存先（systemd / Dramatiq / Discord / J-Quants）
   - archive 理由（FX 側で動作しない具体的な箇所）
   - **復活条件**（何が整えば復活できるか）
   - **FX 側で再設計する場合の置換対象**（conceptual-design.md の表と一致）
4. **復活手順**:
   - 依存インフラが整ったことを確認
   - `git mv .claude/skills/_archived/{skill} .claude/skills/{skill}`
   - Claude Code を再起動して候補に出ることを確認
   - 復活 commit を作成
5. **参照**: `AGENTS.md` L108-117、`devnotes/20260421-1850-fx-skill-port/master-plan.md` Phase 0、`devnotes/20260421-2243-archive-drop-skills/`

### テスト計画
- Markdown が broken link を含まないこと（相対パス 2-3 件をスポットチェック）
- 各 skill の情報が `conceptual-design.md` の表と整合していることをレビューで確認

### リスク
- README の情報が陳腐化する（将来 FX 側で代替インフラが整ったとき更新されない）: 復活手順中に「この README を更新する」ステップを明記することで緩和

---

## 施策 4: 事後検証

### 目的
施策 2 実施後に「対象 7 skill が skill 候補一覧から消えた」ことを実測確認する。

### 変更箇所
- なし（検証ログを `devnotes/20260421-2243-archive-drop-skills/verification-log.md` へ追記）

### 手順
1. Claude Code セッションを再起動（または新規セッション）
2. 利用可能 skill 一覧を取得（`/` メニューまたは ToolSearch 等）
3. 対象 7 件の skill 名が**含まれないこと**を確認
4. `verification-log.md` に "before-move" / "after-move" の 2 snapshot を保存
5. 不一致があれば施策 2 をロールバック（`git reset --soft HEAD^` or `git mv` 逆方向）し、施策 1 のフォールバック案へ分岐

### テスト計画
- before/after snapshot が揃っていること、7 件すべてが after から消えていることを確認
- 他の skill（例: `zenigame-fx-codex-review`、`zenigame-fx-autopilot`）は引き続き候補に出ることを確認（意図しない副作用検出）

### リスク
- 検証方法（skill 一覧取得手段）が harness バージョンに依存。実装時に手順が変わった場合は implement 実施者が代替手段を選ぶ
- ロールバックのタイミングを誤ると AGENTS.md も不整合のままになるため、「施策 5 前に必ず検証」が絶対条件

---

## 施策 5: `AGENTS.md` の archive 方針セクション更新

### 変更箇所
- ファイル: `AGENTS.md` L108-117

### 波及変更
- `.claude/skills/zenigame-fx-*/SKILL.md`: なし
- その他: なし

### 現行コード
```markdown
## .claude/ 設定の現状

zenigame からコピーした skills 群（`.claude/skills/zenigame-*`）はすべて zenigame 固有のインフラ（systemd ワーカー、Alpha Factory、J-Quants etc.）に依存している。**zenigame-fx のインフラが整備されていない現段階では、これらの skill は機能しない。**

方針:
- zenigame-fx の機能が育つにつれて、必要な skill を個別に新設する（`zenigame-fx-*` 名前空間）
- zenigame 固有の skill を流用する必要はない。設計パターンだけ参考にして、zenigame-fx 用に書き直す
- 混乱を避けるため、実装が進んだ段階で zenigame-* skill は削除するか `.claude/skills/_archived/` に退避する

`.claude/hooks/bash-permissions.py` は汎用的なので残す。
```

### 変更後コード
```markdown
## .claude/ 設定の現状

zenigame からコピーした skills 群のうち、zenigame 固有のインフラ（systemd ワーカー、Dramatiq、Discord、J-Quants 等）に依存して FX 環境で動作しない 7 件は `.claude/skills/_archived/` に退避済み（2026-04-21, Phase 0-A 完了）。退避理由・復活条件は `.claude/skills/_archived/README.md` を参照。

それ以外の `.claude/skills/zenigame-*` は `master-plan.md` Phase 1（RENAME-ONLY）および Phase 3（CONTENT-ADAPT）で段階的に `zenigame-fx-*` namespace へ移植する。

方針:
- zenigame-fx の機能が育つにつれて、必要な skill を個別に新設・移植する（`zenigame-fx-*` 名前空間）
- zenigame 固有の skill を流用する必要はない。設計パターンだけ参考にして、zenigame-fx 用に書き直す
- `.claude/skills/_archived/` に退避した 7 件は将来インフラ整備後に復活検討（詳細は `_archived/README.md`）

`.claude/hooks/bash-permissions.py` は汎用的なので残す。
```

### 実行タイミング
**施策 4 の事後検証が成功した後にのみ**実施する。失敗時は本施策をスキップし、ロールバックに進む。

### テスト計画
- Markdown の broken link なし
- `_archived/README.md` への相対リンクが正しいこと

### リスク
- 施策 4 が部分的成功（一部の skill のみ非表示化）の場合、AGENTS.md を更新してよいか判断が必要。基本方針は「全 7 件非表示が確認できない限り AGENTS.md は更新しない」

---

## 施策 6: `.claude/settings.local.json` allow リスト確認

### 変更箇所
- なし（確認のみ、結果を `verification-log.md` に記録）

### 波及変更
- なし

### 確認手順
1. `.claude/settings.local.json` を Read
2. `permissions.allow` に対象 7 skill のパスを含む Edit エントリが**存在しないこと**を確認（2026-04-21 時点で確認済み: `zenigame-run-alpha-factory` / `zenigame-profile-optimize` / `zenigame-run-report` の 3 件は対象外 skill のため本施策とは無関係）
3. 確認結果を `verification-log.md` に記録

### テスト計画
- 実施の都度、`.claude/settings.local.json` を Read した結果に対象 7 skill 名が含まれないことをログ化

### リスク
- 実装時点で settings.local.json に対象 skill への個別エントリが追加されていた場合（想定外）、`.claude/skills/_archived/...` へのパスに書き換えるか、削除するかを判断する必要あり

---

## ルックアヘッドバイアスチェック

本施策は運用インフラ整理で、時系列データ処理・primitive・GA に一切触れないため **該当なし**。

## パフォーマンスチェック

本施策は GA / primitive 実行に影響しないため **該当なし**。メモリ使用量・実行時間は変化しない。

## 総合テスト計画

コード変更がないため pytest 追加はない。代わりに以下を実装完了条件とする:

1. **検証ログの完全性**: `verification-log.md` に施策 1（予備）/ 施策 4（事後）/ 施策 6（allow 確認）の 3 つの snapshot が残っていること
2. **git rename 検出**: `git log --follow` で 7 skill のうち少なくとも 1 件の履歴が元パスまで追えること
3. **実測非表示化**: 施策 4 で 7 件すべてが候補一覧から消えたことが記録されていること
4. **AGENTS.md 更新順序**: 施策 5 のコミットが施策 4 より**後**のタイムスタンプであること（実質同一コミットに含めても可、ただし検証ログを先に保存）
5. **ruff / mypy**: コード変更なしのため実行不要（README の markdownlint は任意）

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental |
| 判断根拠 | 単一目的（7 skill 退避 + README + AGENTS.md）で閉じ、他 TODO との競合なし。コード変更なしで副作用が GA / primitive に波及しない。1 コミット〜2 コミットで完了する見込み |
| 競合リスク | `master-plan.md` Phase 1 以降の skill 移植タスクは本タスク完了を前提にするため、それらとは順序依存。並行する他 TODO との衝突は想定されない |
| 想定実装時間 | 短（予備検証 + 移動 + README 記述 + 検証 + AGENTS.md 更新 = 合計 30–60 分） |

---

## 実装時の推奨コミット構造

1. **コミット A**: `chore(skills): archive 7 zenigame skills that depend on systemd/Dramatiq/J-Quants`
   - `.claude/skills/_archived/` 作成（dir）
   - 7 skill の `git mv`
   - `.claude/skills/_archived/README.md` 新規作成
2. **コミット B**（検証後）: `docs(AGENTS): note Phase 0-A skill archive completion`
   - `AGENTS.md` L108-117 更新

検証ログ（`verification-log.md`）は devnotes 配下でコミット A に含めても B に含めても可。ただし可能ならコミット A に含める。
