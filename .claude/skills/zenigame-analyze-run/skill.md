---
name: zenigame-analyze-run
description: Alpha Factory RUN結果の深層分析（自己分析 + Codex並列分析 + post-run-reviewバックグラウンド起動）
argument-hint: "[run_id] [focus_theme] [--tmp_dir <path>]"
---

# Alpha Factory RUN深層分析

前回Runの結果を深層分析し、Codex（GPT-5 Codex）に独立分析を並行依頼し、post-run-reviewをバックグラウンド起動する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_id` ($1) | No | 分析対象のrun_id（例: run_20260219_212426）。省略時は最新Runを自動検出 |
| `focus_theme` ($2) | No | フォーカステーマ（省略時は focus-theme.json から読み込み） |
| `--tmp_dir` | No | 中間成果物の保存先ディレクトリ（省略時は devnotes/{YYYYMMDD-HHMM-alpha-improve}/ を自動生成） |

**出力**:
- `{tmp_dir}/analysis-claude.md` — 自己分析結果（7次元 + 論理バグ探索 + 実装影響チェック）
- `{tmp_dir}/analysis-codex.md` — Codex独立分析結果
- post-run-review 5テーマのバックグラウンドセッション起動済み

**独立利用**: YES — 「このRunだけ分析して」に対応。improve-cycle外でも単体実行可能。

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
| 2 | **A・B・C評価期間を強い根拠なしに延長する** | 過学習の隠蔽・見かけ上の安定化につながる |
| 3 | **見た目の数値をよくしようとする改善** | Sharpe/WR等の数値を実質を伴わずに操作する施策は無意味 |
| 4 | **GAをハックしてステージを進めようとする** | フィットネス関数の歪曲・特殊ケース追加でStage通過を人為的に達成する行為 |
| 5 | **閾値をいたずらに緩和してステージを飛ばす** | Stage B Sharpe≥0.2等の閾値を安易に下げる行為 |
| 6 | **やたらに複雑な案を提案する** | 改善効果に対してコストが見合わない施策 |
| 7 | **取引回数を削減して見かけの成績を上げようとする** | tc減少は見かけ上Net+に近づくが、統計的に有意でなく使命の「取引回数が多い」に反する |

## 分析方針（厳守）

1. **取引回数削減による見かけの改善を追わない**: Q-band分析の全個体平均で「Q1最良」→「tc減らせ」は統計的錯覚
2. **全個体の平均値を追わない — Top個体の特性を見よ**: Top 5-10個体のシグナル構成・パラメータ・TC・Netが重要
3. **シグナル予測力の根本強化が最優先**: TNVバイアス除去後（Run 79〜）はプリミティブの予測力が取引コストを上回れない状態

## 分析のトーン・視点（厳守）

### Top個体中心の分析

使命は「飛び抜けて成績が高い戦略を1つ生み出す」こと。集団の平均統計は分析の主題ではない。

- **Top 1-5個体**のシグナル構成・パラメータ・Stage C各窓での成績が分析の中心
- 「B-PASS全体の平均net/trade」「C不通過個体の平均C-Sharpe」「A-PASS率の推移」は補足情報に留める
- 考察の主題は常に「最良個体はなぜC-PASSに届かないのか、何を変えれば届くのか」

### 形容詞の禁止

数値に「大幅」「壊滅的」「改善」「良好」等の量的形容詞をつけない。数値だけ書く。

### 使命との距離感

- C-PASS=0の場合、それが最重要事実
- Run間の微小変動を「施策の効果」と断定しない（確率的評価のRun間変動を考慮）
- 「前向きな兆候」「方向性は正しい」等のポジティブ修飾語を使わない
- この分析はplan-and-designやpost-run-reviewに渡される。楽観的な分析は下流の判断を歪める

---

## コンテキスト圧縮対策

状態ファイル `.cache/alpha_factory/current_cycle_state.json` を各ステップの開始・完了時に更新する。

圧縮復帰時はこのファイルを `Read` して現在の状態を復元してから作業を再開すること。

**Writeツールで更新**する（Bashのechoは使わない）。

---

## 事前準備

### 0-1. tmp_dir の決定

`tmp_dir` 引数が指定されている場合はそれを使用。省略時:
```bash
date '+%Y%m%d-%H%M'
```
で `devnotes/{YYYYMMDD-HHMM}-alpha-improve/` を作成:
```bash
mkdir -p devnotes/{YYYYMMDD-HHMM}-alpha-improve
```

### 0-2. 状態ファイルの更新

```json
{
  "skill": "analyze-run",
  "phase": "analysis",
  "phase_detail": "0-2. 初期化",
  "run_id": "{run_id}",
  "tmp_dir": "{tmp_dir}",
  "last_updated": "{ISO8601}"
}
```

---

## Step 1: 積み残し分析の統合（incrementalサイクルのみ）

状態ファイル `.cache/alpha_factory/current_cycle_state.json` を `Read` して `deferred_analyses` リストを確認する。

**リストが空でない場合**（過去の standalone サイクルで蓄積された分析がある）:
- 各パスのファイルを `Read` で読み込む
- 分析内容を「積み残し分析」として把握する（Step 3 の自己分析・Step 5 の Codex コンサルテーションに反映）
- **状態ファイルの `deferred_analyses` を `[]` にリセット**して保存する

**リストが空の場合**: このステップをスキップ。

> **standalone サイクルでは** このステップは実行しない。

---

## Step 2: 前回Runの特定とゲノムアーカイブ分析

**`/zenigame-analyze-genome-archive` スキルを呼び出す**。

```
/zenigame-analyze-genome-archive {run_id}
```

引数`run_id`が省略された場合は最新のgenomes parquetを自動検出:
```bash
ls -lt .cache/alpha_factory/runs/genomes_*.parquet | head -1
```

分析スキルの出力（9ステップ分析結果）を取得・記録する。

### Step 2b: フォーカステーマの読み込み

`.cache/alpha_factory/focus-theme.json` を `Read` する。ファイルが存在すれば `theme` フィールドの値を `focus_theme` 変数として保持し、`policy` フィールドの値を `focus_policy` 変数として保持する（`policy` が存在しない or `null` の場合は `focus_policy = null`）。存在しなければ `focus_theme = null`, `focus_policy = null`（フォーカスなし）。

フォーカステーマが設定されている場合、以降の分析でそのテーマに関連する問題・改善機会を重点的に掘り下げること。

### Step 2c: 前回Runレポートの読み込み

```bash
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || exit 1
latest_report=$(find reports/run-reports -maxdepth 2 -name "run-${latest_n}.md" -not -path '*/old/*' | head -1)
```

最新のRunレポートを読み、実行パラメータ・考察・次のアクションを把握する。

### Step 2d: RUN障害チェック（最優先）

Runレポートと最新ログを確認し、**RUNがクラッシュ・異常終了していないか**を判定する。

**確認対象**:
```bash
ls -lt .cache/alpha_factory/runs/alpha_factory_*.log | head -1
```

以下のいずれかが確認できた場合は **Emergency Fix モード** に入る:
- Runレポートに「FAILED」「Error」「Exception」「Traceback」等の異常終了の記録がある
- ゲノムアーカイブが空またはほぼ空（世代0で止まっている）
- ログに未捕捉例外・プロセス強制終了が記録されている
- 前回Runが正常完了せずに本スキルが起動された

**Emergency Fix モードの動作**:

```
⚠️  RUN障害を検出しました
エラー概要: {エラーの内容}
推定原因: {コードのどこで何が起きたか}

