全体判定: `CHANGES_REQUESTED`

Round 1 解消状況の要約です。`Critical 3` と `Critical 8` は概ね解消、`Warning 1/2/3/4/5/5b` も概ね反映されています。`Critical 9` は部分解消ですが、`system_failure` / `metric_unavailable` の 0.0 fallback が残るため、sentinel 序列の整合性はまだ未完です。

**1. 使命との整合性**
Fact:
- [Suggestion] 無取引個体の構造的優位を止める狙いは、現行の `selection_score=(C_pass,B_pass,A_pass,fitness_pen)` に直接効く論点で、使命との整合は取れています。[scripts/alpha_factory/run_ga.py:110](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L110)
Interpretation:
- 方針自体は正しいです。Round 1 の「`src/ga/runner.py` ではなく Alpha Factory 側を触るべき」という修正要求にも沿っています。

**2. 禁止事項違反**
Fact:
- [Suggestion] `live_criteria.trade_count_min` を触らず、別の `min_exposure_trade_count` を導入する方針、archive schema 変更を scope 外に置く方針は、禁止事項回避として妥当です。[config/alpha_factory/default.yaml:31](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml#L31)
Interpretation:
- 閾値チューニングで逃げず、構造欠陥を直す設計になっています。

**3. 実現可能性**
Fact:
- [Suggestion] 変更対象を `src/alpha_factory/stage_gate.py` / `src/alpha_factory/config.py` / `config/alpha_factory/default.yaml` / tests に置き直したのは妥当です。現行 loader も Stage A 設定をここで受けています。[src/alpha_factory/config.py:261](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L261)
Interpretation:
- 実装コストは小さく、phase の粒度も適切です。

**4. 期待効果の妥当性**
Fact:
- [Critical] `no_trades` の因果列は正しく書き直せています。現行コードでも `evaluate_stage_a` は `trade_count<1` で `fitness_pen=None` のまま返し、archive がそれを `0.0` に正規化し、GA が tie-break に使っています。[src/alpha_factory/stage_gate.py:304](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L304) [src/alpha_factory/archive.py:212](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L212) [src/alpha_factory/archive.py:337](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L337) [scripts/alpha_factory/run_ga.py:110](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L110)
- [Critical] ただし、提案仕様は `no_exposure` にしか sentinel を入れていません。一方、現行 `system_failure` と `metric_unavailable` も `fitness_pen=None` のままなので、archive で引き続き `0.0` になります。[src/alpha_factory/stage_gate.py:304](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L304) [src/alpha_factory/stage_gate.py:308](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L308) [src/alpha_factory/archive.py:212](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/archive.py#L212)
- [Warning] 「best 個体が trade_count=0 状態で plateau する現象の解消」を Verified に置くのは少し強いです。混合集団では言えますが、全個体が no-trade なら best は依然 plateau し得ます。
Interpretation:
- `no_trades` 問題の主鎖は捉えていますが、sentinel 序列を名乗るなら `system_failure` と `metric_unavailable` も同じ 0.0 fallback から外す必要があります。ここが未修正のままだと、序列定義が自己矛盾です。

**5. リスク**
Fact:
- [Warning] `calibrate_gate` は `fitness_pen_pool` に archive 全行をそのまま入れて quantile を取ります。sentinel 混入は現行ロジックに直接入ります。[src/alpha_factory/calibrate_gate.py:317](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py#L317) [src/alpha_factory/calibrate_gate.py:548](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py#L548)
Interpretation:
- 概念設計で「詳細設計で確認」と置くのは理解できますが、少なくとも「混入を許容するのか」「除外するのか」は概念レベルで決めておいた方が安全です。

**6. スコープの適切さ**
Fact:
- [Suggestion] `src/ga/runner.py` 非対象、archive schema 非変更、selection ロジック非変更という切り分けは適切です。
Interpretation:
- 直すべき構造点だけを触っており、scope creep は抑えられています。

**7. メモリ制約**
Fact:
- [Suggestion] 追加されるのは config の整数 1 個と sentinel 定数、既存 row への値代入のみで、メモリ増分は実質無視できます。
Interpretation:
- この観点の懸念はありません。

**8. 前提検証 (C4)**
Fact:
- [Warning] `no_trades` の verified chain は十分です。ただし「0.0 fallback を持つ悪性経路」が `no_trades` だけなのか、`system_failure` / `metric_unavailable` も含むのか、反証側の棚卸しがまだ足りません。[src/alpha_factory/stage_gate.py:302](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L302)
Interpretation:
- C4 は前進していますが、最終版としては「Stage A の `fitness_pen=None` 発生経路一覧」を先に固定した方が堅いです。

**9. Design-first (C1)**
Fact:
- [Warning] 実コード参照は十分入っていますが、SSOT 文書側では Stage A canonical reason code がまだ `no_trades` のみで、`no_exposure` や `min_exposure_trade_count` は未定義です。[docs/alpha_factory/stage-gates.md:111](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md#L111)
- [Warning] 既存テストも `("no_trades",)` を固定で期待しています。reason code 変更方針を明文化しないと詳細設計でぶれます。[tests/alpha_factory/test_stage_gate.py:350](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_stage_gate.py#L350)
Interpretation:
- `Critical 9` は「コード参照を足した」という意味では改善していますが、doc SSOT の更新対象がまだ明示不足です。`stage-gates.md` を同 phase の更新対象に含めるべきです。

修正要求は 2 点です。`system_failure` / `metric_unavailable` を含む Stage A の `fitness_pen=None` 経路全体に対して sentinel 方針を定義し直すこと、そして `no_exposure` / `min_exposure_trade_count` を `docs/alpha_factory/stage-gates.md` の canonical 語彙と SSOT に反映することです。これが入れば、Round 2 としては `APPROVED` に近い内容です。