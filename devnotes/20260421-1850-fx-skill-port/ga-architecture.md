# FX GA アーキテクチャ設計判断

**作成日時**: 2026-04-21 19:00 (JST)
**最終更新**: 2026-04-21 19:20 (JST) — clause と GA スコープが直交する 2 軸であることを明確化
**文脈**: zenigame-* → zenigame-fx-* skill 移植の前提として、GA のアーキテクチャを決定する必要がある。
**未決議題**: 本ドキュメントは未確定。ユーザーの最終判断を反映してから Phase 0 に進む。

---

## 重要な訂正: 2 つの直交する軸

前版で `C = Portfolio GA` を「clause の話」と混同しかけたので訂正。GA アーキテクチャには **直交する 2 軸** がある:

### 軸 1 — ゲノム内部構造（1 ゲノムが 1 本のバーから composite score をどう作るか）

| 選択肢 | 内容 | 採用例 |
|--------|------|--------|
| **(a) フラット式** | `entry_long`, `entry_short`, `exit_long`, `exit_short` の 4 つの Expr ツリー | 現 FX（`src/dsl/genome.py`） |
| **(b) Clause ベース合成** | 1-3 個の Clause（`directional` × `local_gate` × `weight`）の加重合成 → entry_threshold 超で発注。`composite = Σ(clause_weight × clause_score) / Σ\|clause_weight\|` | zenigame（T177 で clause-only-migration 完了） |

zenigame の Clause 構造（参考: `docs/alpha-factory.md` Layer 1）:
```
Clause[k]:
  dir_score[k] = Σ(w_i × signal_i) / Σ|w_i|     # 方向性シグナル加重和（TREND_FOLLOW/MEAN_REVERT/NEUTRAL）
  gate[k]      = Π gate_fn(gate_signal_j)        # local_gate プリミティブの積（MODULATOR）
  clause_score[k] = dir_score[k] × gate[k]

Final composite = Σ(clause_weight × clause_score) / Σ|clause_weight|
```

### 軸 2 — GA スコープ（1 ゲノムを何銘柄に適用するか）

| 選択肢 | 内容 | 1 GA Run の生成物 |
|--------|------|------------------|
| **(i) 銘柄特化 GA** | 1 GA = 1 銘柄。1 ゲノムは特定銘柄に最適化 | 銘柄ごとの Champion ゲノム |
| **(ii) Universal alpha + 集約** | 1 ゲノムを N 銘柄に適用、fitness 集約（mean / min / portfolio sharpe） | 全銘柄に適用可能な汎用ゲノム |
| **(iii) Portfolio strategy** | 1 ゲノムが N 銘柄のポジションを同時管理（明示的なポジション配分） | ポートフォリオ運用ゲノム |

### zenigame の組み合わせ

**(b) Clause ベース構造 × (ii) Universal alpha + cross-sectional 集約**

- 1 ゲノム = 1 銘柄の OHLC から composite score を出力する signal generator（per-instrument な関数）
- 同じゲノムを 4000 銘柄に適用 → composite score でランク付け → Top-K 保有
- Stage A/B/C は universe × OOS 期間の評価
- ロングオンリー（max_pos = 5 など）

つまり **「ゲノム自体は per-instrument な関数。ユニバース運用は外側の cross-sectional 集約」**。前版で私が「zenigame は Portfolio GA」と書いたのは誤り。zenigame の "portfolio" は外側にあり、ゲノム自体はポジション配分を担わない。

### FX 現状の組み合わせ

**(a) フラット式 × (i) 銘柄特化 GA**

- `src/dsl/genome.py` の `Genome` は 4 個の Expr のみ。clause 構造なし。
- `src/ga/runner.py` は 1 銘柄分のバーで 1 ゲノムを評価。
- DSL は banker-agnostic（変数は `close`, `rsi` 等）だが、GA 自体は単一銘柄に閉じている。

---

## ユーザーの問いへの回答

> Cって株式の時のclauseの話とは違うの？

**違います。** 軸 1（clause 構造）と軸 2（GA スコープ）は完全に直交します。

- 私が前版で書いた **C = Portfolio GA** は **軸 2-(iii)**。「ゲノムが複数銘柄のポジションを同時管理する」話。
- zenigame の **Clause** は **軸 1-(b)**。「1 ゲノムの内部で、複数のシグナルを clause 単位で合成する」話。

zenigame は **(b) clause × (ii) universal cross-sectional** の組み合わせを採用しているだけで、C（Portfolio GA）ではない。FX で zenigame を踏襲したいなら **clause 構造を移植** + **GA スコープをどうするか別途判断** という 2 ステップ。

