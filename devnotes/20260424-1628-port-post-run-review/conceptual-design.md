# 概念設計: post-run-review skill port (T026)

**作成日時**: 2026-04-24 16:28 (JST)
**サイクル**: autopilot cycle 29 (port-post-run-review)
**前提**:
- HEAD = `227ac58` (verified — `git log` で確認済)
- test count = 834 passed / 1 skip (報告ベースライン、本 TODO 内で再検証は行わない)
- launch owner = `zenigame-fx-improve-cycle` Phase 1 末尾のみ (verified — §2.8 で単一化)
- TODO 追加は既存 `todo_manager.py` (next-id + add の 2 命令) を改修せず使う (unverified atomic、§2.6 で micro-stagger + retry で吸収)

## 1. 課題と仮説

### 課題

`zenigame-fx-improve-cycle` Phase 1 完了後、`analyze-run` の出力（Run 1 件分の事実集計と次サイクル候補 3-5 個）はあるが、**改善設計 / TODO 登録までは別フェーズ (plan-and-design)** に委ねられている。
plan-and-design は「単一の cycle_focus を選んで設計に落とす」 1 系統のため、複数の戦略視点（シグナル / レジーム / コスト / 堅牢性 / リスク）が単独 Run 内で並列に育たない。

zenigame では `post-run-review` skill が「テーマ別 BG セッション × 5 並列」を担っており、改善案が**テーマ単位で並列に**育っていた。
zenigame-fx でも同等の機構を入れたいが、**zenigame 固有の systemd / Dramatiq に依存しない**形で port する必要がある。

### 仮説

- **H1**: テーマ別レビューを **fire-and-forget で並列起動** すれば、improve-cycle は Phase 2 以降をブロックせず、改善案のスループットを 5 倍化できる。
  Claude Code の Agent ツール (`run_in_background: true`) で 1 テーマ = 1 Agent を起動すれば、systemd / nohup / Dramatiq が無くても等価機能が得られる。
- **H2**: テーマ単位で Open TODO の有無を early-check すれば、同じ問題に対する重複設計を抑止できる。
  zenigame 版の `has-open-theme` 相当を `todo_manager.py list` の出力から自前計算で代替できる。
- **H3**: FX 用 5 テーマ（signal-quality / regime-awareness / cost-efficiency / robustness / risk-management）は debate-synthesis.md の設計骨子（Clause 構造 / Stage A/B/C / cross-pair (ii-lite) / Sieve）と直交し、各テーマで 1 セッションあたり 0-3 件の改善案が生成できる。

### 成功判定 (実測ベース)

- 5 テーマ起動成功率: improve-cycle Phase 1 末尾で `launched / failed / skipped` の run 単位サマリが残る
- 重複 reject 率: 各 Agent の Codex 案 5-6 件のうち重複チェックで reject された割合がログに残る
- 次サイクルで plan-and-design に消費された TODO 数: post-run-review 由来 (`[review:*]` prefix) の Open TODO が次 cycle Phase 2 で `selected_todos` に入った件数
- improve-cycle Phase 1 完了後、親 skill 側は BG Agent の完了を待たず Phase 2 に進める (fire-and-forget)
- 834 tests passing baseline 維持（skill は md のみ、テスト追加なし）
- post-run-review 起動 owner は **`improve-cycle` Phase 1 末尾のみ** (analyze-run は注記のみ復活)

## 2. 全体設計

### 2.1 入出力契約

```
入力:
- run_id                              improve-cycle / analyze-run から渡される
- theme                               5 テーマのいずれか
- analysis-claude.md / analysis-codex.md  improve-cycle から tmp_dir 経由で参照
- 直近 3 Run の reports/run-reports/run-{N}.md
- docs/alpha_factory/TODO.md (Open / Closed)
- .cache/alpha_factory/post-run-review-{theme}-deferred.md (前回申し送り、optional)

処理:
- early-skip: 同テーマ Open TODO ≥ 1 → 即終了
- Codex (gpt-5.3-codex medium) でテーマ別議論 → 5-6 案
- 重複/禁止/実現性チェック → 上位 0-3 案
- 各案について /zenigame-fx-alpha-design → /zenigame-fx-todo-add を順次実行
- 残りを申し送りに保存

出力:
- devnotes/{ts}-{topic}/conceptual-design.md / detailed-design.md
- docs/alpha_factory/TODO.md への新規行追加
- .cache/alpha_factory/post-run-review-{theme}-deferred.md
- .cache/alpha_factory/post-run-review-{theme}-{run_id}.log
- exit code 0 (正常終了 / skip 含む) / 1 (構成エラー)
```

