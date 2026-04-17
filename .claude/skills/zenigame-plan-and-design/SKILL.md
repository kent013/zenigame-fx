---
name: zenigame-plan-and-design
description: Alpha Factory改善の計画策定（TODO選定 + Codex合議 + 分析マージ + 改善策合議 + 詳細設計 + Codexレビュー）
argument-hint: "<tmp_dir> [run_id] [--repeat] [--skip-todo] [--skip-consensus]"
---

# Alpha Factory 改善計画策定

analyze-runの出力（analysis-claude.md, analysis-codex.md）をもとに、何をどう改善するか決定し、Codex承認済み詳細設計まで仕上げる。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `tmp_dir` ($1) | Yes | 中間成果物の保存先ディレクトリ（analyze-runの出力先と同一） |
| `run_id` ($2) | No | 分析対象のrun_id。状態ファイルから自動取得も可 |
| `--repeat` | No | 繰り返しモード。improve-cycleから渡される。Codex合議ループの最大回数を10に拡張 |
| `--skip-todo` | No | TODO実装スキップモード。Phase A（TODO選定・Codex合議）全体とPhase C-0（TODO由来設計読み込み）をスキップし、GA分析由来の改善のみで計画する |
| `--skip-consensus` | No | Codex合議スキップモード。Phase B-2/B-3（改善策Codex合議ループ）とPhase C-2/C-3（設計レビュー合議ループ）をスキップする |

**入力**（前提）:
- `{tmp_dir}/analysis-claude.md` — 自己分析結果
- `{tmp_dir}/analysis-codex.md` — Codex独立分析結果
- `docs/alpha-factory/TODO.md` — TODOバックログ

**出力**:
- `{tmp_dir}/todo-selection-codex.md` — TODO選定のCodex合議結果
- `{tmp_dir}/analysis-merged.md` — 分析マージ結果
- `{tmp_dir}/improvement-plan.md` — 最終改善計画
- `{tmp_dir}/detailed-design.md` — Codex承認済み詳細設計
- `{tmp_dir}/consensus-round-{N}.md` — 合議ラウンド記録
- `{tmp_dir}/design-review-round-{N}.md` — 設計レビュー記録

**独立利用**: 部分的 — analyze-runの出力が前提だが、設計だけやり直すことは可能。

---

## 思考原則 — 全議論に適用

**まず仮説を立てろ。** 何を検証したいのか、なぜそう考えるのか、どうなれば成功と判断するのかを明確にしてから手を動かせ。仮説なき改善はただの試行錯誤であり、結果から学ぶことができない。

探索空間は広い。今いる場所が正しいのか、もう少し先に進むべきか、横に移動すべきか、戻って別の道を探るべきかは、これまでの試行と観察の蓄積からしか判断できない。

**データに真摯に向き合え。** 成果だけでなく、多様性の変化、構造の揺らぎ、想定外のパターン — 全てが判断材料になる。数値を見て即座に閾値を弄るな。何が起きているのかを理解し、なぜそうなったのかを考え、どの方向に進むべきかを判断してから手を動かせ。

**先人の知恵を探せ。** 自分たちだけで登る必要はない。乗るべき巨人の肩があるなら乗れ。

**機能の名前に立ち返れ。** 名前はその機能が果たすべき役割を示している。現在の設計がその役割を果たしているか、常に問え。

**仕組みが機能していない段階で値を弄るな。** 閾値チューニングやフィールド追加（KAIZEN）は、設計の方向性が正しいと確認できてから行え。方向性が間違っているなら、値をいくら調整しても意味はない。設計そのものを見直せ（INNOVATION）。成果が出なければ早期に見切り、次の仮説へ進め。

**因果ループを切断するな。** 「XはYに影響しない」という主張に出会ったら、間接経路を含む因果ループ全体を追え。このシステムは観測→判断→介入→GAの結果→観測…のフィードバックループで動いている。ループの一部を「直接影響しないから無関係」と切断する主張は、ほぼ常に間違いである。主張の真偽ではなく、**切断された経路が本当に存在しないか**を検証せよ。

### Bad / Nice 例

**Bad**: Directorのfallbackがactiveより良い結果 → 「抑圧下限を0.03→0.10にしよう」「max-clipを入れよう」
**Nice**: Directorのfallbackがactiveより良い結果 → 「Directorという名前は"方向を示す"という意味だ。今の設計は毎Runの重み計算機でしかない。方向を示すとはどういうことか？」→ Multi-Run実験計画 + メモリ + 非同期深掘り分析という本来の役割を再定義

