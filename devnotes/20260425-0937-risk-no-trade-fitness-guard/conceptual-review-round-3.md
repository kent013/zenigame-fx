全体判定: `CHANGES_REQUESTED`

Round 2 の残件のうち、`system_failure / metric_unavailable を含む 3 経路 sentinel 化`、`best 個体 plateau を仮説に降格`、`docs SSOT を本 phase に含める` は概ね解消です。未解消なのは `calibrate_gate` の sentinel 除外条件です。

**1. 使命との整合性**  
Fact:
- [Suggestion] 無取引個体の構造的優位を、Stage A → archive → GA selection の主鎖で潰す設計になっています。[conceptual-design.md:36](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L36) [run_ga.py:111](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py#L111)
Interpretation:
- 使命との整合性はあります。直す場所も適切です。

**2. 禁止事項違反**  
Fact:
- [Suggestion] `live_criteria.trade_count_min` は触らず、`min_exposure_trade_count` を別導入する方針です。[conceptual-design.md:72](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L72)
Interpretation:
- 禁止事項 #4 を回避できています。

**3. 実現可能性**  
Fact:
- [Suggestion] 変更対象は `stage_gate/config/default/tests/calibrate_gate/docs` に閉じており、現行 loader にも素直に追加できます。[config.py:261](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/config.py#L261) [conceptual-design.md:102](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L102)
Interpretation:
- 実装可能性は高いです。

**4. 期待効果の妥当性 (C3 / C7)**  
Fact:
- [Suggestion] Stage A の `fitness_pen=None` 3 経路を明示し、sentinel 序列を定義した点は Round 2 Critical の修正として妥当です。[conceptual-design.md:48](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L48)
- [Suggestion] 「best 個体 plateau 解消」は Verified ではなく仮説に降格されています。[conceptual-design.md:84](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L84)
Interpretation:
- C3/C7 観点の過剰 claim は概ね解消しています。

**5. リスク**  
Fact:
- [Critical] `calibrate_gate` で「sentinel 値を除外する」と書いている一方、提案 filter `fitness_pen > _NO_EXPOSURE_FITNESS / 10` だと `_METRIC_UNAVAILABLE_FITNESS = -1e6` は除外されません。設計本文では `metric_unavailable` も sentinel です。[conceptual-design.md:52](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L52) [conceptual-design.md:112](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L112)
- [Critical] `fitness_pen = sharpe - α·size_norm` の `sharpe` には下限 clamp がありません。現行実装上、通常実値が `-1e8` を下回らない保証はありません。[metrics.py:44](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py#L44) [stage_gate.py:312](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/stage_gate.py#L312)
- [Fact] 現行 `calibrate_gate` は pool に archive 全行をそのまま入れています。[calibrate_gate.py:317](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/calibrate_gate.py#L317)
Interpretation:
- Round 2 Warning 5 は未解消です。`fitness_pen > -1e8` は不適切です。除外は閾値分離ではなく、3 sentinel の**明示一致除外**で固定すべきです。

**6. スコープの適切さ**  
Fact:
- [Suggestion] `archive schema` 非変更、`selection_score` 非変更、`src/ga/runner.py` 非対象の切り分けは維持されています。[conceptual-design.md:75](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L75) [conceptual-design.md:109](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L109)
Interpretation:
- スコープは適切です。

**7. メモリ制約**  
Fact:
- [Suggestion] 定数追加と軽微な filter 追加が中心で、row schema も増えません。
Interpretation:
- メモリ懸念はありません。

**8. 前提検証 (C4)**  
Fact:
- [Suggestion] `fitness_pen=None` の 3 経路棚卸し自体は前提検証として前進です。[conceptual-design.md:48](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L48)
- [Warning] ただし「通常実値は sentinel 帯と十分離れている」という `calibrate_gate` の分離前提は verified ではありません。[metrics.py:44](/Users/ishitoya/repository/zenigame-fx/src/backtest/metrics.py#L44)
Interpretation:
- 主鎖の前提は改善しましたが、`calibrate_gate` 側の分離前提は未検証です。

**9. Design-first (C1)**  
Fact:
- [Suggestion] `docs/alpha_factory/stage-gates.md` を本 phase に含めた点で、Round 2 Warning 9 は解消方向です。現行 SSOT に `no_exposure` が未定義であることも正しく認識しています。[stage-gates.md:111](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/stage-gates.md#L111) [conceptual-design.md:113](/Users/ishitoya/repository/zenigame-fx/devnotes/20260425-0937-risk-no-trade-fitness-guard/conceptual-design.md#L113)
Interpretation:
- docs SSOT を phase に含めた点は妥当です。

修正要求は 1 点です。`calibrate_gate` の sentinel 除外条件を `fitness_pen > _NO_EXPOSURE_FITNESS / 10` ではなく、`_SYSTEM_FAILURE_FITNESS / _NO_EXPOSURE_FITNESS / _METRIC_UNAVAILABLE_FITNESS` の**明示一致除外**に置き換えてください。これが入れば `APPROVED` です。