### 2.2 BG 起動方式 (Claude Code Agent / Claude Code 専用 skill)

**前提**: 本 skill は **Claude Code 専用**。CLI 互換 (nohup / systemd / シェルからの直接起動) は提供しない。
run-alpha-factory が CLI 互換を必須とする (heavy GA を放置可能にする) のとは明確にスコープを分離する: 本 skill は軽量な Codex 議論 + 設計 + TODO 登録のみで、Claude Code Agent 内で完結する。

**launcher (improve-cycle Phase 1 末尾) の責務**:

1. 同一 run_id の二重起動を防ぐため `.cache/alpha_factory/post-run-review-launched-{run_id}.json` の存在を確認。あれば skip
2. 各テーマについて Agent ツールを `run_in_background: true` で起動 (5 テーマ → 5 Agent)
3. **micro-stagger**: Agent 間の起動タイミングを 1 秒ずつずらして同時 next-id 採番衝突を緩和
4. プロンプトに `/zenigame-fx-post-run-review {theme} {run_id} --tmp_dir {tmp_dir}` を渡す (`--tmp_dir` は必須)
5. 起動した Agent ID と起動時刻を `.cache/alpha_factory/post-run-review-launched-{run_id}.json` に記録
6. **完了を待たない** (fire-and-forget)。完了通知は autopilot / improve-cycle が拾う

**post-run-review skill 自身の責務**:

1. 必須引数 `{theme} {run_id} --tmp_dir {tmp_dir}` を受け取る (`--tmp_dir` 不在は error exit 1)
2. 各 Phase を順次実行
3. 完了時 (success / fail / skip いずれも) `.cache/alpha_factory/post-run-review-summary-{run_id}.md` に 1 行追記 (`{theme}: {status} / {todos_added} / {note}`)
4. exit 後は Claude Code Agent ランタイムがクリーンアップ

> **systemd / nohup / Dramatiq は不要**。Claude Code Agent 自体が独立プロセスとして動き、stdout/stderr は Claude Code が管理する。
> autopilot Phase 4A の「5 並列 BG Agent」と同じ pattern。
> `max_parallel_review_agents = 5` (デフォルト) — 本 TODO では cap 適用機構までは含めない。GA Phase 4 と時間重複した場合のリソース競合監視は別 TODO。

### 2.3 テーマ定義 (FX 版 5 テーマ)

| theme | フォーカス | 守備範囲 | 主担当境界 (重複回避) |
|-------|----------|---------|---------------------|
| `signal-quality` | プリミティブ予測力 | directional/gate プリミティブの実効性、ルックアヘッド、新規プリミティブ提案、死滅プリミティブ原因究明 | プリミティブ「単体」の予測力。複数プリミティブ間の regime 切替は regime-awareness |
| `regime-awareness` | レジーム適応 | セッション帯（東京 / ロンドン / NY）、ボラ regime、cross-pair common factor、ペア固有 vs universal | regime gate / cross-pair / global_gate。プリミティブ単体は signal-quality |
| `cost-efficiency` | コスト現実性 | spread / slippage / swap / session_close フィルタ、market impact、live execution 整合性 | コスト**モデル**の現実性。コスト後の OOS 性能評価は robustness |
| `robustness` | 過学習耐性 | DSR / PBO / WF-OOS / Sieve、Stage gate 突破率、サンプル外性能、レジーム持続リスク | OOS 検定統計と Stage gate の通過率制御。コストモデル自体は cost-efficiency |
| `risk-management` | リスク統制 | max_pos / time_stop / max_dd / live_criteria 達成パス、ポジションサイジング | live_criteria 達成パスの設計 (DD / pos)。Sieve / DSR は robustness |

