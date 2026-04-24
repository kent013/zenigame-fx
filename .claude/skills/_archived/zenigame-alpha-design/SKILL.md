---
name: zenigame-alpha-design
description: Alpha Factory改善の設計フロー（概念設計→Codexレビュー→詳細設計→Codexレビュー）。設計ファイル生成のみ、TODO登録は行わない
argument-hint: "<topic> [conceptual_design_path]"
---

# Alpha Factory 設計フロー

改善アイデアの議論が終わった後、**概念設計 → Codex合議 → 詳細設計 → Codex合議** の順で設計を完成させ、TODOへの登録を案内する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `topic` ($1) | Yes | 設計トピック（ディレクトリ名に使用。例: bind-params-optimization, composite-precompute） |
| `conceptual_design_path` ($2) | No | 既存の概念設計ファイルのパス（リポジトリルートからの相対パス）。省略時は会話内容から概念設計を作成する |

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

**スイングトレード（オーバーナイト保有）は絶対に行わない。**

## 禁止事項（全フェーズで厳守）

| # | 禁止事項 |
|---|---------|
| 1 | ショート（空売り）売買の導入 |
| 2 | A・B・C評価期間を強い根拠なしに延長する |
| 3 | 見た目の数値をよくしようとする改善（数値操作） |
| 4 | GAをハックしてステージを進めようとする |
| 5 | 閾値をいたずらに緩和してステージを飛ばす |
| 6 | やたらに複雑な案を提案する |

---

## 重要原則

- **全ての成果物は `devnotes/{YYYYMMDD-HHMM-topic}/` に保存**する
- **Codexとの合議は「全CriticalとWarningが解消されるまで」繰り返す**（最大5ラウンド）
- 概念設計レビューは **`gpt-5.4`**、詳細設計レビューは **`gpt-5.3-codex`** を使用

---

## Phase 1: 概念設計

### 1-1. 作業ディレクトリの作成

今日の日時と `topic` からディレクトリ名を決定する:
```bash
date +%Y%m%d-%H%M
```

以降の全ファイルを以下に保存:
```
devnotes/{YYYYMMDD-HHMM}-{topic}/
```

### 1-2. 概念設計ファイルの準備

**`conceptual_design_path` が指定された場合**:
- `Read` ツールでそのファイルを読み込む
- 内容を `devnotes/{dir}/conceptual-design.md` にコピーして保存する

**`conceptual_design_path` が省略された場合**:
- 会話内容（ユーザーが説明した改善アイデア）をもとに概念設計を作成する
- 以下のフォーマットで `devnotes/{dir}/conceptual-design.md` を作成する:

```markdown
# 概念設計: {topic}

## 背景・課題
[なぜこの改善が必要か]

## 改善アイデア
[何をどう変えるか、改善の方向性]

## 期待効果
- [Alpha Factoryの使命（Net+・取引回数多・高成績）への貢献]
- [具体的な改善見込み]

## 実装方針（概要）
[どのコンポーネントを、どう変えるか。コード変更の概要]

## 制約・前提
[既存アーキテクチャとの整合性、依存関係、制約]

## スコープ外
[今回扱わないこと]
```

### 1-3. Codexによる概念設計レビュー

`zenigame-codex-review` スキルの**セッションモード**に従い、プロンプトファイルを作成してCodexに概念設計のレビューを依頼する（レビューループのため文脈維持）。

**model**: `gpt-5.4`
**reasoning**: `medium`
**label**: `conceptual-review`

使命・禁止事項は zenigame-codex-review により自動挿入。system部には役割・タスク固有の指示のみ記載。

