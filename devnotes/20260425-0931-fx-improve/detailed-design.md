# 詳細設計: Run 10 施策

## 使命・制約（絶対遵守）

zenigame-fx-codex-review SKILL.md の使命・禁止事項・C1-C9 を継承。

**FX 固有の絶対制約**: イントラデイ前提 / ロング・ショート両方向許容 / スワップ・スプレッドを fitness に反映。

## 施策一覧

| # | 施策名 | 変更ファイル | target_metric |
|---|--------|------------|--------------|
| 1 | 無取引ペナルティの構造的導入 | `src/alpha_factory/` 内 fitness/penalty 計算（要詳細特定） | trade_count=0 比率 |
| 2 | PnL 集計経路の数値整合性監査ログ | `src/alpha_factory/` PnL 集計箇所 | total_pnl 整合性 |

---

## C1: 無取引ペナルティの構造的導入

### target_metric / failure_mode / causal_path / falsification / success_criterion

improvement-plan.md §確定施策一覧 C1 を継承。

### 変更箇所

**Open question**: 現行コードベースの fitness/penalty 計算パスを Read で特定する必要がある。本 cycle の plan-and-design 範囲では具体的な「変更ファイル + 行番号 + Before/After」確定までは行わない。

理由: 「概念設計・詳細設計の新規作成は zenigame-fx-alpha-design の責務」（plan-and-design SKILL.md §責務境界）。
本施策は新規構造変更であり、`zenigame-fx-alpha-design` で概念設計を立てた上で `zenigame-fx-todo-add` 経由で TODO 化し、次サイクルの Phase 3（implement）で実装することが正規ルート。

### 波及変更

- 概念設計: `docs/alpha_factory/concepts/` に新規（alpha-design 経由）
- TODO 登録: `docs/alpha_factory/TODO.md` に Open 行追加（todo-add 経由）
- AGENTS.md: 評価関数の挙動説明箇所を更新
- skill: improve-cycle SKILL.md の使命/禁止事項に矛盾なし

### テスト計画

- [ ] バグ再現テスト: trade_count=0 個体が fitness_pen=0 で上位選抜される現象を再現する unit test
- [ ] 構造修正後の挙動テスト: 同条件で trade_count=0 が選抜順位下位に落ちることを検証
- [ ] 既存テストの回帰: 取引する個体の評価が壊れないことを確認

### リスク

- 過剰なペナルティで実取引個体まで弾く（trade_count_min との整合）
- 評価関数の連続性が壊れて GA 探索が不安定化

### Run 10 への組み込み

**未組込**（本 cycle 内では実装しない）。本 cycle は cycle 1 = 計画策定 only。次サイクルで TODO 経由で実装。

---

## C2: PnL 集計経路の数値整合性監査ログ

### target_metric / failure_mode / causal_path / falsification / success_criterion

improvement-plan.md §確定施策一覧 C2 を継承。

### 変更箇所

**Open question**: 同様に PnL 集計コードパスを特定する必要があり、新規追加（監査ログ）も alpha-design + todo-add の正規ルートを通すべき。

### Run 10 への組み込み

**未組込**（同上）。

---

## Run 10 実行パラメータ

| パラメータ | 値 | R9 からの変更 |
|-----------|-----|--------------|
| population_size | 96 | +76 (20→96) |
| generations | 60 | +55 (5→60) |
| dataset.start | 2026-03-01T00:00:00Z (driver default) | 同左 |
| dataset.end | 2026-03-15T00:00:00Z | 同左 |
| 他 GA パラメータ | config/alpha_factory/default.yaml の既定値 | 変更なし |

> 注: 本 cycle は **コード変更なしの観察 RUN** に相当する（improvement-plan の施策はいずれも次サイクル以降で実装）。
> Run 10 結果は cycle 2 の analyze-run の入力となり、そこで施策1/2 を実装するための TODO が登録されているはず（並行起動中の post-run-review BG agent と本 cycle の deferred 推薦の合わせ）。

---

## 保留事項

- 施策 1, 2 の concept-design + TODO 登録（cycle 2 に持ち越し）
- post-run-review BG agent (5 theme) 完了通知の取り込み（cycle 2 の TODO リストに反映されている見込み）
- **BG要約反映ゲート** (Codex Critical): cycle 2 の plan-and-design 開始前に `.cache/alpha_factory/post-run-review-summary-run_20260425_002330.md` を Read して各テーマ 1 行要約を取り込み、優先度ゲートを 1 回実施する
- **無取引率再現性検証** (Codex Suggestion): Run 10 で trade_count=0 比率が ≥80% で再現されれば構造問題継続と判定（反証可能仮説）
- **PnL 経路差分監査** (Codex Suggestion): cycle 2 の concept-design で PnL 集計経路の入出力差分テストを必須化

## 設計レビュー結果

- Round 1: CHANGES_REQUESTED → 上記保留事項に反映
- Critical（BG 待機なし実行）はそのまま受容: post-run-review は SKILL 設計上 fire-and-forget であり、cycle 2 の入口で取り込む規約 → 致命的ではない
- 設計レビューは保留事項追加で収束（Round 2 不要）