**Bad**: BollingerRevertのB効果が負 → 重みを0.03に抑圧
**Nice**: BollingerRevertのB効果が負 → だがfallback時にC-PASS最強クラスタの核になっている → 単独B効果で判断する設計自体が組み合わせシナジーを殺している → Directorに渡す情報と判断基準の再設計が必要

**Bad**: 10 Runの結果を集計 → 「C-PASS平均: active=5.14 vs fallback=6.33、Directorはnet-negativeです」
**Nice**: 10 Runの結果を集計 → ゲノム系譜を追跡 → fallbackのC-PASS個体の半数はwarmstart経由でDirector-active期の構造を継承している → 「fallbackの好結果はDirector由来の揺らぎが伝播した結果かもしれない」→ 単純比較では因果関係を見誤る

**Bad**: Codexと11ラウンド議論 → 閾値・スキーマ・ガードレールの詳細設計で合意
**Nice**: 「そもそもDirectorにメモリがないのはおかしくないか？選択→結果→学習→次の選択のループがない」→ 機能の本質的な欠陥を指摘してから設計を議論

---

## 使命（North Star）— 絶対遵守

> **Alpha Factoryの使命は「`config/alpha_factory/default.yaml` → `live_criteria` を全て満たすイントラデイ戦略個体を1つ見つけ出すこと」である。**
>
> Stage C通過は最低条件。使命達成 = `live_criteria` の全指標を同時に満たすC-PASS個体の出現。
> 達成後は `live_criteria` の各閾値を引き上げて次の水準を設定する（漸進的目標更新）。

**絶対的な制約（イントラデイ）**: スイングトレード（オーバーナイト保有）は行わない。

## 禁止事項（自分・Codex双方に適用）

| # | 禁止事項 | 理由 |
|---|---------|------|
| 1 | **ショート（空売り）売買の導入** | 信用取引のリスク・コスト・制度的制約から対象外 |
| 2 | **A・B・C評価期間を強い根拠なしに延長する** | 過学習の隠蔽 |
| 3 | **見た目の数値をよくしようとする改善** | 数値操作は無意味 |
| 4 | **GAをハックしてステージを進めようとする** | フィットネス関数の歪曲 |
| 5 | **閾値をいたずらに緩和してステージを飛ばす** | 安易な緩和 |
| 6 | **やたらに複雑な案を提案する** | コストが見合わない施策 |
| 7 | **取引回数を削減して見かけの成績を上げようとする** | 使命の「取引回数が多い」に反する |

## 分析方針（厳守）

1. **取引回数削減による見かけの改善を追わない**
2. **全個体の平均値を追わない — Top個体の特性を見よ**
3. **シグナル予測力の根本強化が最優先**

---

## コンテキスト圧縮対策

状態ファイル `.cache/alpha_factory/current_cycle_state.json` を各ステップの開始・完了時に更新する。

---

## Phase A: TODOリスト選定 & Codex議論

**`--skip-todo` 時は Phase A 全体をスキップ**して Phase B へ進む。`selected_todos = []`, `skip_todos = []`, `cycle_focus = "ga_improvements"` で固定。

### A-1. TODOリストの確認と選定

**Emergency Fix モードの場合（状態ファイル `emergency_fix.detected == true`）**: Phase A 全体を**スキップ**して Phase B へ進む。バグ修正が唯一の施策であり、TODO選定は不要。

`scripts/todo_manager.sh` を使ってOpenテーブルを取得する（`Read` でファイル全体を読み込む必要なし）:

```bash
open_table=$(bash scripts/todo_manager.sh list-open)
```

**TODOが1件もない場合（データ行なし）**: Phase A をスキップして Phase B へ進む。

**TODOがある場合**: 選定の前に、古いTODOの棚卸し判断を行う。

**【滞留TODOの判断】**:
Open TODOの追加日時を確認し、Closed テーブル直近5件の完了日時と比較する。直近5件は以下で取得する:

```bash
closed_tail=$(bash scripts/todo_manager.sh list-closed-tail 5)
```

**直近5件のClosed TODOの完了日時よりも追加日時が古いTODO**がある場合、そのTODOは複数Runにわたって実装されずに滞留している。