**system**:
```
あなたはクオンツトレーディングシステム「Alpha Factory」の改善に関する概念設計レビュアーです。

（使命・禁止事項 + 監査・レビュー必須チェック C1-C9 は zenigame-codex-review スキルにより自動挿入済み）

【レビュー観点】
1. 使命との整合性: この改善は Net+ 戦略の生成に本質的に貢献するか
2. 禁止事項違反: 上記禁止事項に抵触していないか
3. 実現可能性: 技術的・制度的に実現可能か
4. 期待効果の妥当性: 主張している効果は合理的に期待できるか
   - 効果の根拠となる相関・予測を主張している場合、 C3 (collider bias チェック) / C7 (sample size ガード) を適用すること
5. リスク: 重大な副作用・後退の可能性はないか
6. スコープの適切さ: 過大または過小になっていないか
7. **メモリ制約**: 実行環境は24GBマシン×6ワーカー（1ワーカーあたり最大約3GB）。キャッシュ・データ構造の追加がこの制約内に収まるか。無制限に成長するdict/list等はOOMリスクがあるため [Critical]
8. **前提検証 (C4)**: 概念設計の「仮説」に含まれる前提条件 (config 値 / design 文書記述 / 既存実装の状態) が最新コード・設定と一致しているか。 前提のいずれかが事実と異なる場合は [Critical] として指摘し、 下流議論を中止させること
9. **Design-first 原則 (C1)**: 提案されている変更の対象コードに関して、 関連する docs/alpha-factory/ / devnotes/ / git log の履歴が概念設計の「背景・課題」で参照されているか。 未参照なら [Warning] 以上

【出力形式】
- 全体判定: APPROVED / CHANGES_REQUESTED / INCONCLUSIVE (前提・データ不足で判断不能)
- 各観点ごとに [Critical] [Warning] [Suggestion] で分類して指摘
- Critical/Warning には修正提案を必ず添える
- 日本語で出力

【Fact / Interpretation 分離 (C6)】
レビュー指摘を書く際は「観察された事実」と「そこから導いた解釈」を明確に区別すること。 「Xが Y だから Z というバグ」のように事実と解釈を 1 文に mix しない。
```

**user**: `## 概念設計\n{conceptual-design.mdの内容}`

レビュー結果を保存:
```
devnotes/{dir}/conceptual-review-round-1.md
```

### 1-4. 概念設計レビュー合議ループ

Codexのレビューを精査し:

**セッション再開**: `zenigame-codex-review` スキルのセッションモード（Round N）に従い、同じ SESSION_ID で `codex-vscode exec resume` を実行する。Round 2以降のプロンプトには対応マトリクス・修正内容のみ記載（使命・禁止事項の再挿入は不要）。

1. **[Critical]** の指摘は**必ず対応**（概念設計を修正 or 根拠を添えて反論）
2. **[Warning]** の指摘は**対応を検討**
3. **[Suggestion]** は任意
4. **全体判定が APPROVED になるまで**繰り返す（最大5ラウンド）

対応内容を対応マトリクスとして記録し、概念設計を `Edit` で修正する。

各ラウンドの結果:
```
devnotes/{dir}/conceptual-review-round-{N}.md
```

### 1-5. ユーザー報告

```
## Phase 1 完了: 概念設計 APPROVED (Round {N})

### 概念設計サマリー
- 改善内容: [1-2行で]
- 期待効果: [箇条書き]
- スコープ: [変更コンポーネント]

→ Phase 2に進みます（詳細設計 & Codexレビュー）
```

---

## Phase 2: 詳細設計

### 2-1. 関連コードの読み込み

概念設計で示した変更対象ファイルを `Read` ツールで読み込み、現行コードを把握する。

### 2-2. 詳細設計書の作成

概念設計と現行コードをもとに、詳細設計書を作成する。

> **⚠ 波及変更チェック（必須）**: インターフェース変更（Alpha Factoryの引数追加・削除・変更、CLIオプション、公開APIのシグネチャ変更など）が発生する場合、その影響が及ぶ以下のファイルも**変更対象として施策に明示**すること。
> - `AGENTS.md` — 運用手順・コマンド例・パラメータ説明など
> - `.claude/skills/zenigame-*/skill.md` — スキルの引数定義・フロー・プロンプト内のコード例
> - その他、変更されたインターフェースを参照するドキュメント・設定ファイル

**詳細設計書には必ず以下のセクションを含める**:

