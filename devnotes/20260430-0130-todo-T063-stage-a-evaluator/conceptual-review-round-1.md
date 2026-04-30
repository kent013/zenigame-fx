[VERDICT] **REVISE REQUIRED**

Round 1 の結論は「実装着手前に 4 点を確定すべき」です。特に `T061 出力を消費するだけの T063` という契約と、`T063 側で Stage A 用 threshold を派生する` という記述が両立していません。ここを曖昧にしたまま進むと、trade_rate / net_pnl の解釈差がそのまま実装差になります。  
前提: このレビューは、貼付本文とそこで明示された引用先名 (`synthesis §5.1 / §5.5 / §8.7 / §17 / §19 #4`, zenigame `stage_a_gate.py`) のみを根拠にしています。原文未照合の箇所は **要確認** とします。

[Critical]

- **T061 依存契約と `StageAThresholds` 派生責務が衝突しています。**  
  Fact: 貼付本文では `evaluate_generation(canonical_five_results: list[CanonicalFiveResult])` を T063 の入力契約としつつ、別箇所では「T063 が `StageAThresholds` を構築して T061 に渡す」と書いています。`CanonicalFiveResult` はすでに threshold 適用後の結果なので、T063 が後から 8w 比例 threshold を差し替えることはできません。  
  Interpretation: 現設計のままだと、`trade_count は trade_rate で評価` の実装責務が宙に浮きます。解決策は 2 択です。  
  1. T063 は「T061 実行前の threshold 派生器 + controller」まで責務を持ち、入力契約を `CanonicalFiveResult list` だけにしない。  
  2. threshold 派生は T065 側 orchestrator の責務に寄せ、T063 は「渡された `CanonicalFiveResult` を ranking するだけ」に縮退する。  
  引用: 貼付本文「設計方針」「Module 構造」「Stage A 用 thresholds の派生」「重要な設計判断 1, 2」、synthesis §5.1。

- **`divergence_cycle_count` の signed semantic と更新式が整合していません。**  
  Fact: state 定義では「正=乖離中 / 負=回復中 / 0=正常」とあります。一方 `compute_q_force_with_divergence()` は `max(0, divergence_cycle_count)` なので負値を全て 0 扱いします。さらに `update_a_b_divergence()` は `corr>=0.5` で `divergence_cycle_count -= 1 (min 0 で停止)` とあり、これだと負値状態は到達不能です。  
  Interpretation: 現設計では「0.02/Run で戻す」という §8.7 の意味を実装できません。signed counter は捨てて、`q_force_offset_steps: int >= 0` を直接 state に持ち、`corr<0.5` で `+1`、`corr>=0.5` で `-1`、`0..cap` に clamp する方が一貫します。  
  引用: 貼付本文「q_force 動的計算」「Controller class (state-ful)」「想定 Round 2 以降の論点 3」、synthesis §8.7。

- **immutable state 方針と controller API が矛盾しています。**  
  Fact: 「state は immutable dataclass」と明記されていますが、`StageAGateController` は `state` を内包し、`update_a_b_divergence(corr) -> None` で更新する設計です。さらに前半では `StageAResult` に `updated_state` を含めると書き、後半の出力契約では消えています。  
  Interpretation: 「controller が内部 state を破壊的更新する」のか、「常に新 state / 新 controller を返す」のかが未確定です。ここは API の根幹です。今のままではテストも integration も固定できません。  
  引用: 貼付本文「設計方針」「Module 構造」「Controller class (state-ful)」「出力契約」「制約・前提」。

- **`net_pnl_min` を未確定のまま `worst_gap` ranking に流すのは危険です。**  
  Fact: 貼付本文自身が「`net_pnl_min` の window-aware は議論余地、Round 1 で確認」としています。一方で Stage A ranking は `gate_score = 1 / (1 + worst_gap)` で、worst gap の支配軸がそのまま選抜軸になります。  
  Interpretation: 24m baseline の `total_pnl_min=50000` を 8w proxy にそのまま入れると、`worst_gap` がほぼ常に PnL 軸に支配され、Stage A が「canonical 5 の近接度」ではなく「短期 PnL 未達量ランキング」に寄るリスクがあります。逆に比例縮小すると mission stringency を弱めます。これは **C8: INCONCLUSIVE** ですが、未確定のまま T061/T063 契約を凍結すべきではありません。  
  引用: 貼付本文「Stage A 用 thresholds の派生」「想定 Round 2 以降の論点 2」、synthesis §5.1。**要確認**