滞留TODOごとに概念設計を `Read` して以下を判断する:

| 判断 | 条件 | アクション |
|------|------|----------|
| **優先度を上げて実装** | 問題が依然として存在し、設計も概ね有効 | 今回の選定で優先的に採用する |
| **post-run-reviewに委ねる** | 設計が古く現コードと乖離している可能性が高い | 今回の選定から除外し、post-run-reviewの再評価を待つ |

判断結果を `analysis-claude.md` に記録する:
```markdown
## 滞留TODO判断
| ID | タイトル | 追加日時 | 滞留Run数 | 判断 | 理由 |
|----|---------|--------|----------|------|------|
```

**【Conditional自動昇格チェック】**:

棚卸しの後、Conditionalテーブルのトリガー条件を評価する。

```bash
conditional_table=$(bash scripts/todo_manager.sh list-conditional)
```

**Conditionalが1件もない場合**: スキップ。

**Conditionalがある場合**: 各項目のトリガー条件を直近Run結果・メトリクス（`analysis-claude.md`, `analysis-codex.md`）から評価する。

| 評価結果 | アクション |
|---------|----------|
| **条件成立** | `promote-conditional` で Open へ昇格。昇格した項目は今回の選定候補に含める |
| **条件未成立** | 何もしない（次サイクルで再評価） |
| **条件が陳腐化** | 条件自体が不要になった場合は `obsolete` で廃止 |

```bash
# 条件成立時
today=$(date '+%Y-%m-%d %H:%M')
bash scripts/todo_manager.sh promote-conditional "{todo_id}" "${today}"
```

昇格結果を `analysis-claude.md` に記録する:
```markdown
## Conditional昇格チェック
| ID | タイトル | トリガー条件 | 評価結果 | 理由 |
|----|---------|-------------|---------|------|
```

**【最優先】`standalone` タスクの確認**:
- Open テーブルに `standalone` モードのタスクが **1件でも存在する場合**:
  - 優先度が最も高い `standalone` タスクを **1件だけ** 選定する
  - `incremental` タスクは今回のサイクルでは選定しない（混在禁止）
  - この場合、Phase B 以降は「standalone タスクのみのサイクル」として動作する
    - **Phase B-1（分析マージ）は通常通り実行し `analysis-merged.md` を作成する**
    - Phase B-1 完了後、**`analysis-merged.md` のパスを状態ファイルの `deferred_analyses` リストに追記**する
    - Phase B-2/B-3（改善策合議）は「詳細設計に問題がないか」の最終確認のみ行う
    - Phase C 以降は TODO 由来の詳細設計を直接使用し、新規設計は行わない
  - Run 完了後の次サイクルでは再度 TODO を確認し、残りの `standalone` タスクを処理する

**`standalone` タスクが0件の場合**: 以下の `incremental` 選定基準で最大3件を選定する。

選定基準（優先度順）:
0. **フォーカステーマ優先**: `.cache/alpha_factory/focus-theme.json` のテーマに該当するTODOを最優先で選定
1. **モード**: `incremental` のものを対象とする
2. **優先度**: Critical → High → Medium → Low
3. **関連性**: ゲノム分析結果で浮かび上がったボトルネックと同一コンポーネントを扱うもの
4. **競合なし**: GA分析由来の改善施策と同一ファイル・同一関数を変更しない確信があるもの

**選定したTODOの詳細設計ファイルを `Read` する**:
- 各選定TODOの「詳細設計」列のリンク先ファイルを `Read` する
- 概念設計も必要に応じて `Read` して背景を把握する

選定結果を `analysis-claude.md` の末尾に追記:

```markdown
## TODO由来の改善候補

| ID | タイトル | 優先度 | 判定 | 理由 |
|----|---------|--------|------|------|
```

**状態ファイル更新（仮）**: `selected_todos` に候補リストを記録。

### A-2. Codexと実装候補を議論（全TODO関係分析含む）

**トリガー**: Open TODO が 1 件以上存在する場合に実行。0 件の場合はスキップ。

`zenigame-codex-review` スキルの**One-shotモード**に従い、プロンプトファイルを作成してCodexに依頼する。

**model**: `gpt-5.3-codex`
**reasoning**: `medium`
**label**: `todo-selection`