---

## 軸 1（内部構造）の選択

### Option 1-(a): フラット式を維持

- 現 FX の構造を維持。entry/exit の Expr ツリー 4 個。
- メリット: 改修不要、シンプル。
- デメリット: zenigame の知見（clause 構造、local_gate、合成スコア、entry_threshold）を活かせない。Codex 合議で zenigame の analyze-genome-archive 等を使うとき、語彙が合わない。

### Option 1-(b): Clause 構造へ移行

- `Genome` を `WhenConfig`（凍結 ProhibitionMask + 条件選好）+ `HowConfig`（1-3 clauses + position + risk）に再構築。
- `src/dsl/`, `src/ga/`, `src/backtest/` の改修が必要。
- メリット: zenigame の Alpha Factory 設計思想を継承できる。analyze-genome-archive / plan-and-design / strategic-codex-debate などの skill が概念的にそのまま使える。
- デメリット: backtest engine の signal/score 計算経路に大きな手を入れる。FX 用の primitive（TrendMA, MeanRevertRSI 等）を別途定義必要。

### 推奨

**Option 1-(b) Clause 構造へ移行**。

- 理由: zenigame の skill 群を「内容を変更して完全に移植」する方針なので、ゲノム表現を合わせないと skill の概念がずれる。
- 移植スコープ: zenigame の primitives は equity 用なので FX 用に primitive 一覧を再設計（後述）。clause 合成ロジック自体は流用可能。
- タイミング: Phase 2 の FX 基盤構築でこれを実装する。

---

## 軸 2（GA スコープ）の選択

### Option 2-(i): 銘柄特化 GA（per-instrument）

- 1 サイクル = 1 銘柄の GA。improve-cycle が `--instrument EUR_JPY` を取る。
- 各 Run 1 銘柄、archive に `instrument` カラム、Sieve は同銘柄 OOS。
- 6 銘柄カバーは batch-ga で順次。

### Option 2-(ii): Universal alpha + 集約

- 1 ゲノムを 6 銘柄すべてで backtest、fitness 集約（mean / min / weighted）。
- 計算コスト: 1 ゲノムあたり 6 倍の backtest。
- 集約方法の選択肢:
  - mean sharpe — 平均的に良い
  - min sharpe — 最悪ケース下限保証（robust）
  - portfolio sharpe — equity curve 合算後の sharpe（実運用に近い）
  - weighted mean — 流動性 / ボラティリティで重み付け
- 銘柄ごとの fitness を archive に保持し、Stage B/C で「全銘柄通過」を要求すると過酷だが robust。

### Option 2-(iii): Portfolio strategy

- 1 ゲノムが 6 銘柄のポジションを同時管理（margin, correlation 制約）。
- backtest engine 大改修必要（MockBroker は単一 instrument 想定）。
- 開発コスト数日〜週、現フェーズでは時期尚早。

### 推奨

**Option 2-(i) 銘柄特化 GA + 将来 (ii) へ拡張可能な archive 設計**。

- 理由 1: 現 backtest engine が単一 instrument 設計なので (i) が即座に動く。
- 理由 2: FX は銘柄ごとに性質が極端に違う（USD_ZAR vs EUR_USD）。Universal alpha は機会損失大。
- 理由 3: archive に `instrument` カラムを最初から入れておけば、後で (ii) に拡張するときも横断クエリ可能。
- 理由 4: improve-cycle は `--instruments EUR_JPY,USD_JPY` で複数銘柄を順次回すモードを batch-ga 経由で提供すれば (ii) に近い運用が可能。
- (iii) は将来テーマ。Stage E として位置付け。

### zenigame との差分

| | zenigame | 推奨 FX |
|---|----------|---------|
| 軸 1 内部構造 | (b) Clause | (b) Clause（移植） |
| 軸 2 スコープ | (ii) Universal cross-sectional | (i) 銘柄特化 + 将来 (ii) |

つまり **「ゲノム表現は zenigame に合わせ、運用単位は銘柄ごとに分ける」** というハイブリッド。

---

## FX 用 Primitive 一覧（軸 1-(b) Clause 採用時の前提）

zenigame の primitives は equity 用（`OBVTrend`, `BreakoutDonchian` など）。FX 向けに再設計する。
詳細設計は別ドキュメントに譲るが、最低限の初期セット案:

### TREND_FOLLOW / MEAN_REVERT / NEUTRAL（directional）

