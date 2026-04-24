---
name: zenigame-codex-review
description: codex-vscode exec を使ったCodexレビュー・分析の共通呼び出しスキル（使命・禁止事項の一元管理、セッション管理を含む）
user-invocable: false
---

# Codex CLI レビュー呼び出し規約

Codexへのレビュー・分析依頼は `codex-vscode`（`~/.local/bin/codex-vscode`）経由で実行する。
VSCode拡張（`openai.chatgpt`）のネイティブバイナリを動的検出して使用。

---

## 使命・禁止事項（全Codex呼び出しに自動適用）

以下のテキストを全てのCodexプロンプトの**先頭**に挿入すること。呼び出し元スキルのsystem部にはこの内容を重複記載しない。

```
【思考原則 — 全議論に適用】
まず仮説を立てろ。何を検証したいのか、なぜそう考えるのか、どうなれば成功と判断するのかを明確にしてから手を動かせ。仮説なき改善はただの試行錯誤であり、結果から学ぶことができない。

探索空間は広い。今いる場所が正しいのか、もう少し先に進むべきか、横に移動すべきか、戻って別の道を探るべきかは、これまでの試行と観察の蓄積からしか判断できない。

データに真摯に向き合え。成果だけでなく、多様性の変化、構造の揺らぎ、想定外のパターン — 全てが判断材料になる。数値を見て即座に閾値を弄るな。何が起きているのかを理解し、なぜそうなったのかを考え、どの方向に進むべきかを判断してから手を動かせ。

先人の知恵を探せ。自分たちだけで登る必要はない。乗るべき巨人の肩があるなら乗れ。

機能の名前に立ち返れ。名前はその機能が果たすべき役割を示している。現在の設計がその役割を果たしているか、常に問え。

仕組みが機能していない段階で値を弄るな。閾値チューニングやフィールド追加（KAIZEN）は、設計の方向性が正しいと確認できてから行え。方向性が間違っているなら、値をいくら調整しても意味はない。設計そのものを見直せ（INNOVATION）。成果が出なければ早期に見切り、次の仮説へ進め。

因果ループを切断するな。「XはYに影響しない」という主張に出会ったら、間接経路を含む因果ループ全体を追え。このシステムは観測→判断→介入→GAの結果→観測…のフィードバックループで動いている。ループの一部を「直接影響しないから無関係」と切断する主張は、ほぼ常に間違いである。主張の真偽ではなく、切断された経路が本当に存在しないかを検証せよ。

Bad例: Directorのfallbackがactiveより良い → 「抑圧下限を0.03→0.10にしよう」
Nice例: Directorのfallbackがactiveより良い → 「Directorは方向を示す存在。今の設計は重み計算機でしかない」→ 本来の役割を再定義

Bad例: BollingerRevertのB効果が負 → 重みを0.03に抑圧
Nice例: B効果が負だがfallback時にC-PASS最強クラスタの核 → 単独B効果で判断する設計自体が問題 → 判断基準の再設計

Bad例: 10 Runの結果 → 「C-PASS平均: active=5.14 vs fallback=6.33、net-negative」
Nice例: ゲノム系譜追跡 → fallbackのC-PASS半数はDirector-active期の構造を継承 → 単純比較では因果関係を見誤る

【使命（North Star）— 絶対遵守】
Alpha Factoryの使命は「live_criteria（default.yaml）を全て満たすイントラデイ戦略個体を1つ見つけ出すこと」。
Stage C通過は最低条件。使命達成 = live_criteriaの全指標を同時に満たすC-PASS個体の出現。
達成後は閾値を引き上げて次の水準を設定する。
絶対制約: イントラデイ専用（スイングトレード / オーバーナイト保有は禁止）。日本株市場（東証）、分足データ。

【禁止事項 — 以下の提案・設計・実装は絶対に行わないこと】
1. ショート（空売り）売買の導入
2. A・B・C評価期間を強い根拠なしに延長する
3. 見た目の数値をよくしようとする改善（Sharpe/WR等の数値操作）
4. GAをハックしてステージを進めようとする（フィットネス関数の歪曲等）
5. 閾値をいたずらに緩和してステージを飛ばす（Stage B Sharpe≥0.2を下げる等）
6. やたらに複雑な案を提案する（大規模リファクタリング、新フレームワーク導入等）
7. 取引回数を削減して見かけの成績を上げようとする（entry_threshold過剰引き上げ、max_pos過度縮小等でtcを減らす方向の施策）

【ツール使用制限】
コマンド実行・ファイル書き込みは一切行わず、提供されたテキストの分析に集中すること。ファイル読み込みは許可。

【レビュー重点項目 — 転記漏れパターン】
このプロジェクトでは「値の転記漏れ・伝搬漏れ・記録漏れ」が繰り返し発生している。以下を重点的にチェックすること:
1. 新規パラメータ/カラム追加時: config定義→GAConfig読み込み→genome.meta注入→消費者参照の4段階が全て接続されているか
2. archive記録: GENOMES_SCHEMAにフィールド定義→_create_row_template初期値→collect_stage_*書き込み→flush出力の4点セット
3. 関数パラメータ: 新規パラメータ追加時に全呼び出し元で引数が渡されているか
4. ログ出力: 新規の値伝搬に対応するlogger出力が追加されているか

【監査・レビュー時の必須チェック — False-positive 再発防止】
2026-04-14 の pipeline 徹底監査で約 9 割が false-positive (完全に誤り / right-fact-wrong-interpretation / collider bias / 未検証 claim) だった反省から、以下の discipline を全レビュー・監査で遵守すること。詳細は `devnotes/20260415-0100-pipeline-audit-postmortem/postmortem.md` §5 を参照。

### C1. Design-first 原則 (code grep より先に docs を読む)
コードの bug / 設計欠陥について claim を出す前に、以下を必ず verify せよ:
- `docs/alpha-factory/` 配下の該当セクション (stage-gates.md / alpha-sieve.md 等) を Read で確認
- `devnotes/` 配下の関連 T-number (関数コメントや git log に出てくる T-xxx) を `ls devnotes/ | grep T{xxx}` で探して読む
- `git log --all -S "識別子"` で該当 code の変更履歴を辿る
- 該当機能と並行計算される可能性のある経路を `grep -rn "期待する関数名 / 期待する変数名"` で広く検索
未実施で「バグ」claim を出すことは禁止。 これらは **bug ではなく doc review failure** として扱う。

### C2. 「X が無い = バグ」禁止ルール
関数 Y の signature / body に識別子 X が無いことを根拠に bug 判定してはならない。 以下を verify してから:
- X がシステム内の他の場所 (別関数 / 別モジュール / 別経路) で計算されているか `grep -rn "X"` で広く検索
- 計算結果が Y が参照するデータ構造 (archive / metadata / config) に入っている可能性を確認
- 「X が Y の引数でないのは意図された設計か」を devnotes / design doc で確認
これらを通過しない場合、 「X 未接続」という **observation** は許されるが **「バグ」という verdict は禁止**。

### C3. Collider bias 必須チェック (相関分析時)
2 つの変数 A, B の相関 (Spearman / Pearson / 回帰係数) を計算して report する場合、 以下を必ず明記せよ:
- **Conditioning set**: 相関を計算した集団 (全個体 / B-passers / C-passers / archive entries / ...)
- **Collider の有無**: A の値に依存して conditioning set に入るか出るかが決まる場合、 B との相関は因果的に解釈不能である旨を明示
- **Unconditioned 推定**: 可能なら rejected 群まで含めた集団で相関を再計算 (代理 metric があれば)。 不可能ならその旨を明示
**禁止**: Conditioning set 内の負相関を「anti-predictor」、 ゼロ相関を「predictor ではない」と因果的に解釈すること。 Filter 目的の階層の gate_score は「次段の選抜品質を最大化する」ことが役割であり、 次段 metric の予測器ではない。

### C4. 前提明示ルール
Claim / verdict を出す前に、 prompt の先頭に「本分析の前提」を bullet でリスト化し、 **各前提について verify 済みであることを明示**せよ。 例:
```
## 前提 (全て verified であること)
- [x] `mission_gap_enabled = true` (default.yaml L404 確認済み)
- [x] `stage_a_gate_stage_b_ratio = 0.17` (default.yaml L691 確認済み)
- [x] Production では n_bootstrap=1 (default.yaml L954 確認済み)
```
レビュイー (Codex 側) は「前提のいずれかが事実と異なる」と指摘した場合、 **下流の議論を中止して前提検証に戻る**こと。 Round 1 prompt には必ず「この前提は正しいか」という質問を含めよ。

### C5. 並列 sub-agent の framing 独立性チェック
監査で並列 sub-agent を launch する場合、 以下のいずれかを満たせ:
1. Sub-agent ごとに **異なる出発点** (異なる Explore 出力 / 異なる対象ファイル / 異なる視点) を与える
2. 1 つの sub-agent が他の sub-agent の中間成果物を **否定的に** 読む ("この finding の反証を探せ")
3. 最終 synthesis の前に、 sub-agent 間の framing を手動で cross-check し、 共通の前提・共通の framing を明示化する
**禁止**: N 個の sub-agent に「同じ code map を読んで / 同じ framing で / 同じ議論スタイルで」分析させて independent verification と見なすこと。 それは 1 つの誤読の N 倍冗長実行である。

### C6. Fact / Interpretation 分離ルール
Sub-agent / Codex の report に以下のセクション区切りを使え:
```markdown
## 観察された事実 (Facts)
- F1: [測定値 / 観察内容]、 source: [file:line / parquet path]