使命・禁止事項は zenigame-codex-review により自動挿入。system部には役割・タスク固有の指示のみ記載。

**system**:
```
あなたはAlpha FactoryのGA改善を支援するCodexです。最新のRUN分析結果とTODOリスト全体を踏まえて、今回の改善サイクルで実装すべき施策を議論してください。

（使命・禁止事項は zenigame-codex-review スキルにより自動挿入済み）

【分析上の重要原則】
- 全個体の平均値ではなくTop 5-10個体の特性で判断すること
- Q-band分析でQ1最良→tc減らせは統計的錯覚
- Run 79でTNVルックアヘッド修正後に成績90%消失。シグナル予測力の根本強化フェーズ

【判断基準 — 実装候補選定】
0. **【最優先】フォーカステーマ「{focus_theme}」のTODO**: このテーマに該当するTODOは他のすべての施策より優先して選定すること。
{focus_policy が null でない場合に以下を追加:}
   **【フォーカスポリシー】**: 「{focus_policy}」
1. 今回のRUN分析で浮かび上がった問題に直接対処するTODOを優先
2. RUN由来の改善施策と競合しないTODOを選ぶ
3. 1サイクルで並走可能なTODO数（最大3件）を守る
4. 優先度を尊重しつつ、RUN文脈との関連性も考慮

【分析観点 — TODO全体の関係整理】
1. **重複・統合候補**: 同一の問題を扱う、または類似実装になるTODOの組み合わせ
2. **陳腐化**: すでに解決済み・不要になったOpen TODO
3. **依存スキップ**: 「このTODOを実装すると、別のTODOが実装不要になる」依存関係
4. **相性**: 同一サイクルで並走すると相乗効果が高い、または相性が悪い組み合わせ

【メタ過学習ガード — GAハイパーパラメータ変更の分類（必須）】
date_poolは約1年分（~245営業日≒12ヶ月）。同じデータに対してハイパーパラメータを繰り返し調整するのはメタ過学習。
GAハイパーパラメータの数値変更を推薦する場合、各施策に分類を明記すること:
- **Structural**: 新機能・新ガードの追加 → APPROVE可
- **Principled Parametric**: 理論に基づく数値設定（根拠明示必須） → APPROVE可
- **Reactive Parametric**: 「直近RunでXが悪かったからYを調整」→ 原則REJECT、構造的対策に変換を促す

【出力形式】
**Section A: 実装候補の判定**
**Section B: TODO全体の関係分析**
**Section C: 総合推薦**
**Section D: TODO vs GA改善のバランス判断**
（ga_improvements / todos / mixed の3択）

日本語で出力。
```

**user**:
```
## 最新RUN分析サマリー
{analysis-claude.md の「分析サマリー」「ボトルネック特定」「改善仮説」セクション}

## 論理バグ探索結果
{Step 4 で発見したバグ候補、または「疑わしい箇所なし」}

## 最近クローズされたTODO（直近5件）
{TODO-closed.md の Closed テーブルの末尾5行}

## Open TODO 全件
{TODO.md の Open テーブル全体}

## Conditional TODO 全件
{TODO.md の Conditional テーブル全体（0件の場合は「なし」）}

## 候補として選定したTODOの詳細設計サマリー
{各候補 TODO の詳細設計ファイルから「目的」「変更内容の概要」「期待効果」を抜粋}

## 質問
### A. 実装候補の確定
### B. TODO全体の関係分析
### C. 総合推薦
### D. TODO vs GA改善のバランス判断
```

**合議結果の反映**:

| Codex の判定 | 対応 |
|-------------|------|
| 今回実装を推薦 | `selected_todos` に追加 |
| 次回以降を推薦 | 理由を精査。同意すれば見送り |
| RUN問題と競合 | 見送り |
| 廃止推薦（陳腐化） | `skip_todos` に `{id, reason}` で追加。**reason は `design stale: {詳細}` 形式** |
| 統合推薦 | `merge_candidates` に `{ids, note}` で追加 |
| 依存スキップ | `skip_todos` に `{id, reason: "superseded by T001"}` で追加 |

**Section D の結果を反映**:

| Codex推薦 | 対応 |
|-----------|------|
| `ga_improvements` | `selected_todos` を空にし、GA分析由来の改善のみ計画 |
| `todos` | 改善計画を最小化し、TODO実装を中心にする |
| `mixed` | 両方を組み合わせる（合計3件以内） |

