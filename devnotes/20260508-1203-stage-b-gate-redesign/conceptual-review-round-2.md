**重点レビュー**

1. `median_oos_sharpe_min 0.05 → 0.025`

- **Fact**: 変更対象は `stage_b_median_oos_sharpe_min` であり、`live_criteria.sharpe_min` 自体は変更していない。
- **Fact**: Stage B は trade-level Sharpe、live criteria は T042 換算後の annualized Sharpe という別スケールとして扱われている。
- **Fact**: 設計は「真値 SR=0.05 の個体が 0.025 以上になる確率 ~84%」と主張している。
- **Interpretation**: これは禁止事項 4 の直接違反ではない。Stage B gate は live criteria そのものではないため、`live_criteria` 緩和とは区別できる。
- **Interpretation**: ただし Stage B は使命候補を選別する主要ゲートなので、実質的な探索圧の緩和ではある。根拠が弱い場合は「いたずらな緩和」に近づく。
- **Interpretation**: 確率計算の根拠が崩れている。SE=0.10、真値 0.05、閾値 0.025 なら `P(estimate >= 0.025)` は概算で約 60% であり、84% ではない。
- **Falsification**: run-52 replay で `median_oos_sharpe>=0.025` 通過個体が出ても、Stage C と cross-pair ii-lite を通らなければ「live_criteria 達成に本質貢献」とは言えない。
- **判定**: **Warning**
- **修正提案**: 0.025 採用自体は可。ただし Lo (2002) に基づく確率説明を修正し、成功条件を「Stage B pass」ではなく「Stage C + live_criteria + cross-pair ii-lite 通過候補の増加」に置き直すべき。

2. DSR per-fold 計算

- **Fact**: 設計は「per-fold で DSR を計算し median across folds」と書いている。
- **Fact**: DSR の trial 数 `N` を何にするかが定義されていない。
- **Fact**: 設計は DSR を「過去最大値からのドローダウン補正」と説明している。
- **Interpretation**: DSR の説明が不正確。Bailey & López de Prado (2014) の DSR は主に selection bias、multiple testing、非正規性を補正する指標であり、ドローダウン補正ではない。
- **Interpretation**: `N` 未定義のまま non-null DSR を archive に記録すると、見た目は統計量だが意味が固定されない危険な列になる。
- **Interpretation**: per-fold trade 数が `fold_trade_count_min=10` 近辺だと skew/kurtosis 推定も不安定で、DSR の信頼性は低い。monitor only でも `dsr_method` や `dsr_trials` なしでは再解釈できない。
- **Falsification**: 同じ fold Sharpe に対して `N=世代内全個体数`、`N=Stage B 到達個体数`、`N=有効独立ゲノム数` のどれを使うかで DSR 符号が変わるなら、この設計の DSR は gate 設計材料として使えない。
- **判定**: **Critical**
- **修正提案**: Phase 1 では `dsr` 実値化を延期するか、`dsr_method`, `dsr_trials`, `dsr_observations`, `dsr_skew`, `dsr_kurtosis`, `dsr_valid` を同時に定義する。`N` は最低でも「同一 run・同一 fold で Stage B 評価対象となった候補数」などに固定し、近似であることを archive に残すべき。

3. `trade_count_full_dataset`

- **Fact**: 設計は `trade_count_full_dataset = Stage A + Stage B` としている。
- **Fact**: Stage B は walk-forward fold 構造であり、`wf_test_days=18`, `wf_step_days=5` なら OOS 期間が重複し得る。
- **Fact**: 設計自身が「Stage B 全体 backtest は別途必要」と書いている。
- **Interpretation**: fold trade 数の単純合算では、同じ時間帯・同じシグナル由来の trade を重複カウントする可能性がある。
- **Interpretation**: selection の `feasible` に使う指標なので、計算定義が曖昧なまま導入すると探索圧そのものを誤誘導する。
- **Interpretation**: archive 4 点セットは概念上触れられているが、重点項目の `config → GaConfig → meta → consumer` という伝搬観点では不足がある。特に consumer は `run_ga.py` selection cache だけでなく replay/report 側も対象になる。
- **Falsification**: `Stage B fold trade 合算` と `Stage B 全期間単発 backtest` で `trade_count_full_dataset>=50` の判定が異なる個体が多数出るなら、この設計の selection 改善効果は成立しない。
- **判定**: **Critical**
- **修正提案**: `trade_count_full_dataset` の canonical 定義を先に決めるべき。推奨は「Stage B partition 全体を 1 回だけ OOS 相当で再評価した unique trade count + Stage A unique trade count」。fold 合算を使う場合は entry/exit timestamp と instrument で de-duplicate する契約を明記する。