## 解釈 / 推論 (Interpretations)
- I1 (from F1, F2): [解釈]
- 根拠: [F1, F2 が I1 を支持する理由]
- 反証可能性: [I1 が false だった場合に観察されるはずの事実]

## 最終判定 (Verdict)
- Confidence: HIGH / MEDIUM / LOW / INCONCLUSIVE
```
**禁止**: Fact と Interpretation を 1 文に mix して「verified な bug」と主張すること (例: 「Stage B 94.9% 素通り (fact) / anti-predictor (interpretation)」を同一 bullet で書かない)。

### C7. Sample size ガード
n < 30 のサンプルで相関 / 統計的 claim を出す場合、 以下を必ず明記:
- Sample size (明示的な数値)
- p-value または bootstrapped CI
- 「この sample size では因果解釈しない」旨
**n < 10 は相関 claim を禁止** (observation のみ許可、 monitoring 用途でのみ使用可)。

### C8. INCONCLUSIVE を第一級 verdict に
Verdict template に `INCONCLUSIVE (データ不足 / 検証手段なし)` を CONFIRMED / REJECTED と同格の選択肢として明示。 **INCONCLUSIVE は正当な結論**であり、 agent の義務遂行度に影響しない。 「何か verdict を出さないと仕事をしていない」という implicit pressure で CONFIRMED に寄せることを禁止。

### C9. Falsification-first プロンプト
Sub-agent prompt の Round 1 は「この hypothesis の反証を探せ」という指示を先に書く。 Codex に対しても「hypothesis を支持する証拠」と「hypothesis を否定する証拠」の両方を求める。 Round 2 以降は両者の重みづけを議論する。
**禁止**: 「この hypothesis の正しさを論証せよ」という framing を Round 1 で使うこと。 それは confirmation bias を強制する。
```

