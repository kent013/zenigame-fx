## 各レビュー項目への所見（1〜8、Fact/Interpretation 分離）
前提（C4）  
Fact: 判定根拠はインライン提供された `detailed-design.md` 全文と補足 2 断片のみ。実ファイル実装・pytest 実行結果は未検証。  
Interpretation: 実行時挙動が必要な点は「条件付き判定」または「INCONCLUSIVE」を残す。

1. 関数シグネチャ整合  
Fact: `PrimitiveEvaluator.evaluate(bars, idx, signal)->float`、`compute_composite(clauses, values_per_clause)->float`、`enforce_consistency(genome)->genome` の責務分離は一貫。`values_per_clause` は clause ごとの `dict[name->value]` で `compute_composite` に接続可能。  
Interpretation: 型レベルの整合は概ね良好。ただし `strategy.py` 擬似コードに `evaluator/bars/clauses/genome/units` の参照名ゆらぎがあり、実装時に取り違えると即バグ化するため要修正。

2. 境界条件網羅  
Fact: 仕様として `θ_on` は `>=` で entry、`θ_off` は `<` で exit、`session_close_utc=None` は強制クローズしない、`denom=0 -> 0.0`、空 directional は clause 除去（全除去なら raise）まで明記。  
Interpretation: 主要境界は定義済み。ただし `entry_threshold` の正値制約（例: `entry<=0`）は未拘束で、病的設定時に常時エントリー化し得る。

3. ヒステリシス挙動の正当性  
Fact: 保有時は exit 判定のみ、無保有時のみ entry 判定。`θ_off < composite < θ_on` 領域で「保有継続/新規なし」の非対称は成立。  
Interpretation: 状態機械は閉じている。反転シグナル時に「同バーでドテンしない（close のみ）」仕様は一貫しているが、意図として明文化すると後続実装差異を防げる。

4. `enforce_consistency` の完全性  
Fact: directional/gate の clip・dedupe・最大 clause 数・position の `entry>exit` 化・risk 下限は実装方針あり。全 clause 消失時 raise も明示。  
Interpretation: 「一部の異常入力」には強いが、「全ての異常入力」に対しては不十分。`NaN/inf`（threshold/weight/risk）を弾く規則がなく、不正値が温存され得る。

5. `src/ga/` 非変更と skip 方針  
Fact: 方針は `src/ga` 本体非変更、`tests/ga/*` module-level skip。  
Interpretation: 方針自体は現実的。ただし pytest の module-level skip は“インポート前”ではないため、import 時に壊れるテストは回避不可。`collection 成功` は実測で担保すべきで、設計文だけでは確証不足。

6. spread フィルタ受け渡し契約  
Fact: 後続 TODO に `BacktestConfig.max_spread_bps/swap_cost_per_day` 追加、`evaluate_genome` で `DslStrategy` 組み立てを記載。  
Interpretation: I/F は高レベル記述に留まり、単位・適用タイミング・欠落時 fail-fast・`config→GaConfig→meta→consumer` 4段伝搬契約が不足。North Star の絶対制約（spread/swap を fitness 反映）観点で弱い。

7. `params: dict` mutability 対策  
Fact: mutable/非 hash を認識し、`replace(..., params=new_dict)` 運用と serialize で `dict(...)` コピーを記載。  
Interpretation: 認識は正しいが mitigation は運用依存。生成時の防御的コピー/不変化が無く、共有参照の混入を完全には防げない。

8. テストケース網羅性  
Fact: composite・strategy・enforce の主要ケース（entry/exit 境界、time_stop、session_close、clause truncation 等）は列挙済み。  
Interpretation: 基本網羅は良い。追加必須に近い欠落は `enforce_consistency` 冪等性テスト、`θ_off` 等号の long/short 明示テスト、`NaN/inf` 異常系、`--collect-only` 回帰確認。

## Falsification 結果（H1〜H4）
- H1: `max_clause=1` でもフラット式と非等価が保証される  
結果: **FALSIFIED**  
Fact: 1 clause・gate 空・clause.weight=+1 のとき `composite = dir_score` となり、フラット正規化式と一致する構成が存在。  
Interpretation: 「非等価保証」は成立しない。保証したいなら構文/評価に追加制約が必要。

- H2: `src/ga/` を変更しない戦略で pytest collection は成功する  
結果: **INCONCLUSIVE（条件付き支持）**  
Fact: 設計文は「import は成功し runtime で壊れる」と仮定。  
Interpretation: pytest 実挙動は import 時点依存のため、実測なしに確定不可。`--collect-only` で検証が必要。

- H3: `enforce_consistency` は冪等（`f(f(x))==f(x)`）  
結果: **SUPPORTED（有限実数入力前提）**  
Fact: clip/dedupe/truncate/swap+epsilon は決定的で、2回目適用で追加変化しない構造。  
Interpretation: 通常入力では冪等と見なせる。`clip` の NaN 振る舞い次第で例外があり得るため、非有限値の明示排除が望ましい。

- H4: `DslStrategy` 境界条件（`θ_on/θ_off` 等号）が望ましい挙動として網羅  
結果: **SUPPORTED_WITH_GAP**  
Fact: 仕様文で等号/不等号は明記。テスト一覧に `θ_on` 等号は明示。  
Interpretation: 設計意図は網羅。ただし `θ_off` 等号（long/short）を“明示値で”固定するテスト追記が必要。

## 致命的指摘 (Blockers)
1. **H1 反証成立**: `max_clause=1` でフラット式と等価な個体が構成可能。設計目標に「非等価保証」を置くなら未達。  
2. **`enforce_consistency` の異常入力完全性不足**: `NaN/inf` を無効化する規則がなく、「全異常入力で有効 Genome or 意図的 raise」の要件を満たせない。  
3. **spread/swap I/F 契約の粒度不足**: 4段伝搬と fail-fast 条件が未定義で、絶対制約（fitness 反映）に対する仕様保証が弱い。

## 改善提案 (Non-blocking)
1. `enforce_consistency` に `isfinite` 検証を追加し、非有限値は clip ではなく明示 raise。  
2. H1 を解消したい場合は `max_clause=1` を禁止、または `gate 必須/非線形項必須` などの非等価制約を enforce 側で固定。  
3. spread/swap 契約に「単位（bps/日次コスト）」「適用時点（約定前フィルタ/fitness控除）」「欠落時の例外」を明記。  
4. テストに `test_enforce_idempotent`、`test_exit_at_theta_off_equal_long_short_no_close`、`test_enforce_rejects_nan_inf`、`pytest --collect-only` CI を追加。  
5. `params` は `Mapping` 化または生成時 defensive copy で共有参照を構造的に遮断。

## 判定: NEEDS_REVISION