[Warning]

- **`trade_rate` の定義がまだ仕様になっていません。**  
  Fact: 現案は `window_ratio = 56 / 730` による count 比例です。ユーザー論点にも `8/104` と `trades/day` / `trades/week` の代替解釈が挙がっています。  
  Interpretation: `trade_rate` は「何で割るか」を決めないと仕様になりません。calendar day、tradable day、bar count のどれかを明示しない限り、同じ “rate” でも別実装になります。  
  引用: 貼付本文「Stage A 用 thresholds の派生」「想定 Round 2 以降の論点 1」、synthesis §5.1。**要確認**

- **`trade_count_max_window` に `ceil` を使うのは上限制約としてやや不自然です。**  
  Fact: 最小値・最大値の両方に `ceil` を使う提案です。  
  Interpretation: 下限は `ceil` で良いですが、上限は `floor` か、そもそも rate 比較を直接行う方が筋が通ります。ここは軽微ですが、仕様意図を明文化した方がよいです。  
  引用: 貼付本文「Stage A 用 thresholds の派生」。

- **`top q_force%` の N 算出規則が未定義です。**  
  Fact: `select_top_q_force(scores, q_force)` はありますが、`ceil` / `floor` / `round` / `min 1` の定義が書かれていません。  
  Interpretation: `n_hard_pass` が少ない世代で挙動が変わるため、ここは deterministic に固定すべきです。  
  引用: 貼付本文「Helpers」「Controller class」、synthesis §5.1。**要確認**

- **`StageAResult` が `a_pass_indices` のみだと、下流での default-deny を強制できません。**  
  Fact: 「A-fail 完全排除は T065 責務」とし、T063 は pass 集合のみ返す設計です。  
  Interpretation: 責務分離自体は妥当ですが、下流が “not in pass set means excluded” を厳密に実装しないと漏れます。`a_fail_indices` を返さなくてもよいですが、契約文に「T063 出力を使う consumer は pass 集合以外を既定で棄却する」と明記した方が安全です。  
  引用: 貼付本文「重要な設計判断 5」「Phase 2 申し送り」、synthesis §5.5。

- **`threshold_score` は `float` 固定だと空集合ケースを表現できません。**  
  Fact: `n_selected=0` または `n_hard_pass=0` の場合、cutoff は定義不能です。  
  Interpretation: `float | None` にしておく方が契約として自然です。  
  引用: 貼付本文「出力契約」。

[Suggestion]

- **state は signed counter ではなく、`divergence_offset_steps: int` に単純化した方がよいです。**  
  これなら §8.7 の「+0.02/Run、corr>=0.5 で戻す、上限 0.40」をそのまま表現できます。`last_a_b_correlation` は別 field で十分です。  
  引用: 貼付本文「Controller class」「想定 Round 2 以降の論点 3」、synthesis §8.7。

- **T063 の責務を 2 つに割ると設計が締まります。**  
  1. `derive_stage_a_thresholds(...)` は orchestration 側。  
  2. `StageAGateController.evaluate_generation(...)` は「hard floor + ranking + q_force state」のみ。  
  こうすると T061/T063 境界が明確になります。  
  引用: 貼付本文「重要な設計判断 1, 2」「Phase 2 申し送り」。

- **未確定論点は設計本文に “Decision Pending” として明示した方がよいです。**  
  対象は `trade_rate denominator`、`net_pnl_min window-aware`、`top-N rounding` の 3 点です。Round 2 でここだけ潰せば、概念設計はかなり安定します。  
  引用: 貼付本文「想定 Round 2 以降の論点 1-3」。

補足です。  
`世代内 ranking 採用`、`A→B corr 計算責務を外に置く`、`T063 は Phase 1 で既存経路に touch しない` の 3 点は、現時点では妥当です。ここに強い反証は見当たりません。  
一方で、Round 1 で潰すべき本丸は `threshold を誰が決めるか` と `divergence state をどう表現するか` です。ここが固まれば、残りは実装詳細に落とせます。