> 株版固有テーマ（director-evolution / signal-predictive-power / japan-market / live-trading / performance / speed）は **撤回**。
> FX 5 テーマは debate-synthesis.md の設計次元（Clause × Stage gate × Cross-pair × Sieve × Risk）と概ね直交する。

### 2.3a review-theme → TODO theme マッピング

post-run-review が引数として受け取る `review-theme` (5 種) は、`zenigame-fx-todo-add` の既存 `--theme` (10 種: ga-architecture / primitives / stage-gate / cross-pair / statistics / data-ingest / swim-lane / skill-port / infrastructure / general) とは別空間である。
post-run-review は内部でマッピングして `todo-add` を呼ぶ:

| review-theme (引数) | TODO theme (`--theme`) | 補足 |
|---|---|---|
| `signal-quality` | `primitives` | プリミティブ予測力・ルックアヘッド・新規プリミティブ |
| `regime-awareness` | `cross-pair` | アンカー / ii-lite / common factor / regime gate |
| `cost-efficiency` | `ga-architecture` | spread / slippage / swap / session_close は GA 評価関数側 |
| `robustness` | `statistics` | DSR / PBO / Sieve / WF |
| `risk-management` | `stage-gate` | live_criteria 達成パスを左右する gate / max_pos / time_stop |

**review-theme 識別**:
- post-run-review 経由で追加する TODO は `--summary` の先頭に **`[r:{code}]`** prefix を付与 (短縮 code を使う、30 文字制約対応)
- 短縮 code (固定): `sq` = signal-quality / `ra` = regime-awareness / `ce` = cost-efficiency / `rb` = robustness / `rm` = risk-management
  - 例: `--summary "[r:sq] ATR 正規化窓の補正"` (`[r:sq] ` で 7 文字 → 内容 23 文字残る)
- 同 review-theme の Open TODO 検出: `todo_manager.py list` の出力を `awk` で `[r:{code}]` を検出する (§2.6 末尾参照)

### 2.4 テーマ別 system prompt (要点のみ)

各テーマ共通 (`zenigame-fx-codex-review` で使命・禁止事項は自動挿入されるため重複記述しない):

```
あなたは zenigame-fx Alpha Factory の {テーマ説明} 専門家です。

【テーマ固有フォーカス】
- {そのテーマで重視する観点 3-5 個}

【追加禁止事項 — 全テーマ共通】
- trade_count 削減を主効果とする提案は禁止 (live_criteria.trade_count_min からの距離が悪化する案は reject)
- 取引回数を削減することで見かけの Sharpe / WR が上がる案は禁止事項#6 違反

【改善ループとの役割分担】
このセッションは「複数 Run にわたって価値を持つ構造的改善」を担う。
以下は別の改善ループ (improve-cycle plan-and-design) が対処するため提案しない:
- 「今回 Run の X 指標に基づく Y パラメータ Z 変更」系の場当たり修正
- 特定 Run の結果から直接導かれる一過性の改善

【出力形式】
- 改善提案を「優先度: Critical / High / Medium」で 5-6 件
- 各提案に「テーマ固有の効果評価」「実装難易度」「実装規模」「trade_count への影響予測 (増 / 不変 / 減 — 減の場合は justify)」を明記
- 既存 Open TODO と重複しない提案
- 日本語
```

### 2.5 Phase 構成

```
Phase 1-0  早期スキップ判定 (Open >= 1 → 即終了)
Phase 1    コンテキスト読み込み (analysis-*, 直近 3 Run, TODO Open/Closed)
Phase 1-5  前回申し送り読み込み (existing なら)
Phase 2    Codex テーマ議論 → 5-6 案 → 上位 0-3 案選定
Phase 3    /zenigame-fx-alpha-design → /zenigame-fx-todo-add を順次 (0-3 回)
Phase 4    申し送りファイル更新
Phase 5    最終ログ出力 → exit
```

zenigame 版の Phase 1-1b（プロファイリング判定）は **削除**。
FX 版で speed テーマを設けないため、対応する判定経路も不要。