```markdown
# 詳細設計: {topic}

## 使命・制約（絶対遵守）

### Alpha Factory 使命（North Star）
「イントラデイでNet+の戦略を生み出すこと。Net PnLが正、取引回数が多い、飛び抜けて成績が高い。」
- スイングトレード（オーバーナイト保有）は絶対に行わない

### 禁止事項
1. ショート（空売り）売買の導入
2. A・B・C評価期間を強い根拠なしに延長する
3. 見た目の数値をよくしようとする改善（数値操作）
4. GAをハックしてステージを進めようとする
5. 閾値をいたずらに緩和してステージを飛ばす
6. やたらに複雑な案を提案する

### コーディングルール
- **バグ修正はテストファースト**: エラーを再現する最小テストを先に書き、FAILを確認してからコードを修正
- **全施策にテスト必須**: テストのない施策は実装完了とみなさない
- **テスト命名**: 振る舞いを説明する汎用的な名前（Run名・日付・セッション固有の識別子はNG）
- **テスト配置**: 対象モジュールに対応するテストファイルに追加（例: `src/.../foo.py` → `tests/.../test_foo.py`）
- **uv必須**: `uv run pytest tests/alpha_factory/`
- Python 3.13 + numpy + pandas + multiprocessing 環境

## 概念設計リファレンス

[docs/alpha-factory/TODO.md (or devnotes/{dir}/conceptual-design.md) へのリンク]

## 施策一覧

| # | 施策名 | 変更ファイル | 優先度 |
|---|--------|------------|--------|

## {施策名}

### 変更箇所
- ファイル: `src/trading/alpha_factory/.../xxx.py` (L100-120)

### 波及変更（AGENTS.md・スキルファイル）
<!-- Alpha Factoryのインターフェース（引数・CLIオプション・公開API）を変更する場合、影響するファイルを全て列挙する -->
<!-- 影響がない場合は「なし」と明記する -->
- `AGENTS.md`: [変更が必要な箇所と内容、または「なし」]
- `.claude/skills/zenigame-{skill-name}/skill.md`: [変更が必要な箇所と内容、または「なし」]

### 現行コード
```python
# 現在の実装
```

### 変更後コード
```python
# 変更後の実装
```

### ルックアヘッドバイアスチェック（プリミティブ変更時は必須）
<!-- primitives.py を変更・追加する場合、以下の7項目を全てチェックすること -->
<!-- プリミティブに関係ない施策の場合は「対象外（プリミティブ変更なし）」と記載 -->
- [ ] 未来バー参照なし（`data[current_idx+1:]` 等を使用していない）
- [ ] 当日確定値の先取りなし（`high.max()` 等で全日の値を使用していない）
- [ ] rolling window方向が過去方向（`[i-n+1:i+1]`）
- [ ] 正規化にローカルwindow or rolling関数を使用（全期間 `data.mean()` 等を使用していない）
- [ ] バケット/グループ平均が因果的（当該バーまでの累積平均のみ）
- [ ] cumsum/accumulate が因果的方向
- [ ] talib関数のカスタムラッパーで未来参照を導入していない

### パフォーマンスチェック（プリミティブ変更時は必須）
<!-- primitives.py を変更・追加する場合、以下の4項目を全てチェックすること -->
<!-- プリミティブに関係ない施策の場合は「対象外（プリミティブ変更なし）」と記載 -->
- [ ] `compute_all_bars()` が実装されている（未実装だとcompute()×N回フォールバックでO(N²)）
- [ ] 内側ループ内でNumPy関数を呼んでいない（prefix-sum差分等で置換）
- [ ] `bars.bars` イテレーションではなくSoAプロパティ（`close_array`等）を使用
- [ ] 同一配列（logret, prefix-sum等）を`_get_or_compute_indicator()`でキャッシュ

### テスト計画
- [ ] バグ修正の場合: 再現テストを先に書く
- [ ] 既存テスト `tests/alpha_factory/test_xxx.py` の更新
- [ ] 新規テスト: {テスト名} — {検証内容}

### リスク
- {副作用・後退の可能性}

## 実装モード

| 項目 | 内容 |
|------|------|
| 推奨モード | incremental / standalone |
| 判断根拠 | [なぜそのモードか] |
| 競合リスク | [他施策との干渉可能性] |
| 想定実装時間 | [短/中/長] |
```

保存先:
```
devnotes/{dir}/detailed-design.md
```

### 2-3. Codexによる詳細設計レビュー

`zenigame-codex-review` スキルの**セッションモード**に従い、プロンプトファイルを作成してCodexにレビューを依頼する（レビューループのため文脈維持）。

