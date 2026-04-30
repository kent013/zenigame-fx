**前提**
- `verified`: レビュー対象には 2 件の独立した概念設計が含まれています。1 件目は「composite per-bar 計算の Numba JIT 化」、2 件目は「negative equity 再発の根本修正」です。
- `verified`: 根拠として使える情報は、この会話に埋め込まれた設計文書・コード抜粋・profile 抜粋・設定抜粋のみです。追加のファイル読解はしていません。
- `verified`: 1 件目は `src/dsl/composite.py` / `src/dsl/strategy.py` / cProfile 抜粋 / `default.yaml` 抜粋が提示されています。
- `verified`: 2 件目は `src/broker/mock.py` / `src/backtest/engine.py` / config 抜粋 / OANDA spec 要約が提示されています。
- `unverified`: 1 件目で言及される zenigame 側の高速化実績値、Numba 0.61+ の Python 3.13 実運用安定性、worker 並列時の cache 挙動は、この入力だけでは検証不能です。
- `unverified`: 2 件目で言及される run-25 実ログ、commit `a255338`、T049/T053-T055 の実コード差分は、この入力だけでは検証不能です。
- `unverified`: 1 件目の `stage_gate.evaluate_stage_a` が profile dataset 14 日全体をそのまま backtest しているのか、内部で 60 日 window を別解釈しているのかは、抜粋だけでは確定できません。
- `unverified`: 2 件目の `Decimal('NaN')` や `Infinity` が broker 内に流入し得るかは、抜粋だけでは確定できません。

**全体判定**
- 1 件目「Numba JIT 化」: **Warning**
- 2 件目「negative equity 修正」: **Warning**

**Fact**
- 1 件目では、`[strategy.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py)` の prepared path が per-bar で `dict` を構築し、`[composite.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/composite.py)` の pure Python 関数を多重呼び出ししています。
- 1 件目の cProfile 抜粋では、`strategy.py:on_bar` cumtime 1.165s、`compute_clause_score` 0.402s、`compute_composite` 0.379s、`compute_dir_score` 0.251s です。
- 2 件目では、`[mock.py](/Users/ishitoya/repository/zenigame-fx/src/broker/mock.py)` の `fill_pending` が `pre_fill_equity` を取得するだけで open 系 signal を通し、`_open_position` でも余力 gate をしていません。
- 2 件目では、`[engine.py](/Users/ishitoya/repository/zenigame-fx/src/backtest/engine.py)` の bar loop が `fill_pending -> mark_to_market -> force_close_if_margin_call -> strategy.on_bar` の順です。

**Interpretation**
- 1 件目は、ボトルネック候補として composite 経路を疑う方向自体は妥当ですが、設計文書の外挿と高速化期待値にはまだ反証余地があります。
- 2 件目は、negative equity 再発経路の主仮説はかなり強いですが、`fill_pending` のみで閉じる設計だと fail-closed の境界条件に弱さが残ります。

## 1 件目: composite per-bar 計算の Numba JIT 化

### [Warning] Stage A 外挿の `bars_scale_a = 60d / 14d = 4.29x` は、この入力だけでは成立していません
- 反証:
  - `default.yaml` では dataset は約 6 ヶ月で `stage_a.window_days: 60` です。
  - しかし profile 実行は CLI で `2026-03-01` から `2026-03-15` の 14 日に絞っています。
  - `run_backtest` が「与えられた 14 日 dataset 全体」をそのまま回しただけなら、Stage A は実質 14 日運転であり、4.29x 外挿は仮説に留まります。
  - `stage_gate.py:evaluate_stage_a` の抜粋がないので、60 日 window の内部適用有無を確認できません。
- 修正提案:
  - 設計書の外挿を「`unverified`」に格下げしてください。
  - 少なくとも次のどちらかを先に実測してください。
    1. 実 dataset 60 日固定で同条件 cProfile を再取得する
    2. `evaluate_stage_a` が `run_backtest` に渡す bars 長をログまたは unit test で確定する