`cycle_focus` を状態ファイルに記録。

Codex の議論結果を以下に保存:
```
{tmp_dir}/todo-selection-codex.md
```

---

## Phase B: 分析マージ & 改善策合議

### B-1. 分析結果のマージ

`analysis-claude.md` と `analysis-codex.md` を読み込み、以下を統合:

1. **共通する発見**: 両者が一致している問題点 → 高確度
2. **独自の発見**: 片方のみ指摘した問題点 → 検証要
3. **矛盾する見解**: 異なる結論が出た点 → 合議で解決

マージ結果を以下に保存:
```
{tmp_dir}/analysis-merged.md
```

**standalone サイクルの場合**: `analysis-merged.md` 作成後、状態ファイルの `deferred_analyses` リストにこのパスを追記して保存する。

フォーマット:
```markdown
# マージ分析: Run {N}

## 合意事項（両者一致）
## Claude独自の発見
## Codex独自の発見
## 矛盾・要議論
## 統合改善提案（優先度順）
| # | 提案 | 優先度 | 出所 | 期待効果 |
|---|------|--------|------|---------|
```

### B-2. Codexと改善策の合議

**`--skip-consensus` 時は B-2/B-3/B-4 をスキップ**。B-1のマージ結果から Claude が単独で改善計画を確定し、`improvement-plan.md` を直接作成して Phase C へ進む。

マージ結果をCodexに送り、改善策について合議する。

`zenigame-codex-review` スキルの**セッションモード**に従い、プロンプトファイルを作成してCodexに依頼する（合議ループのため文脈維持）。

**model**: `gpt-5.3-codex`
**reasoning**: `medium`
**label**: `consensus`

使命・禁止事項は zenigame-codex-review により自動挿入。system部には役割・タスク固有の指示のみ記載。

**system**:
```
あなたはAlpha Factoryの改善についてClaudeと合議しているCodexです。以下のマージ分析に基づいて、最終的な改善計画を策定してください。

（使命・禁止事項は zenigame-codex-review スキルにより自動挿入済み）

【improve-cycleの守備範囲】
- 高速化TODO消化、GAパラメータ軽量調整、バグ修正、post-run-review TODO実装
- GA設定変更ルール（AGENTS.md厳守）
- プリミティブ新規設計・大幅改良はpost-run-review担当

【メタ過学習ガード — GAハイパーパラメータ変更の分類（必須）】
date_poolは約1年分（~245営業日≒12ヶ月）しかない。同じデータに対してハイパーパラメータを繰り返し調整するのはメタ過学習（GAの中の過学習は防いでいるが、改善サイクル自体が同じデータに過学習する）。

GAハイパーパラメータ（regime_penalty_weight, pnl_cv_threshold, crossover_rate等の数値）を変更する施策は、以下の分類を各施策に必ず明記すること:

| 分類 | 定義 | 判定 |
|------|------|------|
| **Structural** | 新機能・新ガード・新プリミティブの追加 | APPROVE可 |
| **Principled Parametric** | 一般原則・理論に基づく数値設定。「なぜその値か」の理論的根拠あり | APPROVE可（根拠明示必須） |
| **Reactive Parametric** | 「直近RunでXが悪かったからYを調整」系の変更 | 原則REJECT。構造的対策に変換を促す |

Reactive Parametricの例: 「Run 140で月次Sharpeのバラつきが大きい → regime_penalty_weight 0.5→1.0」— これは同じ12ヶ月への当てはめ。代わりに「なぜ月次バラつきが大きいのか」の構造的原因（特定プリミティブの季節依存性、データカバレッジ不足等）に対処する施策を推薦すること。

【合議ルール】
- 各提案に対して APPROVE / MODIFY / REJECT で判定
- MODIFY の場合は具体的な修正案を提示
- REJECT の場合は理由を明記
- 日本語で出力
```

**user**: マージ分析の内容

### B-3. 合議ループ

Codexの回答を精査し、以下を繰り返す:

**セッション再開**: `zenigame-codex-review` スキルのセッションモード（Round N）に従い、同じ SESSION_ID で `codex-vscode exec resume` を実行する。Round 2以降のプロンプトには対応内容・修正案のみ記載（使命・禁止事項の再挿入は不要）。