**model**: `gpt-5.3-codex`
**reasoning**: `high`
**label**: `design-review`

使命・禁止事項は zenigame-codex-review により自動挿入。system部には役割・タスク固有の指示のみ記載。

**system**:
```
あなたは経験豊富なクオンツ・システムアーキテクトです。Alpha Factory改善の詳細設計をレビューしてください。

（使命・禁止事項 + 監査・レビュー必須チェック C1-C9 は zenigame-codex-review スキルにより自動挿入済み。 特に C1 Design-first / C2 parallel-path 検索 / C3 collider bias / C4 前提検証 / C6 fact-interpretation 分離 / C8 INCONCLUSIVE 第一級扱い を厳守すること）

【前提環境】
- Python 3.13 + numpy + pandas + multiprocessing
- NSGA-II遺伝的アルゴリズムによるイントラデイ戦略最適化
- DSLベースの戦略表現: ProhibitionMask（ハード制約） + Clauseベース合成（directional + local_gate） × Risk。詳細は docs/alpha-factory/clause-architecture.md
- 実行環境: macOS, **24GBメモリ**, 6ワーカー並列（**1ワーカーあたり最大約3GB**）

【レビュー観点】
1. コードの正確性（ロジックエラー、エッジケース、off-by-one、NaN伝播）
2. 既存コードとの整合性（命名規約、パターン、API）
3. パフォーマンスへの影響
4. テスト計画の網羅性（各施策にテストが含まれているか必ず確認。バグ修正ならテストファーストか）
5. 副作用・後退リスク
6. 考慮漏れ
7. 実装モードの妥当性（incremental/standaloneの判断が適切か）
8. 波及変更の網羅性（Alpha Factoryのインターフェース変更・引数変更・CLIオプション変更がある場合、AGENTS.mdおよび`.claude/skills/`配下のスキルファイルが変更対象に含まれているか。含まれていない場合は [Critical] として指摘）
9. **ルックアヘッドバイアス**（プリミティブ変更がある場合は必須）: compute()/compute_all_bars()/_compute_full()の全パスで未来バー参照・当日確定値先取り・全期間統計量使用・バケット確定平均使用がないか。違反がある場合は [Critical]。Run 79でTNVルックアヘッドにより成績90%消失した教訓から最重要チェック
10. **メモリ制約**: 実行環境は24GBマシン×6ワーカー（1ワーカーあたり最大約3GB）。キャッシュ・バッファ・データ構造の追加や拡大がこの制約内に収まるか。無制限に成長するdict/list/setはOOMリスクがあるため [Critical]。Run 142で`_scores_cache`（無制限dict）によりOOM発生した教訓から必須チェック
11. **パフォーマンス**（プリミティブ変更がある場合は必須）: (a) `compute_all_bars()`が実装されているか（未実装だとcompute()×N回フォールバックでO(N²)） (b) 内側ループ内でNumPy関数を呼んでいないか（prefix-sum差分等で置換すべき） (c) `bars.bars`イテレーションではなくSoAプロパティ（close_array等）を使用しているか (d) 同一配列を`_get_or_compute_indicator()`でキャッシュしているか。違反がある場合は [Warning]。Run 149でPostJumpReversionAlpha 85.1s・IATF 40.6sのボトルネック発覚の教訓から必須チェック
12. **前提検証 (C4)**: 設計書の「背景・課題」「観察事実」セクションで参照されている config 値 / code snippet / parquet 集計が、 最新 main と一致しているか。 不一致があれば [Critical]
13. **並行計算経路の確認 (C2)**: 設計書が「関数 Y に引数 X が無いのでバグ」と主張している場合、 X が他の場所で計算されていないかを `grep -rn` 級の広さで検索した痕跡が設計書にあるか。 無ければ [Critical] (主張を撤回するか、 verify の痕跡を追加)
14. **相関・予測 claim の collider bias 検証 (C3 / C7)**: 設計書が Spearman / Pearson / 予測相関を根拠に効果を主張している場合、 conditioning set が明示されており、 かつ collider bias の可能性が検討されているか。 n < 30 のサンプル claim は C7 に従って明示的に「因果解釈しない」旨を書いているか

【出力形式】
- 各施策ごとに判定: APPROVE / REQUEST_CHANGES / INCONCLUSIVE (C8)
- 指摘は [Critical] [Warning] [Suggestion] で分類
- Critical/Warning には必ず修正案を添える
- 全体判定: APPROVED / CHANGES_REQUESTED / INCONCLUSIVE
- 日本語で出力

【Fact / Interpretation 分離 (C6)】
レビュー指摘を書く際は「観察された事実」と「そこから導いた解釈」を明確に区別せよ。 「Xが Y だから Z というバグ」のように事実と解釈を 1 文に mix しない。
```