→ Emergency Fix モードに入ります。
```

1. 状態ファイルの `emergency_fix` を記録:
   ```json
   {"detected": true, "error_summary": "...", "suspected_file": "...", "suspected_cause": "..."}
   ```
2. **Step 3〜5 をスキップ**して Step 6（ユーザー報告）へ進む
3. 呼び出し元（improve-cycle）はこの情報をもとにバグ修正フローに分岐する

**正常完了の場合**: このステップをスキップして Step 3 へ進む。

---

## Step 3: 深層考察の実施（自分）

Step 2の情報をもとに、以下の観点で深層考察を行う:

| 観点 | 分析内容 |
|------|---------|
| **ボトルネック特定** | Stage B失敗の主因は何か（Sharpe壁 / コスト / 収益力 / 多様性）|
| **GA進化の質** | offspring vs randomのA-PASS率差、世代推移の健全性 |
| **シグナル有効性** | どのプリミティブが有効/死滅しているか、組み合わせ効果 |
| **パラメータ空間** | time_stop, max_pos, entry_threshold等の分布と最適域 |
| **日付窓依存性** | 特定月/期間への偏りがないか |
| **前回施策の効果** | 直前Runで適用した変更の効果判定 |
| **コスト構造** | gross/trade vs cost/tradeのバランス、改善余地 |

考察結果を以下のファイルに保存:
```
{tmp_dir}/analysis-claude.md
```

フォーマット:
```markdown
# 深層分析: Run {N} ({run_id})