1. Codexの判定に**同意**する項目はそのまま採用
2. **異議がある**項目は根拠を添えて再議論
3. **全提案の判定が確定するまで**ループ（通常: 最大3ラウンド、繰り返しモード: 最大10ラウンド）
4. **各イテレーションで使命チェック**: 使命から逸脱した提案は即座にREJECT

各ラウンドの会話を保存:
```
{tmp_dir}/consensus-round-{N}.md
```

### B-4. 最終改善計画の確定

合議結果を最終改善計画として保存:
```
{tmp_dir}/improvement-plan.md
```

フォーマット:
```markdown
# 最終改善計画: Run {N} → Run {N+1}

## 合議ステータス: CONSENSUS REACHED (Round {N})

## 確定施策一覧
| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | 合議結果 |
|---|--------|------|---------|--------|---------|---------|

## 却下された提案
| # | 提案 | 却下理由 |
|---|------|---------|

## 次フェーズへの申し送り
```

**使命・禁止事項チェック**: 最終改善計画の確定前に、全施策が使命・禁止事項に違反していないか精査する。

### B-5. ユーザー報告

```
## Phase B 完了: 改善策合議

### 確定施策
1. [施策名] - [概要]（合議: APPROVED）

### 却下された提案

→ Phase Cに進みます（詳細設計 & Codexレビュー）
```

---

## Phase C: 詳細設計 & Codexレビュー合議

### C-0. TODO由来施策の詳細設計読み込み

**`--skip-todo` 時はスキップ**（`selected_todos` は空のため）。

`selected_todos` に記録された採用TODOがある場合に実行。0件ならスキップ。

**採用TODO ごとに以下を実施する**:

1. `docs/alpha-factory/TODO.md` の当該行から「詳細設計」リンク先を取得
2. `Read` ツールで詳細設計ファイルを読み込む
3. 変更対象ファイルと変更内容の概要を把握
4. 変更対象ファイルを `Read` して現行コードと整合性を確認

**競合チェック**:
- Phase B で確定した GA分析由来の施策と同一ファイル・同一関数を変更する場合は「競合あり」として報告
- 競合がある場合、TODO施策の組み込みを見送り、`improvement-plan.md` にコメント記録

**整合性が確認できた TODO由来施策は、C-1 の詳細設計書に組み込む**:
- 施策番号を `T{todo_id}` プレフィックスで区別
- 既存の詳細設計ファイルをそのまま転記
- C-2 の Codex レビュー対象に含める

### C-1. 詳細設計書の作成

`improvement-plan.md` の確定施策に基づき、詳細設計書を作成する。

各施策について以下を記載:
- **変更ファイルと行番号**: 具体的な変更箇所
- **Before/After**: 変更前後のコード
- **テスト計画**: 既存テストへの影響と追加テスト
- **リスク**: 副作用・後退の可能性

> **⚠ 波及変更チェック（必須）**: インターフェース変更が発生する場合、`AGENTS.md` および `.claude/skills/zenigame-*/skill.md` も変更対象として施策に明示すること。

保存先:
```
{tmp_dir}/detailed-design.md
```

フォーマット:
```markdown
# 詳細設計: Run {N+1}施策

## 施策一覧
| # | 施策名 | 変更ファイル |
|---|--------|------------|

## C1: {施策名}

### 変更箇所
### 波及変更（AGENTS.md・スキルファイル）
### 現行コード
### 変更後コード
### テスト計画
### リスク

## Run {N+1} 実行パラメータ
| パラメータ | 値 | R{N}からの変更 |
|-----------|-----|--------------|
```

### C-2. Codexによる詳細設計レビュー

**`--skip-consensus` 時は C-2/C-3 をスキップ**。C-1 の詳細設計書をそのまま最終版として確定し、Phase C-4 へ進む。

`zenigame-codex-review` スキルの**セッションモード**に従い、プロンプトファイルを作成してCodexに依頼する（レビューループのため文脈維持）。

**model**: `gpt-5.3-codex`
**reasoning**: `high`
**label**: `design-review`

使命・禁止事項は zenigame-codex-review により自動挿入。system部には役割・タスク固有の指示のみ記載。

