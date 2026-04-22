# 用語集 (Terminology)

## 目的

zenigame-fx Alpha Factory の全ドキュメントから参照される横断用語集。各用語の初出は必ず本ファイルの anchor へリンクする。

## スコープ

本 Alpha Factory 固有の概念・略語・統計指標を収録する。一般的な金融用語（Sharpe, Drawdown など）は収録しない。

## 用語リンク

本ドキュメントが SSOT のため、他ファイルへのリンクは不要（本ファイルへの被リンク側のみ）。

## 主要定義

### Clause

`<a id="clause"></a>` Clause — ゲノムを構成する最小の判断単位。`directional × local_gate × weight` の 3 要素で 1 clause が構成される。複数 clause を `composite score` で合成して売買判定に使う。Jordan & Jacobs (1994) Mixture of Experts の系譜。

### Composite Score

`<a id="composite-score"></a>` Composite Score — 複数 clause を加重合成して得られる最終判断スコア。形: `Σ(cw_k × cs_k) / Σ|cw_k|`。ヒステリシス付き閾値判定でエントリー・エグジットを出す。

### Directional

`<a id="directional"></a>` Directional Signal — 方向性（long / short）を決める signal 群の加重和。形: `Σ(w_i × x_i) / Σ|w_i|`。

### Local Gate

`<a id="local-gate"></a>` Local Gate — 同じ clause 内の directional signal を閉じる / 開くゲート関数群。`[0, 1]` sigmoid 有界。

### Modulator

`<a id="modulator"></a>` Modulator — local_gate / global_gate を構成するプリミティブ群（ATRRegimeGate / SessionGate / VIXRegimeGate 等）。方向性を生まず、他 signal の効力を調整する。

### Tier

`<a id="tier"></a>` Tier — スイムレーンの階層。Tier 1 = per-instrument GA、Graduation lane = 卒業個体の universal 探索。

### Lane

`<a id="lane"></a>` Lane — スイムレーン内の独立した GA 個体群。instrument × tier で 1 レーン。

### Graduation

`<a id="graduation"></a>` Graduation — Tier 1 で Stage C 通過かつ (ii-lite) shadow 基準超えの個体を Graduation lane に昇格させる条件・処理。

### Stage A

`<a id="stage-a"></a>` Stage A — Fast Screen。短期窓で低コストスクリーニング + 複雑度ペナルティ α_A 適用。

### Stage B

`<a id="stage-b"></a>` Stage B — Full IS + Walk-Forward OOS。train / test / step / embargo の 4 パラメータで WF を実行、median OOS Sharpe / 正 fold 比率 / DSR の複合判定。

### Stage C

`<a id="stage-c"></a>` Stage C — Live Criteria 判定 + スプレッド stress + trade range チェック + (ii-lite) 評価。

### Walk-Forward

`<a id="walk-forward"></a>` Walk-Forward (WF) — 時系列 OOS 検証手法。train 窓で学習、test 窓で評価、step 幅で前進。embargo で train/test 境界のリーク防止。López de Prado (2018) Advances in Financial ML。

### IS / OOS

`<a id="is-oos"></a>` IS / OOS — In-Sample / Out-of-Sample。学習に使った区間 / 使っていない区間。

### DSR

`<a id="dsr"></a>` DSR — Deflated Sharpe Ratio。複数試行・非正規分布を補正した Sharpe の有意性指標。Bailey & López de Prado (2014)。

### PBO

`<a id="pbo"></a>` PBO — Probability of Backtest Overfitting。CSCV (Combinatorially Symmetric Cross-Validation) で得られる過学習確率。Bailey et al. (2014)。

### Reality Check

`<a id="reality-check"></a>` Reality Check — 複数戦略の同時有意性検定。ブートストラップで null 分布を構成し p 値を得る。White (2000)。

### SPA

`<a id="spa"></a>` SPA — Superior Predictive Ability test。Reality Check の改良版。Hansen (2005)。

### CRN

`<a id="crn"></a>` CRN — Common Random Numbers。複数戦略を同じ乱数系列で比較してノイズを相殺する分散削減手法。

### TC

`<a id="tc"></a>` TC — Transaction Cost。スプレッド・スリッページ・手数料・スワップを合算した取引コスト。本プロジェクトでは fitness に必ず反映する（絶対制約）。

### IC

`<a id="ic"></a>` IC — Information Coefficient。signal 値と将来リターンの順位相関（Spearman）。プリミティブ評価の基本指標。

### (ii-lite)

`<a id="ii-lite"></a>` (ii-lite) Cross-pair Evaluation — target ペア + アンカー 2 ペアで同一ゲノムを評価し、集約指標で通過判定する軽量 cross-pair 検証。hard gate 化は Phase 6。

### Anchor Pair

`<a id="anchor-pair"></a>` Anchor Pair — (ii-lite) で target と並走評価するアンカー通貨ペア。target ごとに 2 本固定。

## SSOT 参照

本ファイル自身が用語の SSOT。`config/alpha_factory/default.yaml` への参照は無い。

## 関連ドキュメント

- [clause-architecture.md](clause-architecture.md)
- [stage-gates.md](stage-gates.md)
- [swim-lane.md](swim-lane.md)
- [cross-pair.md](cross-pair.md)
- [statistics.md](statistics.md)
- [migration-triggers.md](migration-triggers.md)

## 関連 TODO

- 未着手（用語追加は各 doc 作成時に随時）