| ID | 名前 | 概要 |
|----|------|------|
| F1 | TrendEMA | tanh((EMA_fast - EMA_slow) / ATR) |
| F2 | RSIRevert | tanh((50 - RSI) / scale) |
| F3 | DonchianBreak | tanh((close - DC_mid) / (k×ATR)) |
| F4 | BollingerRevert | tanh((BB_mid - close) / (k × BB_std)) |
| F5 | MACDTrend | tanh((MACD - signal) / scale) |
| F6 | StochRevert | tanh((50 - %K) / scale) |
| F7 | SessionMomentum | tokyo / london / ny セッション内モメンタム |

### MODULATOR（local_gate / multiplicative）

| ID | 名前 | 概要 |
|----|------|------|
| M1 | ATRRegimeGate | ボラティリティ帯選好（高/低 ATR 環境） |
| M2 | SpreadConditionGate | スプレッド許容上限（低スプレッド時のみ通過） |
| M3 | SessionGate | tokyo / london / ny セッション選好 |
| M4 | TrendStrengthGate | ADX > θ 時のみ通過（トレンド強度フィルタ） |
| M5 | EconomicEventGate | 経済指標発表前後の取引抑制 |

これらは既存 `src/strategy/` の素材を再利用できる可能性あり（要確認）。

---

## Stage A/B/C の FX 版定義（再掲）

| Stage | 目的 | 期間 | 通過率目安 |
|-------|------|------|-----------|
| A (Fast Screen) | 明らかに悪い個体除去 | 直近 5-10 日の IS | 40% |
| B (Full IS) | 本格 IS 評価 | 直近 30-60 日の IS | 33% |
| C (OOS) | OOS + Walk-forward | IS 直後 N 日の OOS | Top-K |

Universe = 単一銘柄なので「銘柄数」次元は無し。代わりに **時間軸** で 3 段ゲート。

Alpha Sieve は Stage C 通過後の更に別期間 OOS で再検証。

---

## Skill 移植への影響（軸 1-(b) × 軸 2-(i) 採用時）

| skill | 影響 |
|-------|------|
| fx-run-ga | `--instrument` 必須、Clause 構造を生成・進化、Stage A/B/C を流す |
| fx-analyze-genome-archive | Clause 構造分析（n_clauses 分布、local_gate 使用、構造多様性、primitive 別貢献度）。 `instrument` カラム前提 |
| fx-run-report | 1 銘柄 1 レポート、Clause 構造の summary、Stage 通過率、live_criteria 判定 |
| fx-alpha-sieve | 同銘柄 OOS（別期間）。別銘柄 transfer test は将来 |
| fx-improve-cycle | `--instrument` 第一級、Clause 進化を前提に plan-and-design |
| fx-batch-ga | 銘柄ループ（`--instruments AUD_JPY,EUR_JPY,...`） |
| fx-set-focus | テーマ + ターゲット銘柄 |
| fx-recent-trends | 銘柄別 best B-Sharpe 推移、Clause 構造の変遷 |
| fx-strategic-codex-debate | clause / primitive / 銘柄選択 を議論ターゲットに |

---

## 未決事項（ユーザー回答待ち）

1. **軸 1 — Clause 構造を採用するか?**
   - YES → Phase 2 で `src/dsl/genome.py` を WhenConfig + HowConfig に再構築、FX primitives を実装。
   - NO  → 現フラット式を維持し、skill 群を flat genome 前提に書き換え。
2. **軸 2 — 銘柄特化 GA で進めるか?**
   - YES → 推奨案。`--instrument` 第一級、archive に `instrument` カラム。
   - NO（universal alpha 希望） → 集約方法（mean/min/weighted/portfolio sharpe）の選好も。
3. **優先銘柄**: 6 通貨ペアの主力 / 次点 / 除外の序列。
   - 例: 主力 = EUR_JPY, USD_JPY / 次点 = EUR_USD, AUD_JPY / 除外 = USD_ZAR（スワップ大・スプレッド大）
4. **Phase 2 の Clause 移植スコープ**: zenigame の何を流用し、FX 用に何を新規実装するか細分化（別ドキュメントに譲る）。

---

## 決定後の反映先

- `design.md`（全体設計）— 軸 1 / 軸 2 の決定を前提に書き換え
- `config/alpha_factory/default.yaml` — `dataset.instrument`, Stage Gate, Clause 設定
- `config/alpha_factory/focus-theme.json` — ターゲット銘柄フィールド
- 各 skill の SKILL.md — Clause 前提・銘柄特化前提を明記