---

## プロンプト構成ルール

1. **プロンプトはファイルに書き出し、stdin経由で渡す**（シェル引数では渡さない）
2. Write ツールでプロンプトファイルを作成 → stdin リダイレクトで `codex-vscode exec` に渡す
3. プロンプトの構成順序:

```
{使命・禁止事項・ツール使用制限}  ← 本スキルの正規定義をそのまま挿入
{system部: 役割・タスク固有の指示}  ← 呼び出し元スキルが定義
---
{user部: データ・質問}              ← 呼び出し元スキルが定義
```

4. プロンプトファイルの配置先: `{tmp_dir}/.codex-prompt-{label}.md`
   - `label` は呼び出し元が指定する識別子（例: `analysis`, `consensus`, `design-review`, `impl-review`）

---

## One-shotモード

セッションを保持しない単発呼び出し。独立分析、テーマ別議論など合議ループを伴わない用途で使用。

**コマンドテンプレート**:
```bash
codex-vscode exec --ephemeral --sandbox read-only -m {model} \
  -c 'model_reasoning_effort="{reasoning}"' \
  -o {出力ファイル} - < {tmp_dir}/.codex-prompt-{label}.md
```

**必須オプション**:
- `--ephemeral`: セッションファイルを永続化しない
- `--sandbox read-only`: コマンド実行・ファイル書き込みを禁止（読み込みは許可）
- `-m {model}`: モデルを指定（`gpt-5.3-codex` / `gpt-5.4` 等）
- `-c 'model_reasoning_effort="{reasoning}"'`: reasoning effortを指定（モデル互換性のため常に明示指定。詳細は `zenigame-codex-vscode` 参照）
- `-o {出力ファイル}`: 結果をファイルに保存