### [Warning] `on_bar 1.165s - composite 系 tottime 0.473s = 残差 0.69s` をそのまま dict/hash overhead とみなすのは強すぎます
- 反証:
  - 比較しているのは `on_bar` の `cumtime` と composite 関数群の `tottime` で、軸が一致していません。
  - `compute_clause_score` は内部で `compute_dir_score` を呼ぶので、単純合算も二重計上を含みます。
  - `on_bar` には dict 構築以外に warmup 判定、prepared/unprepared 分岐、active clause 集計、後段ロジックの一部も乗っています。
- 修正提案:
  - 「dict allocation / Python loop overhead が主要因」は仮説として残し、断定を避けてください。
  - line profiler か py-spy で `[strategy.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/strategy.py)` prepared path の以下を分離計測してください。
    - `vals` 構築
    - `compute_composite`
    - active_clause 集計ループ

### [Warning] `fastmath=False` でも「bit-identical」は過剰主張です
- 反証:
  - Numba の `njit` は Python `float` と同じ IEEE 754 を使っても、生成コード・型昇格・ループ最適化の都合で厳密な bit-identical まで保証しません。
  - 設計書自身も later section で `np.allclose(atol=1e-6, rtol=0)` を使っており、bit-identical と整合していません。
  - `math.isfinite` と Numba 側の `np.isfinite`/`math.isfinite` は通常同等ですが、実装差の検証は別です。
- 修正提案:
  - 受入基準を `bit-identical` ではなく「pure Python baseline に対して `allclose(atol=1e-6, rtol=0)`」へ統一してください。
  - archive diff も同じ許容差で定義し直してください。

### [Warning] `active_clause_indices` の semantics は kernel 化で再現可能だが、比較演算の境界を明文化しないとズレます
- 反証:
  - 現実の契約は「`compute_clause_score(clause, vals) != 0.0` が 1 度でも起きた clause」です。
  - kernel 側で `abs(score) > eps` に変えると semantics が変わります。
  - gate に 0 を含む場合や正負が打ち消し合う場合、純 Python と完全同一比較でないとズレます。
- 修正提案:
  - 設計書に「active 判定は `score != 0.0` の厳密比較を維持する」と明記してください。
  - pure Python 実装と kernel 実装で `active_clause_indices` の一致を別テスト項目として追加してください。

### [Suggestion] Stage B/C への「線形に効く」は弱い表現に落とした方がよいです
- 根拠:
  - 同じ `engine.run_backtest -> strategy.on_bar` 経路を通る点は事実です。
  - ただし Stage B/C では bars 数、trade 密度、broker 側比率、metrics 比率が変わるので、run 全体への寄与は線形とは限りません。
- 修正提案:
  - 「`on_bar` 成分には同方向に効く可能性が高い。ただし stage 全体の短縮率は再プロファイルで確認」と書き換えるのが妥当です。

### [Suggestion] メモリ見積りは signal 配列の共有前提を明示した方がよいです
- 根拠:
  - `PreparedSignals.arrays` は `(name, params)` 単位で共有 cache を持っています。
  - 設計書の `dir_value_arrs[total_dir, n_bars]` は「flat 化後に clause ごと複製しない」前提なら妥当ですが、実装を誤ると共有が消えて見積りが崩れます。
- 修正提案:
  - `dir_value_arrs` / `gate_value_arrs` は「shared precomputed arrays への index table」で持つのか、「実データを再配置した dense matrix」で持つのかを詳細設計で確定してください。
  - 後者なら Stage B 30MB/genome は過小見積りになる可能性があります。

## 2 件目: negative equity 再発の根本修正

### [Warning] `fill_pending` だけに gate を置く設計は、防御層として 1 段薄いです
- 反証:
  - 主要経路が `fill_pending -> _open_position` なのは抜粋上その通りです。
  - ただし将来 `_open_position` を別経路から呼ぶ実装が入ると、fail-closed が壊れます。
  - broker の物理制約は最終到達点でも守る方が設計として強いです。
- 修正提案:
  - 主ゲートは `fill_pending` でよいですが、`_open_position` にも defensive check を追加してください。
  - 具体的には `equity_at_entry <= 0` または非有限なら `ValueError` ではなく open 拒否の internal no-op / domain-specific exception にして、`fill_pending` で握る形が安全です。