### 2.6 重複チェック + TODO 追加の race 吸収戦略

**重複チェック**:
- Open TODO 全件のタイトル + 概要 + 設計リンク (`devnotes/{dir}/`) を `todo_manager.py list` から取得
- 同一問題 / 同一アプローチ / 上位互換 / 下位互換と判定された案は **却下**
- 同一テーマでなくても重複チェックする (signal-quality 案が cost-efficiency Open TODO と被ることもある)

**TODO 追加の race 吸収** (todo_manager.py 改修なし、`lockf` で排他保証):

`scripts/alpha_factory/todo_manager.py` の `next-id` (最大 ID + 1 を返す) と `add` (行追加) は分離されており、ロック / CAS / ID 重複検出は無い。
post-run-review 並列起動 (5 Agent) 環境で 2 件の Agent が同タイミングに `next-id` を引き、別案を `add` すると **同 ID 行が 2 件追加されてサイレントに ID 衝突**が起きる (add 側で error が返らない)。
micro-stagger だけでは確率低減にしかならず排他保証にならないため、本 TODO は **OS 標準 `lockf` で next-id + add 全体を排他クリティカルセクション化**する:

1. **post-run-review skill 内 Phase 3**: 各 `/zenigame-fx-todo-add` 呼び出しは **必ず `/usr/bin/lockf -k -s -t 60 /tmp/zenigame-fx-todo-add.lock sh -c '...'` でラップ**して実行 (skill 内シーケンス必須、同 skill 内 Phase 3 は元々シリアルなので追加の lock オーバーヘッドは小)
2. **`todo-add` skill (Step 3-4) を本 TODO で lockf 化**: **`next-id` と `add` を必ず同じ `lockf` 呼び出しの `sh -c` ブロック内で実行**:
   ```
   /usr/bin/lockf -k -s -t 60 /tmp/zenigame-fx-todo-add.lock sh -c '
     next_id=$(uv run python scripts/alpha_factory/todo_manager.py next-id) || exit 1
     uv run python scripts/alpha_factory/todo_manager.py add --id "$next_id" --title "$PRR_TITLE" ...
   '
   ```
   `/tmp/zenigame-fx-todo-add.lock` を共有 (システム全体で 1 ロック)。**両者を別 `lockf` 呼び出しに分けてはいけない**
3. **launcher (improve-cycle) micro-stagger**: 5 Agent を 1 秒間隔で起動 (lock 競合の集中を更に分散、必須ではないが lock wait 時間の上振れを抑える)
4. **次 cycle Phase 1-2 重複検出**: 万が一 prefix `[r:*]` の意味的重複が残った場合、次 cycle の post-run-review Phase 1-2 重複チェックで検出 → `/zenigame-fx-todo-close --obsolete` で吸収

> 注: `lockf` 化は `zenigame-fx-todo-add` SKILL.md の Step 3-4 (`next-id` + `add`) を「`scripts/alpha_factory/todo_add.sh` を新規追加し、その中で `lockf` する」形でも、または skill 側で `lockf` で直接ラップする形でも良い。**本 TODO 範囲では skill 側で直接ラップする形を採用** (todo_manager.py 改修なし)。
> macOS 標準 `/usr/bin/lockf` を前提とする (`flock` は macOS 標準では不在。Linux でも GNU/BSD `lockf` 互換実装あり)。
> 将来的な `todo_manager.py add-auto` (lock + 重複 summary 検出を 1 命令に統合) は別 TODO に分離。

**`has-open-theme` 等価判定の実装方針 (現行 list 出力に対応)**:

`todo_manager.py list` は Markdown 行を stdout に出すだけ (JSON ではない)。post-run-review Phase 1-0 の同 review-theme Open 検出は以下で実装 (短縮 code を引数で受け取り `index($0, "[r:" code "]")` で検出):

```bash
# 同 review-theme 短縮 code を持つ Open 行を検出 (1 件以上 → exit 0 = skip)
# CODE は 5 値固定 enum (sq/ra/ce/rb/rm)、正規表現メタ文字なし
uv run python scripts/alpha_factory/todo_manager.py list \
  | awk -v c="$CODE" '/^## Open/{open=1;next} /^##/{open=0} open && index($0, "[r:" c "]"){found=1} END{exit !found}'
```

