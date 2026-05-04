**結論**
Run-29 の打ち手は **案 C を MODIFY 採用** が最も妥当です。  
ただし「GA 全体の評価式をいじる」ではなく、**elite / archive / winner 伝搬経路に `feasibility=True` を要求する最小変更**に限定します。

**前提**
- Verified: `min_exposure_trade_count >= live_criteria.trade_count_min` は T034 ガードで明示禁止。
- Verified: T034 の意図は「Stage A が live_criteria 相当の trade_count gate になること」を防ぐこと。
- Verified: Run-28 best は `trade_count=48` で mission 基準未達。
- Unverified: infeasible 個体が elite 経由で保存・伝搬されたかは、実コード・ログ確認が必要。

**Q1: 案 A-F 判定**
- **案 A `1 -> 49`: REJECT**。strict less を満たすだけのガード回避で、Structural ではなく Reactive Parametric 寄り。T034 の精神にも反する。
- **案 B ガード緩和: REJECT**。明示 invariant を壊すため、cycle 2 の「単一変更」範囲を超える。
- **案 C elite を feasibility=True のみに制限: MODIFY 採用**。既存 `ga.feasibility.entry_count_min=50` の意味を elite/保存経路にも通す構造修正。
- **案 D fold 整合で Stage A `>=60`: REJECT**。T034 が禁止した「Stage A trade_count gate 化」をさらに強める。
- **案 E trade_density 追加: DEFER**。構造案としてはあり得るが、新 threshold 導入で複雑化し、今回の単一変更原則に反する。
- **案 F no-op rerun: REJECT as improvement**。control run としての情報価値はあるが、Run-29 改善策ではない。

**Run-29 採用案**
- **classification**: Structural
- **target_metric**: elite / archive / winner に `trade_count < live_criteria.trade_count_min` 個体が残らないこと
- **failure_mode**: selection_score 上は infeasible 扱いでも、elite 保存経路が infeasible 個体を温存する
- **causal_path**: infeasible elite が残る -> 次世代探索・best選出・archive が infeasible 近傍に寄る -> live_criteria 充足個体に到達しにくい
- **falsification**: 変更前ログで infeasible elite が存在しないなら案 C の主因仮説は棄却
- **falsification**: 変更後も archive/winner に infeasible 個体が残るなら、別の伝搬経路漏れ
- **falsification**: feasible 個体だけになっても Stage B が Sharpe 不足支配なら、次は signal 品質仮説へ移行
- **success_criterion**: elite / archive / final best が全て `feasibility=True`
- **success_criterion**: best 個体が `trade_count >= 50`
- **success_criterion**: Stage B 失敗理由が trade_count 不足から Sharpe / signal 品質側へ移る

**Q2: 案 C の波及範囲**
案 C は実装点を誤ると大きいです。  
`operators` や `nsga2` の評価式そのものを変えるなら大変更ですが、**elite 抽出・archive 追加・winner 選出の acceptance guard** に限定すれば小さな構造修正です。

避けるべき範囲:
- GA objective の重み変更
- mutation / crossover の変更
- Stage A threshold 変更
- Stage B 判定式変更

狙うべき範囲:
- elite candidate 採用前に `feasibility=True` を要求
- archive 追加前に `feasibility=True` を要求
- final best / winner 出力前に `feasibility=True` を要求
- infeasible しか存在しない場合は fail-closed または明示ログで INCONCLUSIVE

**Q3: no-op Run-29 の情報量**
情報量は限定的です。  
確率揺らぎ・calibrate-gate の再確認には使えますが、因果介入がないため「何が改善/悪化させたか」は学べません。やるなら **Run-29 改善 run ではなく control rerun** と明示すべきです。

**Q4: T034 ガードを破れる条件**
今回破るべきではありません。  
許容されるのは「回避」ではなく「設計置換」として扱える場合だけです。

必要条件:
- T034 の前提、つまり Stage A と live_criteria の評価期間非対称が現在も妥当か検証済み
- Stage A fast screen の役割を壊さない代替 invariant が設計済み
- live_criteria 緩和ではなく、mission 基準を強める/整合させるだけだと説明可能
- 変更前に devnotes で設計更新し、既存ガードを削除ではなく置換する
- 反証条件と rollback 条件が事前登録済み

**最終判断**
Run-29 は **案 C: feasibility=True の elite/archive/winner 伝搬ガード** に絞るべきです。  
`min_exposure_trade_count` は触らない、T034 ガードも触らない。今回の仮説は「low-trade を Stage A で落とす」ではなく、**mission-infeasible 個体を GA の保存経路で温存しない**に修正します。