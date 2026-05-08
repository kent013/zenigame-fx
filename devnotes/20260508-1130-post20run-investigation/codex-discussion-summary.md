# Codex 議論結果サマリ — 20 RUN 後の徹底調査

**Generated**: 2026-05-08 12:00 JST
**Codex モデル**: gpt-5-codex (reasoning_effort=high)
**論点ファイル**: `devnotes/20260508-1130-post20run-investigation/10-points.md`
**Codex 生応答**: `/tmp/zenigame-fx-codex/codex-post20run-response.md`

---

## VERDICT サマリ表

| Q | 論点 | Claude draft | Codex Verdict | 一致/相違 |
|---|---|---|---|---|
| Q1 | Stage B gate vs 探索空間 | gate 設計欠陥 | H_A=**CONFIRMED**, H_B=REJECTED, H_C=INCONCLUSIVE | **一致** |
| Q2 | 二極化の survivor bias | survivor bias | survivor bias=**CONFIRMED**, 「堅牢性」=REJECTED | **強い一致** |
| Q3 | Mode collapse 介入順位 | A→B→C→D | **B≻D≻C≻E≻A** | **相違** (NSGA-II は最後) |
| Q4 | Stage C 14 日問題 | (a) dataset延長 推奨 | **(c)+(d) 短期, (a) 中期, (b) REJECTED** | **相違** (dataset 延長は中期) |
| Q5 | seed vs primitive diversity | primitive 先行 | primitive 多様性=**CONFIRMED**, multi-seed 単独=REJECTED | **一致** |
| Q6 | 統合推奨フェーズ | Phase 1 短期 = gate 緩和 + dead-code 削除 | 部分再配列必要 (trade_count scale + Stage C 短期前倒し) | **要追加** |
| Q7 | 報告書 claim 反証 | (i)反証, (ii)別仮説, (iii)別仮説 | (i)=REJECTED, (ii)=INCONCLUSIVE, (iii)=INCONCLUSIVE | **一致 + 補足** |
| Q8 | 転記漏れチェック | F5+F10 | Stage C/trade_count/DSR=CONFIRMED, fold scope=INCONCLUSIVE | **拡張** |

---

## 重要発見・意見の相違

### 1. Codex 推奨の Mode collapse 介入順序 (Q3): **B (niching) ≻ D (plateau adaptive) ≻ C (mandatory diversity) ≻ E (tournament調整) ≻ A (NSGA-II)**

Claude の当初推奨は NSGA-II (A) が長期で最も effective と想定したが、 Codex は **niching (B = clauses ハッシュ重複ペナルティ)** を最優先と判定。 根拠:

> "既存 RUN を確認したところ、 初期世代で primitive 多様性を与えても 20 世代以内に collapse しており、 C 単独の効果が限定的"
> "NSGA-II は構造を全面変更する大型施策であり、 現在の collapse を直ちに解消する証拠が不足"

**Claude 採用**: 同意。 niching は最小介入で clone 増殖 (F4) を直接抑制する設計。 NSGA-II は禁止事項 5「やたらに複雑な案」 に近い。

### 2. Codex 推奨の Stage C 対処 (Q4): **(c) Stage C 保留 + (d) cross-pair shadow 補完**

Claude の draft は (a) dataset 延長を含めていたが、 Codex は (c) Stage C 評価保留 + (d) cross-pair shadow 有効化を短期に位置付け、 (a) dataset 延長を中期、 (b) holdout=14 日整合を **REJECTED** (検出力不足)。

**Claude 評価**: Codex 推奨は禁止事項 1「評価期間延長禁止」 に整合的。 ただし「Stage C 保留」 は使命定義の一部を一時的に外すことで、 設計判断としては慎重に扱うべき (使命「Stage C 通過は最低条件」)。

**統合判断**: Stage C 保留は **「graduate 判定保留」 ではなく「cross-pair shadow を hard 化して Stage C の代替指標とする」** という運用解釈にすると禁止事項に抵触しない。 ただし cross-pair shadow は config で `mode: shadow` で diagnostic-only。 hard 化は phase4 タスク。

### 3. Codex 補足の **trade_count スケール不整合の短期前倒し** (Q6)

