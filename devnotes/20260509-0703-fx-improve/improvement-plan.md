# 最終改善計画: Run 53 → Run 54

**Generated**: 2026-05-09 07:30 JST
**run_id**: `run_20260507_142410` (run-53)
**next run**: Run 54

## 合議ステータス

**CONSENSUS REACHED (Round 1)** — Codex consensus Round 1 で全提案に判定が確定、 追加ラウンド不要。

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **T091 実装 (Stage B gate redesign Phase 1)** | (a) median_oos_sharpe_min: 0.05→0.025、 (b) trade_count_full_dataset 列追加 + selection 切替、 (c) stage_partition_guard holdout 検証 + 二重 opt-in、 (d) 失格理由の分解ログ必須化 (Codex 追加要請) | src/alpha_factory/stage_gate.py、 archive.py、 stage_partition_guard.py、 scripts/alpha_factory/run_ga.py、 src/alpha_factory/run_context.py、 config/alpha_factory/default.yaml | High | Structural + Principled Parametric | Stage B pass 率、 Sharpe / PnL 必要条件充足率 | median + pfre 同時 trigger で全滅 (run-53 で 1439/1439) | Lo (2002) SE 公式から median_oos SE ≈ 0.10、 0.05 閾値が真値 SR=0.05 検出力 50%。 0.025 で 60%。 trade_count_full_dataset で selection 圧整合化。 partition guard で holdout 不整合顕在化 | run-52 archive replay で pass=0 継続なら仮説棄却 | Layer 1 archive replay で Stage B pass>=1、 Layer 2 RUN で trade_count_full>=50 + pnl>=50,000 個体 >=1 | **APPROVE** |

## 並行新規 TODO 登録 (今 cycle 概念設計のみ、 実装は次 cycle)

| # | 施策名 | 内容 | 設計範囲 | 優先度 | 分類 | 合議結果 |
|---|---|---|---|---|---|---|
| 2 | **n_fold_effective=0 上位化ガード** | selection_score に「評価可能性ペナルティ」 1 要素を追加、 best 個体が trade<50 / n_fold_eff=0 で評価不能のまま上位化する問題を構造的に解消 | selection_score 拡張 (selection_score schema bump v3_5、 T091 の v3_4 とは別タイミングで分離)、 IndividualCacheEntry field 追加は **回避** (スキーマ衝突リスク) | High | Structural | **MODIFY** (今 cycle 概念設計のみ、 実装次 cycle) |

## 却下された提案

| # | 提案 | 却下理由 |
|---|---|---|
| 3 | primitive entropy 監視 (Phase 1 内実装) | Phase 1 ゲート正常化前に監視追加しても処方が不明確、 collider bias と責務混線増加。 → Phase 2 へ移動 (APPROVE) |
| 4 | cross-pair shadow 復帰 (Phase 1 内実装) | Stage B 未解決のまま shadow 追加は因果混線。 → Phase 2 へ移動 (APPROVE) |
| 5 | 次 RUN を seed=42 単独で実行 | Reactive Parametric (cherry-pick)、 メタ過学習禁止事項違反 |

## Phase 2 開始トリガー条件 (Codex 確定)

1. T091 実装完了
2. Layer 1 archive replay で Stage B pass>=1 確認
3. Layer 2 RUN で少なくとも 1 個体が trade_count_full>=50 を満たす
4. Stage C 評価が実行可能 (母数ゼロでない)

## 保留事項

| # | 仮説 | 最小変更案 | 検証条件 |
|---|---|---|---|
| H_seed | seed 戦略 (固定 seed=100 維持 vs 別 seed) | T091 完了後に Layer 1 結果で別議論 | run_args は前 RUN 同一 (seed=100, gens=60) で baseline 維持、 比較 seed は分離実験 |

## 次 RUN 実行戦略 (Codex APPROVE)

- run_args: **前 RUN 同一** (`seed=100, gens=60`) で因果同定優先
- T091 完了後の Layer 1 archive replay (run-52 archive で 1+ 件 Stage B pass) を最初に実施
- 比較 seed は別実験で分離 (今 cycle では決定しない)

## T091 実装監視ポイント (Codex 追加要請)

1. Stage B 失格理由の分布 (単一条件集中か)
2. `n_fold_effective` 分布の世代推移
3. `trade_count_full` 下限違反率
4. spread/swap 反映後の PnL 符号反転率
5. Stage C への通過母数 (0 張り付き監視)

## 次フェーズへの申し送り

### Phase C (詳細設計) で確認すべき事項

1. **既存 detailed-design.md (commit 4624c7a) は Codex APPROVED at Round 5、 設計変更不要**
2. Codex 追加要請の「失格理由分解ログ」 を施策 1 に統合 (既存設計の `evaluate_stage_b` の logger 出力で部分対応済、 詳細を確認)
3. 5 監視ポイントを implementation review (Phase 3) で観測対象にする
4. **施策 2 (n_fold_effective=0 ガード) の概念設計を別 devnotes で開始** — `/zenigame-fx-alpha-design` で正規フロー実施 (本 plan-and-design の責務範囲外、 Phase D で TODO 登録)

### Phase 3 (implement) で確認すべき事項

- T091 を 3 段階 incremental で実装 (median → trade_count_full → partition guard)
- 各段階で Layer 1 archive replay を実行 (検証フェーズ)
- 5 監視ポイントの計測値を記録

### 改善計画の使命整合性

- ✅ live_criteria 全指標は維持 (Stage B 内部閾値のみ調整)
- ✅ 取引回数削減なし (むしろ trade_count_full_dataset で全期間 trade 数を要求)
- ✅ オーバーナイト保有なし (intraday 前提維持、 Stage B fold 構造変更なし)
- ✅ archive 値伝搬漏れ防止 (4 段伝搬契約遵守の設計)
- ✅ Reactive 兆候なし (Lo 2002 / Bailey-LdP 2014 の理論根拠 + run-52 archive 直読の反証可能事実に基づく)