---

## セッションモード（合議ループ用）

複数ラウンドの合議でCodexが前回の指摘を記憶した状態で再レビューできるモード。

### Round 1: セッション作成

```bash
codex-vscode exec --sandbox read-only -m {model} \
  -c 'model_reasoning_effort="{reasoning}"' --json \
  -o {出力ファイル}-round-1.md \
  - < {tmp_dir}/.codex-prompt-{label}.md \
  > {tmp_dir}/.codex-session-{label}.jsonl

SESSION_ID=$(head -1 {tmp_dir}/.codex-session-{label}.jsonl \
  | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['thread_id'])")
```

- `--ephemeral` を付けない（セッションを永続化）
- `--json` でJSONLイベントをstdoutに出力 → ファイルに保存
- 1行目の `thread.started` イベントから `thread_id` を抽出

### Round N (N≥2): セッション再開

```bash
codex-vscode exec resume "$SESSION_ID" --json \
  -o {出力ファイル}-round-{N}.md \
  - < {tmp_dir}/.codex-prompt-{label}-round-{N}.md \
  >> {tmp_dir}/.codex-session-{label}.jsonl
```

- `exec resume {SESSION_ID}` で前回セッションを再開（文脈維持）
- Round Nのプロンプトには対応マトリクス・修正内容のみ記載（使命・禁止事項の再挿入は不要）
- JSONLは追記（`>>`）

### session_label の命名規則

並列実行時の衝突を避けるため、呼び出し元が一意な `label` を指定する:
- `consensus` — 改善策合議（plan-and-design B-2/B-3）
- `design-review` — 詳細設計レビュー（plan-and-design C-2/C-3、alpha-design 2-3/2-4）
- `conceptual-review` — 概念設計レビュー（alpha-design 1-3/1-4）
- `impl-review` — 実装レビュー（implement A-2/A-3）

---

## エラーハンドリング

### 共通（全モード）
- `codex-vscode exec` / `codex-vscode exec resume` が非ゼロ終了コードを返した場合、30秒待って1回リトライ
- 2回連続失敗時の挙動は呼び出し元スキルの規定に従う

### セッションモード固有
- **Round 1 で失敗**: リトライ時も新規セッションを作成（SESSION_IDは更新される）
- **Round N (N≥2) で失敗**: 同じ SESSION_ID でリトライする
- **SESSION_ID 取得失敗**（JSONLパースエラー等）: one-shotモードにフォールバック（`--ephemeral` で再実行）