## 分析サマリー
- [ゲノム分析結果を要約]

## ボトルネック特定
- [最重要の問題点]

## シグナル有効性
- [有効/死滅/要調整のプリミティブ]

## パラメータ空間
- [最適域の推定]

## 改善仮説（優先度順）
1. (★★★) ...
2. (★★☆) ...
3. (★☆☆) ...
```

### Step 3b: 実装影響チェック（standaloneサイクル後のみ）

**前のサイクルが standalone 実装だった場合**（状態ファイルで確認）、通常の分析に加えて以下を実施する:

前サイクルで実装した TODO タスクの詳細設計を `Read` し、**期待していた変化**を把握する。その上で現在の Run データを見て:

| チェック項目 | 確認内容 |
|------------|---------|
| **指標変化** | 実装が直接影響する指標の分布が期待通り変化したか |
| **副作用** | 意図しない指標悪化がないか |
| **バグ修正の効果** | バグ修正の場合、修正前の異常パターンが消えているか |
| **資本スケーリング** | 銘柄ユニバースの有効活用率が想定通りか |

チェック結果を `analysis-claude.md` の末尾に "## 実装影響チェック（T{ID}: {タイトル}）" セクションとして追記する。

---

## Step 4: 既存コードの論理バグ探索

ゲノム分析・Runレポートで見えた異常を手がかりに、Alpha Factory関連コードの論理バグを探索する。

**探索対象ディレクトリ**:
- `src/trading/alpha_factory/` — GA本体、フィットネス計算、ゲノム変異
- `src/trading/alpha_factory/signals/` — シグナルプリミティブ
- `src/trading/alpha_factory/exit_engine.py` — エグジットエンジン
- `src/trading/backtest/` — バックテストエンジン、コスト計算

**探索観点**:
| # | 観点 | 例 |
|---|------|-----|
| 1 | **計算ロジックの誤り** | フィットネス計算の符号ミス、平均と合計の取り違え、off-by-oneエラー |
| 2 | **条件分岐の漏れ** | エッジケース未処理（0除算、空配列、NaN伝播） |
| 3 | **状態管理の不整合** | リセットされるべき状態が世代間で残存、キャッシュの汚染 |
| 4 | **パラメータ適用の誤り** | clip範囲の上下逆、スケール変換の欠落、デフォルト値の不適切 |
| 5 | **データフローの断絶** | 変異で生成した値が実際のシグナル計算に反映されていない |
| 6 | **ルックアヘッドバイアス** | 未来バー参照、当日確定値の先取り、全期間統計量での正規化。詳細は `docs/alpha-factory/primitives.md` を参照 |

**手順**:
1. ゲノム分析結果から「不自然なパターン」を特定
2. 該当コードパスを `Read` / `Grep` で追跡し、ロジックを精査
3. 疑わしい箇所があれば `analysis-claude.md` の改善仮説にバグ修正候補として追記

**注意**: この段階では修正しない。発見のみ行い、plan-and-designフェーズの合議でCodexにも確認を求める。

---

## Step 5: Codexに独立分析を依頼（並行）

`zenigame-codex-review` スキルの**One-shotモード**に従い、プロンプトファイルを作成してCodexに依頼する。

**model**: `gpt-5.3-codex`
**reasoning**: `medium`
**label**: `analysis`

使命・禁止事項は `zenigame-codex-review` により自動挿入。system部には役割・タスク固有の指示のみ記載。

**system**: 以下のプロンプトを使用
```
あなたはクオンツトレーディングシステムの専門家です。遺伝的アルゴリズム（NSGA-II）によるイントラデイ戦略最適化システム「Alpha Factory」のGA実行結果を分析し、改善策を提案してください。

（使命・禁止事項は zenigame-codex-review スキルにより自動挿入済み）