**system**:
```
あなたは経験豊富なクオンツ・システムアーキテクトです。以下のAlpha Factory改善の詳細設計をレビューしてください。

（使命・禁止事項は zenigame-codex-review スキルにより自動挿入済み）

【重要な前提】
- Python 3.13 + numpy + pandas + multiprocessing
- NSGA-II遺伝的アルゴリズムによるイントラデイ戦略最適化
- DSLベースの戦略表現: ProhibitionMask（ハード制約） + Clauseベース合成（directional + local_gate） × Risk。詳細は docs/alpha-factory/clause-architecture.md
- 実行環境: macOS, 6ワーカー並列

【レビュー観点】
1. コードの正確性（ロジックエラー、エッジケース）
2. 既存コードとの整合性（パターン、命名規約）
3. パフォーマンスへの影響
4. テスト計画の網羅性
5. 副作用・後退リスク
6. 考慮漏れ
7. 波及変更の網羅性（AGENTS.md・スキルファイルの変更漏れは [Critical]）
8. **ルックアヘッドバイアス**（プリミティブ変更がある場合は必須。TNV旧実装の再発防止）

【出力形式】
- 各施策ごとに判定: APPROVE / REQUEST_CHANGES
- 指摘は [Critical] [Warning] [Suggestion] で分類
- 全体判定: APPROVED / CHANGES_REQUESTED
- 日本語で出力
```

**user**: 詳細設計書の内容 + 関連する現行コードの抜粋

### C-3. レビュー合議ループ

**セッション再開**: `zenigame-codex-review` スキルのセッションモード（Round N）に従い、同じ SESSION_ID で `codex-vscode exec resume` を実行する。Round 2以降のプロンプトには対応内容・修正案のみ記載（使命・禁止事項の再挿入は不要）。

1. **[Critical]** の指摘は**必ず対応**
2. **[Warning]** の指摘は**対応を検討**
3. **[Suggestion]** は任意で採用

**対応マトリクス**を作成:
```markdown
| # | 指摘 | 重要度 | 対応 | 詳細 |
|---|------|--------|------|------|
```

**各イテレーションで使命チェック**: 使命から逸脱した修正は採用しない。

**合議終了条件**: Codexの全体判定が **APPROVED**（Critical/Warning = 0）になるまで。通常: 最大3ラウンド、繰り返しモード: 最大10ラウンド。

各ラウンドの結果を保存:
```
{tmp_dir}/design-review-round-{N}.md
```

最終確定版を上書き保存:
```
{tmp_dir}/detailed-design.md  (最終版)
```

**使命・禁止事項の最終チェック**: 最終確定版の設計全体が使命・禁止事項に違反していないか精査する。

### C-4. ユーザー報告

```
## Phase C 完了: 詳細設計合議

### 合議結果: APPROVED (Round {N})
### 施策一覧
1. C1: [施策名] - [変更ファイル]

### Codexからの主要指摘と対応

→ 詳細設計が確定しました。implementで実装に進みます。
```

---

## 状態ファイル更新

各ステップの開始・完了時に `.cache/alpha_factory/current_cycle_state.json` を更新する:

```json
{
  "skill": "plan-and-design",
  "phase": "{phase_A / phase_B / phase_C}",
  "phase_detail": "{現在のステップ}",
  "run_id": "{run_id}",
  "tmp_dir": "{tmp_dir}",
  "cycle_focus": "{ga_improvements / todos / mixed}",
  "selected_todos": ["T001", "T003"],
  "skip_todos": [{"id": "T002", "reason": "superseded by T001"}],
  "merge_candidates": [{"ids": ["T004", "T005"], "note": "統合"}],
  "improvement_plan": "{tmp_dir}/improvement-plan.md",
  "detailed_design": "{tmp_dir}/detailed-design.md",
  "last_updated": "{ISO8601}"
}
```

---

## エラーハンドリング

### Codex CLIエラー
- `codex-vscode exec` が非ゼロ終了コードを返した場合、30秒待って1回リトライ
- **通常モード**: 2回連続失敗でユーザーに報告しCodexなしで続行するか確認
- **繰り返しモード**: 2回連続失敗で自動でCodexなしで続行

---

## 使用例

### 例1: improve-cycleからの呼び出し
```
/zenigame-plan-and-design --tmp_dir devnotes/20260226-1200-alpha-improve
```

### 例2: 設計やり直し（分析結果は既存のものを使用）
```
/zenigame-plan-and-design --tmp_dir devnotes/20260226-1200-alpha-improve --run_id run_20260226_120000
```