`list --json` 等のサブコマンド追加は別 TODO に分離 (本 TODO は md only)。

### 2.7 失敗時 defensive + run 単位サマリ

| 状況 | 挙動 | summary 行 |
|------|------|-----------|
| `--tmp_dir` 不在 | error exit 1 (使い方ミス) | `{theme}: failed / 0 / missing --tmp_dir` |
| analysis-claude.md / analysis-codex.md 不在 | warning ログ、Run report のみで続行 | (続行) |
| Run report 不在 | warning ログ、Codex 議論を skip して early-exit | `{theme}: skipped / 0 / no run report` |
| Codex 失敗 | 30s 待って 1 リトライ → ダメなら skip して exit | `{theme}: failed / 0 / codex unavailable` |
| alpha-design 失敗 (1 件目) | エラーログ、2 件目以降は続行 | `{theme}: partial / N / alpha-design err on #1` |
| todo-add 失敗 | エラーログ、申し送りに残して exit | `{theme}: partial / N / todo-add err on #M` |
| 既に同 review-theme Open TODO あり | early-exit (exit 0)、申し送りも更新しない | `{theme}: skipped / 0 / open todo exists` |
| 全 Phase 正常完了 | success exit 0 | `{theme}: success / N / -` |

**run 単位サマリ**: `.cache/alpha_factory/post-run-review-summary-{run_id}.md` に各 Agent が完了時 1 行追記 (5 Agent → 5 行)。
silent failure を防ぎ、後続 cycle で「前回 5 テーマがどう走ったか」を観測可能にする。

### 2.8 hook 接続点 (本 TODO のスコープ) — launch owner 単一化

**Launch owner = `zenigame-fx-improve-cycle` Phase 1 末尾のみ**。
analyze-run は注記を更新するだけで、**実起動コードは追加しない**。

理由:
- improve-cycle が必ず Phase 1 で analyze-run を呼ぶため、analyze-run 側で起動すると同一 Run で二重起動になる
- analyze-run のスタンドアロン起動 (`/zenigame-fx-analyze-run` を直接呼ぶケース) では post-run-review は走らない。これは許容: スタンドアロン使用は人間の即席分析用途で、改善案の自動生成は improve-cycle 経由で行う設計
- runbook に「analyze-run 単独実行後に手動で改善案を出したい場合は `/zenigame-fx-post-run-review {theme} {run_id} --tmp_dir {tmp_dir}` をユーザー判断で実行」と明記する (運用 fallback)

**同一 run_id 再起動禁止**:
- improve-cycle が起動前に `.cache/alpha_factory/post-run-review-launched-{run_id}.json` の存在を確認
- 既存なら skip (二重起動防止)
- 新規起動時は launch 直後に同ファイルへ Agent ID + 起動時刻を記録

#### improve-cycle SKILL.md (Phase 1 末尾コメント書き換え)

```diff
- <!-- TODO(post-run-review-port): zenigame-fx-post-run-review 整備後に BG 起動を追加。現時点では no-op -->
+ <!-- post-run-review hook: 5 テーマを BG Agent (run_in_background: true) で起動 (launch owner = 本フェーズ単一)。
+      .cache/alpha_factory/post-run-review-launched-{run_id}.json で二重起動防止。
+      自動起動条件 / cooldown / theme rotation の判断ロジックは別 TODO -->
```

#### analyze-run SKILL.md (注記のみ復活、起動コードなし)

```diff
- × /zenigame-fx-post-run-review        (未移植、整備後に接続)
+ → /zenigame-fx-post-run-review        (改善案 hook 標準起動点は improve-cycle Phase 1 末尾。
+                                       analyze-run スタンドアロンでは起動しない)
```

ただし**自動起動の判断ロジック**（どの Run のどのテーマで起動するか / cooldown 等）は本 TODO のスコープ外。
本 TODO では「接続点を復活させる + launched marker による二重起動防止」までを含める。