【重要な前提】
- DSL（Domain Specific Language）ベースの戦略表現: ProhibitionMask（ハード制約） + Clauseベース合成（directional + local_gate × steep sigmoid gate） × Risk（リスク管理）。詳細は docs/alpha-factory/clause-architecture.md 参照
- NSGA-II多目的最適化: net_return, max_dd, exec_score, trade_count_violation
- Stage A（IS期間）→ Stage B（OOS期間）→ Stage C（ローリング検証）の3段階評価
- Stage B通過条件: Sharpe≥0.2, Return>0, WinRate≥0.3, Trades≥8, MaxDD>-15%
- リターン単位は %（IC比）。1.08 = 1.08% = 10,800円
- Sharpeは Raw（非年率化）

【improve-cycleの守備範囲 — 重要な役割分担】
improve-cycleは「サイクルを素早く回す」ことに集中する。以下がimprove-cycleの担当範囲:
- 高速化TODOの消化（イテレーション速度向上）
- GAパラメータの軽量な調整（crossover率、mutation率、immigration率等）
  - **GA設定変更ルール（AGENTS.md「GA設定変更の管理ルール」厳守）**:
    - 設定変更後は**最低2 RUN**回してから効果を判断する。1 RUNで撤回しない
    - 1 RUNで例外撤回が許されるのは: A-PASS率が直近5RUN平均比−50%以上 or Best B-Sharpeが−60%以上の場合のみ
    - 1回の変更は**2変数以内**。6パラメータ同時変更のようなショットガン変更は禁止
    - GA設定変更とsignal-predictive-power系/performance系/japan-market系TODOを同一RUNで同時変更しない
    - 評価期間中はspeed系・live-trading系TODOのみ並行実装可
- バグ修正（論理バグ探索で見つかった問題の修正）
- post-run-reviewで設計されたTODOの実装
**以下はimprove-cycleでは提案しないこと（post-run-review signal-predictive-powerテーマが担当）:**
- プリミティブの新規設計・大幅改良の提案
- シグナル予測力の深い分析に基づく新しいプリミティブの提案
- 既存プリミティブの計算ロジック変更・正規化方法の変更

【分析上の重要原則】
- **Top個体が全て**: 目標はA/B/C各1でいいから飛び抜けた個体を1つ生み出すこと。集団の平均統計は主題ではない
- **Top 1-5個体**のシグナル構成・パラメータ・Stage C各窓の成績・不通過原因が分析の中心
- 集団平均（A-PASS率、B-PASS全体のnet/trade等）は補足。主語にしない
- 集団の底上げに言及する場合は「なぜ底上げがTop個体の出現に必要か」の理論的根拠を示すこと
- **「Q1（低tc）が最良」は錯覚**: tc=10-15での月1%のNet+はOOS 60日で統計的に有意でない
- **歴史的文脈**: Run 79でTNVルックアヘッドバイアスを修正後、C-PASS: 0・B-Sharpe: 0.07。現在はシグナル予測力の根本的不足を解消するフェーズ
- **形容詞禁止**: 数値に「大幅」「壊滅的」「改善」等の量的形容詞をつけない。数値だけ書く

【分析観点】
1. **Top個体がC-PASSに届かない原因は何か**（どの窓で、何の指標が閾値未満か）
2. Top個体のシグナル構成・パラメータから、次に何を変異させれば突破に近づくか
3. シグナル（プリミティブ）の有効性と組み合わせ（データ分析のみ。プリミティブ改良提案はpost-reviewに委任）
4. コスト構造（Top個体のgross vs cost）
5. **既存コードの論理バグ**: 計算ロジックの誤り・条件分岐の漏れ・状態管理の不整合等がないか精査
6. 具体的な改善提案（コード変更レベルで、バグ修正・GA調整・高速化に限定）

【出力形式】
- 根本原因分析
- 改善提案（優先度 Critical / High / Medium で分類）
- 各提案に期待効果と実装難易度を明記
- 日本語で出力
```

**user**: 以下の情報を送信
```
## 前回Runレポート
{runレポートの内容}

## ゲノムアーカイブ分析結果
{Step 2の分析結果}

## 関連コード情報
- プリミティブ一覧: {primitives.mdの内容またはschema.pyの関連部分}
- 現行パラメータ範囲: {schema.pyのクリップ値}
- GA設定: {nsga2.pyの主要パラメータ}