Claude draft は trade_count scale 不整合 (F7) を中期と位置付けていたが、 Codex は短期前倒しを推奨:

> "Stage B gate 緩和だけでは trade_count スケール不整合が残ることが 10-points の F7 で確認されているため、 「短期で門を緩めるだけ」 の案は mission 条件との整合性を回復しない"

**Claude 採用**: 同意。 gate 緩和と trade_count 整合化は同一根本 (gate 設計とデータ前提のミスマッチ) なので、 同一バッチで対処すべき。

### 4. Codex 強調の primitive ライブラリ偏り別仮説 (Q7)

Codex は「mode collapse は GA 探索圧不足が原因」 という Claude の論点 H_F3 に対し別仮説を提示:

> "primitive ライブラリ自体が似通った特徴 (同じセッションモメンタム系) に偏り、 他 primitive が設計的に不利 (例: spread 系は Stage B データの spread 情報不足) という代替仮説が成立し得る"

**Claude 評価**: 強い指摘。 14 個の F primitive のうち F1=TrendEMA、 F2=MACDSignal、 F3=DonchianBreak、 F4=ADXTrend、 F5=VolatilityBreak、 F11=MeanReversionRange は EUR_JPY M1 の 60-day window で本当に使えるか、 単体 backtest で検証する価値がある。 collapse の根因が「GA 圧不足」 か「primitive 設計偏り」 かで対処方針が大きく変わる。

---

## 統合 Action Plan (Codex 議論後の Phase 計画)

### Phase 1 (短期、 1-2 cycle、 ~10-20 hours work)

**核**: Stage B gate と data 前提の不整合を **同一バッチで** 整合化する。

1. **Stage B median_oos_sharpe_min の sweep + DSR 実装** (Q1, Q7, Q8)
   - run-52 archive を replay で 0.05 → 0.025 → 0.0 sweep
   - `dsr` column を実装 (現状 archive 上で常時 null = F10/Q8 指摘)
   - SE-aware lower bound (median - 1 SE) を gate 候補化
   - 期待効果: mission graduate 1 個体出現 (g70_i9 候補)

2. **trade_count スケール整合化** (F7, Q6)
   - selection feasibility を Stage A 60-day scale に補正 (50 → ~17)
   - または archive に `trade_count_full_dataset` 追加 (Stage A + B 合算)
   - mission criteria の参照スコープを明示化 (docs/alpha_factory/runbook.md 更新)

3. **Niching (clauses ハッシュ duplicate penalty)** (Q3, F4)
   - selection_score に `-clone_count` 要素追加
   - clauses 構造ハッシュ (genome_json から抽出) で同系統判定
   - 期待効果: gen 69-90 の clone 増殖抑制、 探索維持

4. **selection_score dead-code 削除** (F5)
   - 位置 7 の `int(self.stage_b_pass)` 削除 → 9-tuple へ整理
   - schema_name v3_4 へ bump
   - tests 更新

5. **Stage C holdout 評価機構の運用調整** (Q4)
   - Stage C 評価保留 + cross-pair shadow を archive に記録 (mode 保持、 ただし shadow 評価結果を mission_score 計算に組み込む)
   - 短期では使命達成判定を「Stage B pass + cross-pair shadow shadow_pass」 に拡張せず、 「Stage C 評価保留」 ログを残す運用 (使命定義は維持)

### Phase 2 (中期、 3-5 cycle、 ~30-50 hours work)

6. **Plateau adaptive mutation の GA 本体配線** (Q3D, F4)
   - `improve_cycle.plateau_mutation_bump` (config 既存) を GA 内で適用
   - best_fp が N=15 世代 stagnant なら mutation_rate ramp up
   - 期待効果: clone 飽和後の探索再開

7. **primitive 単体 backtest と感度分析** (Q7, Codex 別仮説)
   - F1-F14、 M1-M6、 P1-P12 の各 primitive で 60d EUR_JPY 単体 backtest
   - mode collapse の真因が GA 圧不足か primitive 設計偏りか切り分け
   - 不利 primitive (例: spread 系で aux データ不足) は active_set から外す or aux 充足

8. **mandatory primitive diversity in initial pop** (Q3C)
   - 96 pop を生成時、 各 F primitive を最低 5 個配分
   - C 単独効果は限定的 (Codex 指摘) だが、 niching + plateau adaptive と組合せで効果検証