## 3. ファイル構成

```
.claude/skills/zenigame-fx-post-run-review/SKILL.md   (新規 / md only)
docs/alpha_factory/concepts/post-run-review.md        (新規)
docs/alpha_factory/runbook.md                         (post-run-review 起動手順追記)
docs/alpha_factory/terminology.md                     (post-run-review / theme review 用語追加)
.claude/skills/zenigame-fx-improve-cycle/SKILL.md     (hook コメント書き換え)
.claude/skills/zenigame-fx-analyze-run/SKILL.md       (hook コメント書き換え)
```

テストは追加しない（skill は md のみ、ロジックは Claude Code の text 解釈に依存）。
834 tests passing baseline は維持される。

## 4. 反証検討 (C9 Falsification-first)

- **反証1**: 「FX 5 テーマでは細かすぎて、各テーマで毎回 0 件しか出ないのでは？」
  → 暫定: テーマ Open TODO が既にある場合は early-skip。何も出なくても申し送りに残せばよい。
  cooldown / 起動条件は別 TODO で調整。
- **反証2**: 「BG Agent 5 個並列はトークンコストが高い」
  → Codex 1 ラウンドは medium reasoning なので 1 セッションあたり数千 tok 程度。
  improve-cycle 全体に占める割合は小さい。autopilot の Phase 4A 5 並列も同様の負荷で運用済み。
- **反証3**: 「systemd / nohup と等価とは限らない（Claude Code 側の死活管理）」
  → autopilot の `run_in_background: true` は既に audit / implement で実績。
  fire-and-forget なので親側は気にしない設計。失敗しても申し送りが残らないだけで improve-cycle は続行可能。
- **反証4**: 「improve-cycle が複数 BG を投げると分析の結果が plan-and-design に間に合わない」
  → 設計上 plan-and-design とは独立非同期。post-run-review 由来の TODO は次サイクル以降の Phase 2 で消費される。
- **反証5**: 「テーマ間で類似案が重複生成される（cost-efficiency と robustness で同じ slippage 案）」
  → 重複チェックを「テーマ横断 Open TODO 全件」で行う設計（2.6 節）。
  ただし**並列起動の race condition**（2 Agent が同時に同じトピックで todo-add を試みる）は残る。
  → mitigation: `todo_manager.py next-id` は atomic（連番採番）なので ID 衝突は起きない。タイトル衝突は申し送りで吸収する想定（次回 1-2 で重複検出）。

## 5. スコープ外（明示）

- 自動起動条件の決定ロジック（cooldown / theme rotation / トリガー条件）— 別 TODO
- BG 起動結果の集約 / Discord 通知等 — 別 TODO
- post-run-review のテスト整備（skill md only のため）— 不要
- analyze-run の emergency_fix producer — 別 TODO
- focus-theme.json 連動 — `set-focus` skill 整備後

## 6. 残課題

- 起動条件 / cooldown / rotation の調整（運用してから決定）
- 申し送りファイルが膨れた場合の archive 戦略（運用してから決定）
- Codex 出力品質の評価（Run 数件貯まったら verify）

---

## レビュー観点 (Codex conceptual-review 用)

1. **テーマ分割の妥当性** — FX 5 テーマ (signal-quality / regime-awareness / cost-efficiency / robustness / risk-management) は debate-synthesis.md の設計次元と整合し、株版テーマと直交しているか？
2. **fire-and-forget 設計の妥当性** — Claude Code Agent (run_in_background: true) は systemd / Dramatiq の代替として妥当か？ 失敗時のリカバリは申し送りで十分か？
3. **重複チェック方針** — テーマ横断 Open TODO 比較で並列 Agent の race condition を申し送り側で吸収する案は妥当か？ 別の安全弁は必要か？
4. **hook 接続のスコープ** — 本 TODO は「接続点を復活させる」までで、自動起動条件は別 TODO とする分離は妥当か？
5. **株版機能との差分** — director-evolution / signal-predictive-power / japan-market / live-trading / performance / speed テーマを撤回することで、改善ループの抜け穴は生じないか？