{Step 1 で積み残し分析を読み込んだ場合のみ追加:}
## 過去の standalone サイクルからの積み残し分析
（以下の Run で観測された問題点・仮説を現在の分析に統合してください）
{各 deferred_analysis ファイルの内容}
```

Codexの分析結果を以下に保存:
```
{tmp_dir}/analysis-codex.md
```

---

## Step 5b: Post-Run Review起動（バックグラウンド）

Step 2〜5 の分析が完了した時点で、完了済みセッションをクリーンアップしてからpost-run-reviewをバックグラウンド起動する。

**起動前のスキップ判定（呼び出し側で実施）**:

`scripts/todo_manager.sh` を使って、テーマごとにOpen TODOの有無を確認する（`Read` でファイル全体を読み込む必要なし）。
Open TODOが1件以上あるテーマはセッションを**起動しない**（context節約のため）。

```bash
# テーマごとにOpen TODOの有無を判定
themes="speed live-trading performance japan-market signal-predictive-power"
launch_themes=""
skip_themes=""
for t in $themes; do
  if bash scripts/todo_manager.sh has-open-theme "$t"; then
    skip_themes="$skip_themes $t"
  else
    launch_themes="$launch_themes $t"
  fi
done
```

スキップしたテーマはユーザーに報告する:
```
[SKIP] post-run-review: {skip_themes} — Open TODOあり、セッション起動をスキップ
[LAUNCH] post-run-review: {launch_themes}
```

```bash
# 完了済み・ゾンビセッションをクリーンアップ
uv run python scripts/cleanup_claude_sessions.py --cleanup
```

**launch_themes に含まれるテーマのみ**起動する。**launch_themes が空の場合は1件も起動しない。**

```bash
mkdir -p .cache/alpha_factory
# unset CLAUDECODE: ネストセッション検出を回避
unset CLAUDECODE
# launch_themes に含まれるテーマのみループで起動（skip_themes は起動しない）
for t in $launch_themes; do
  nohup claude-vscode --dangerously-skip-permissions -p "/zenigame-post-run-review $t" \
    > ".cache/alpha_factory/post-run-review-${t}.log" 2>&1 &
done
```

**重要**: 上記のループを**そのまま実行する**こと。launch_themes 変数にはスキップ判定で残ったテーマのみが入っている。
5テーマ個別のnohupコマンドを手動で書き下さないこと（テーマの追加漏れ・スキップ漏れの原因になる）。

各セッションは独立して以下を自動実行する（完全自律・ユーザー介入不要）:
1. 最新Runレポート + analyze-runの分析成果の読み込み
2. テーマ別のCodex議論 → アイデア選定
3. `/zenigame-alpha-design` で概念設計 → 詳細設計
4. `/zenigame-todo-add` でTODO登録

ログは `.cache/alpha_factory/post-run-review-{theme}.log` で確認可能。

---

## Step 6: ユーザー報告

```
## analyze-run 完了: 深層分析

### 自分の分析
- [主要発見3点を箇条書き]

### 論理バグ探索結果
- [発見したバグ候補、または「疑わしい箇所なし」]

### Codexの分析（RUN分析）
- [主要発見3点を箇条書き]

### Emergency Fix
- {検出の有無。検出された場合はエラー概要と推定原因}

### 成果物
- 自己分析: {tmp_dir}/analysis-claude.md
- Codex分析: {tmp_dir}/analysis-codex.md
- post-run-review: {launch_themes}起動 / {skip_themes}スキップ（Open TODOあり）
```

---

## 状態ファイル更新

各ステップの開始・完了時に `.cache/alpha_factory/current_cycle_state.json` を更新する:

```json
{
  "skill": "analyze-run",
  "phase": "analysis",
  "phase_detail": "{現在のステップ}",
  "run_id": "{run_id}",
  "tmp_dir": "{tmp_dir}",
  "focus_theme": "{focus_theme}",
  "focus_policy": "{focus_policy}",
  "emergency_fix": null,
  "deferred_analyses": [],
  "last_updated": "{ISO8601}"
}
```

---

## エラーハンドリング

### Codex CLIエラー
- `codex-vscode exec` が非ゼロ終了コードを返した場合、30秒待って1回リトライ
- 2回連続失敗の場合、Codex分析なしで続行（analysis-codex.mdは「Codex分析スキップ（CLIエラー）」と記録）

---

## 使用例

### 例1: 最新Runを分析
```
User: /zenigame-analyze-run
```

### 例2: 特定Runを分析
```
User: /zenigame-analyze-run run_20260219_212426
```

### 例3: improve-cycleからの呼び出し（tmp_dir指定）
```
/zenigame-analyze-run {run_id} --tmp_dir devnotes/20260226-1200-alpha-improve
```