4. `--allow-holdout-short`

- **Fact**: 設計は holdout_days 不整合を fail-closed にしつつ、smoke test 用に `--allow-holdout-short` を許可している。
- **Fact**: Stage C は使命達成の最低条件であり、holdout 不足は評価信頼性を直接下げる。
- **Interpretation**: escape hatch 自体は開発運用上あり得る。
- **Interpretation**: ただし production RUN で誤指定できるなら、fail-closed guard の意味が弱くなる。
- **Falsification**: `--allow-holdout-short` 付き RUN の archive が通常 RUN と区別できず、graduate 判定や calibrate/history に混入するなら、この escape hatch は不適切。
- **判定**: **Warning**
- **修正提案**: `--allow-holdout-short` は `--run-mode smoke` または専用 env var との二重 opt-in にする。さらに archive/meta/log に `holdout_short_override=true` を必ず記録し、この RUN では graduate 判定・calibrate 反映・live_criteria 達成扱いを禁止するべき。

5. H_A1〜H_A3 の反証可能性

- **Fact**: H_A1 は「mission-eligible 7/7 が Stage B pass」としている。
- **Fact**: 設計本文では 7 個体中 5 個体が `positive_fold_ratio<min` にも blocked と記載されている。
- **Interpretation**: H_A1 は設計本文内の事実と矛盾している。反証可能以前に仮説が過大。
- **Fact**: H_A3 は「次 RUN で trade>=120 over-trading 個体の比率が下がる」としている。
- **Interpretation**: 1 RUN 比較では GA の確率変動、median threshold 変更、selection 変更が交絡する。C3 collider bias と C7 sample size の観点で因果 claim には弱い。
- **Falsification**: H_A1 は replay で 0 件なら反証可能だが、期待値 `7/7` が誤っている。H_A3 は single RUN では反証条件が曖昧で、失敗しても stochastic noise と区別できない。
- **判定**: **Critical**
- **修正提案**: H_A1 は「pfre>=0.6 かつ median のみ blocked の g70_i9/g83_i12 が 1 件以上 pass」に修正する。H_A3 は archive replay の top-K selection before/after、または同 seed 複数条件の比較に変更し、最低でも分布比較として扱うべき。

**観点別まとめ**

- **[Warning] 使命整合性**: Stage B 改善は使命に関係するが、成功条件が「Stage B pass + PnL + trade_count」に寄りすぎている。修正提案: 成功判定に Stage C、live_criteria 全指標、cross-pair ii-lite を明示する。
- **[Warning] 禁止事項**: live criteria の直接緩和ではないが、Stage B gate 緩和の統計根拠に誤りがある。修正提案: 0.025 の根拠を再計算し、replay で副作用を確認する。
- **[Critical] 実現可能性**: DSR と `trade_count_full_dataset` の定義が未確定。修正提案: 実装前に `N`、returns 単位、trade count de-dup 契約を詳細設計へ落とす。
- **[Warning] 期待効果**: run-52 の観察から gate 問題を疑うのは妥当だが、single archive replay だけで因果確定はできない。修正提案: replay と次 RUN を分け、前者は機械的再判定、後者は探索挙動の観察に限定する。
- **[Suggestion] スコープ**: incremental 方針は妥当。ただし Phase 1 に threshold、DSR、selection、partition guard を同時に入れると原因帰属が濁る。修正提案: threshold replay → trade_count 定義 → DSR monitor → guard の順で段階適用する。

**全体判定: CHANGES_REQUESTED**

方向性は概ね妥当です。特に `median_oos_sharpe_min` の変更は live criteria 緩和そのものではありません。ただし、DSR の `N` 未定義、`trade_count_full_dataset` の計算定義未確定、H_A1/H_A3 の反証設計不備は実装前に直す必要があります。