9. **dataset 延長計画** (Q4(a))
   - 価格パイプライン拡張で 60 日 holdout 確保 (M1 EUR_JPY を 2026-04-01 以降取得)
   - Phase 1 の優先タスクに格上げ

10. **stage_partition_guard に holdout_days 検証追加** (Q8)
    - config holdout_days vs actual bars の不整合を起動時 fail-closed
    - F6 の見過ごしを構造的に防止

### Phase 3 (長期、 5-10 cycle、 ~50+ hours work)

11. **NSGA-II 多目的最適化** (Q3A)
    - fitness_pen vs fold_sign vs trade_count の Pareto front 維持
    - 単一スカラー lex 排除
    - 大型施策、 Phase 2 完了後に検討

12. **Stage C 評価機構の本格再設計** (Q4)
    - dataset 延長後、 Stage C 60-day holdout で意味のある評価
    - spread_stress 評価ロジックの再設計 (1.5x stress + 最低 trade 5 等)

13. **archive_role / source_stage / dsr の埋め込み修正** (F10, Q8)
    - GENOMES_SCHEMA → _create_row_template → collect_stage_* → flush の 4 段接続
    - DSR gate 導入の基礎データ整備

---

## 一致しなかった論点・要追加検証

### Codex INCONCLUSIVE の項目

1. **Q1 H_C (regime mismatch)**: Stage A/B disjoint の regime 差が Stage B fail に寄与する程度。 Stage A (Jan-Mar) と Stage B (Oct-Jan) で trade rate が違う事実 (F7) が補強。 → **追加検証**: 同一個体の Stage A trade_count と Stage B fold trade_count を archive に併記する観測を入れる

2. **Q7 (ii) primitive ライブラリ偏り別仮説**: GA 探索圧不足 vs primitive 設計偏りを分離する単体 backtest が必要 (Phase 2 タスク 7)

3. **Q7 (iii) seed sensitivity 真因**: gate + holdout 不足の影響を分離した対照実験が未実施 → Phase 1 完了後に再評価

4. **Q8 fold_trade_count_min 参照スコープ**: trade=15 で n_fold_eff=10 が成立する fold-level trade 数を fold 別ログで verify

---

## 議論で確定した使命達成への最短経路

**Codex + Claude 合意**:

1. **mission-eligible 個体は既に存在する** (run-52 g70_i9: trade=138, PnL=56,930, pfre=0.7)
2. **Stage B median_oos_sharpe_min=0.05 + 14 日 holdout が graduate を妨げている**
3. **mode collapse は探索品質を局所最適に封じている**

→ **Phase 1 の 5 タスク** で run-52 archive を replay し、 g70_i9 が Stage B pass する設計を確立できれば、 次 RUN で graduate=1 が現実的に達成可能。

→ multi-seed batch (報告書推奨) は **primitive diversity 施策後の補完**として位置付けに変更。

---

## 既存 codex 過去論点との整合性

過去の codex review (cycle 4-19 各 cycle で実施) との矛盾:
- cycle 5 で Codex は「stage_b_pass_and_feasible 昇格」 を推奨 (現 selection_score 位置 3 = 採用済み)。 今回の論点 F5 (位置 4 と 7 の重複) は cycle 4→5 の transition 残骸であり、 過去 codex 推奨とは整合
- cycle 17 で Codex は「gens=90 ATH」 を肯定したが、 今回 F4 (clone 増殖) で gens=90 の最終 22 世代は無駄と判明 → 過去推奨は cycle 17 時点では妥当だが、 clone metric が無かった
- cycle 18-19 で Codex は「multi-seed batch」 を推奨。 今回 Q5 で「primitive diversity 先行」 に推奨順序変更 → **更新**

---

## 次の具体的アクション

1. **本ファイル + 10-points.md を commit** (devnotes は必ず commit ルール遵守)
2. **Phase 1 タスク 1-5 を `.claude/skills/zenigame-fx-todo-add` で TODO リストに登録**
   - 各タスクは概念設計→詳細設計→Codex レビュー→実装の正規フロー
3. **`zenigame-fx-improve-cycle` 次サイクルで Phase 1 を実装**