### [Warning] `equity <= 0` 判定だけでは非有限値を安全に閉じ切れていません
- 反証:
  - `Decimal('NaN') <= 0` は `InvalidOperation` を起こし得ます。
  - `Decimal('Infinity')` は `<= 0` で false ですが、Infinity を正常扱いにしてよいとは限りません。
- 修正提案:
  - gate 条件を「`equity.is_finite() and equity > 0` のときのみ open 許可」にしてください。
  - それ以外は fail-closed で drop する方が broker 制約として一貫しています。

### [Warning] `fill_pending` 冒頭 gate は「その bar の open 約定前 snapshot」を基準にするので、同 bar の close signal と競合すると conservative に過ぎる場合があります
- 反証:
  - 現行 loop では `fill_pending` が strategy の close signal より先に動くため、その bar で recovery する close はまだ pending にありません。
  - したがって「equity 復活直前」の open を落とす可能性はあります。
  - ただしこれは fail-closed としては許容されやすいです。
- 修正提案:
  - 設計書に「同 bar 内 recovery を取り逃がす conservative policy を意図的に採用」と明記してください。
  - そうでないなら loop 順序そのものの再設計が必要です。

### [Suggestion] `maintenance_margin_level_pct` の config 化は本件の本質ではなく、別 TODO に切った方がよいです
- 根拠:
  - negative equity 再発の根本因は open gate 欠如であり、maintenance threshold config 化は独立変更です。
  - 1 PR/1 TODO に混ぜると検証面が広がります。
- 修正提案:
  - 今回は open gate と counter 追加に集中し、config 化は follow-up に分離する方がレビューしやすいです。

### [Suggestion] counter accessor 案は妥当ですが、「いつリセットされるか」を契約化してください
- 根拠:
  - engine 側は per-backtest 集計を想定しています。
  - accessor が累積型だと複数 backtest や再利用時に混線します。
- 修正提案:
  - `pop_negative_equity_drop_count()` のように pop semantics にするか、`fill_pending` ごとの drop 件数を broker 内部で前回分だけ返す契約にしてください。

## 論点別の判定

1. `bars_scale_a = 4.29x` の妥当性
- **結論: unverified**
- 14 日 profile が実質 14 日 Stage A なら 4.29x は仮説止まりです。60 日 bars 実測か `evaluate_stage_a` の実引数確認が必要です。

2. `on_bar` と composite 系の差分 0.69s の解釈
- **結論: unverified**
- dict/hash overhead の可能性は高いですが、cumtime/tottime 混在なのでこの差分をそのまま削減余地とは言えません。

3. Numba 導入の隠れコスト
- **結論: unverified**
- 初回 compile、worker ごとの import、cache 共有、Python 3.13 互換はすべて実測要です。設計段階で断定しない方がよいです。

4. 数値同値性
- **結論: 部分的に否定**
- `fastmath=False` は良いですが、bit-identical 主張は下げるべきです。`allclose` ベースで十分です。

5. T037 `active_clause_indices`
- **結論: verified ではないが再現可能**
- ただし `!= 0.0` を厳密維持すること、epsilon 判定に変えないことが条件です。

6. Stage B/C INCONCLUSIVE の妥当性
- **結論: 妥当**
- 「同じ engine 経路を共有するため、少なくとも `on_bar` 成分には効く」は言えますが、stage 全体への線形外挿は弱めるべきです。

7. メモリ概算
- **結論: unverified**
- shared array 前提なら概ねあり得る数字ですが、flat 化で複製が入る実装だと崩れます。

## まとめ
- 1 件目の Numba 設計は方向性自体は妥当ですが、**外挿根拠と bit-identical 主張が強すぎる**ため、そのままでは Warning です。実測で 60 日 profile を取り直し、受入基準を `allclose` に揃えるべきです。
- 2 件目の negative equity 修正は主原因の仮説が強く、`fill_pending` gate は有効です。ただし **非有限値の fail-closed と `_open_position` 側の最終防御**を足さないと設計として薄いです。