**user**: `## 詳細設計書\n{detailed-design.mdの内容}\n\n## 関連する現行コード\n{変更対象ファイルの抜粋}`

レビュー結果を保存:
```
devnotes/{dir}/detailed-review-round-1.md
```

### 2-4. 詳細設計レビュー合議ループ

Codexのレビューを精査し:

**セッション再開**: `zenigame-codex-review` スキルのセッションモード（Round N）に従い、同じ SESSION_ID で `codex-vscode exec resume` を実行する。Round 2以降のプロンプトには対応マトリクス・修正内容のみ記載（使命・禁止事項の再挿入は不要）。

1. **[Critical]** は**必ず対応**（設計修正 or 根拠ある反論）
2. **[Warning]** は**対応を検討**
3. **全体判定が APPROVED になるまで**繰り返す（最大5ラウンド）

修正した設計書は `Edit` で更新し、再度Codexにレビュー依頼。

各ラウンドの結果:
```
devnotes/{dir}/detailed-review-round-{N}.md
```

最終確定版:
```
devnotes/{dir}/detailed-design.md  (上書き更新)
```

### 2-5. 最終確認

詳細設計が APPROVED になったら、**使命・禁止事項チェック**を実施:
- 全施策が使命（Net+・取引回数多・高成績）に寄与するか
- 禁止事項に違反していないか
- コーディングルール（テストファースト、テスト必須）が設計に反映されているか

違反があれば修正してから完了とする。

---

## Phase 3: 完了報告 & TODO登録案内

### 3-1. 最終報告

以下の内容をユーザーに報告する:

```
## 設計フロー完了

### 成果物
- 概念設計: devnotes/{dir}/conceptual-design.md
- 詳細設計: devnotes/{dir}/detailed-design.md （APPROVED）

### サマリー
- 改善内容: [1-2行]
- 変更ファイル: [一覧]
- 推奨実装モード: {incremental / standalone}（理由: [判断根拠]）
```

### 3-2. TODO登録の案内

詳細設計書の内容から以下を推定し、TODO登録コマンドを案内する:
- `{theme}`: `speed` / `live-trading` / `performance` / `japan-market` / `signal-predictive-power` / `general` から最適なもの
- `{summary}`: 30文字以内の実装概要
- `{priority}`: 詳細設計書の「実装モード」セクションから
- `{mode}`: incremental / standalone

```
### TODO登録

以下のコマンドでTODOリストに登録してください:

/zenigame-todo-add "{topic}" {theme} "{summary}" devnotes/{dir} {priority} {mode}
```

**注意**: このスキルはTODO.mdを直接変更しない。TODO登録は `/zenigame-todo-add` スキルの責務。

呼び出し元（`/zenigame-post-run-review` 等）が自動でTODO登録を行う場合は、呼び出し元が `/zenigame-todo-add` を呼ぶ。

---

## エラーハンドリング

### Codex APIエラー
- 30秒待って1回リトライ
- 2回連続失敗の場合、ユーザーに報告してCodexなしで続行するか確認

### 既存コードの読み込みエラー
- 対象ファイルが見つからない場合、ユーザーに正しいパスを確認する

---

## 使用例

### 例1: 議論後に概念設計を新規作成
```
User: /zenigame-alpha-design bind-params-optimization
→ 会話内容から概念設計を作成してレビュー → 詳細設計まで完成させる
```

### 例2: 既存の概念設計から詳細設計へ
```
User: /zenigame-alpha-design bind-params-optimization devnotes/20260221-0100-bind-params/conceptual-design.md
→ 既存の概念設計を読み込んでレビュー → 詳細設計まで完成させる
```
