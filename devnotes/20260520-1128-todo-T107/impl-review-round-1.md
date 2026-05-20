**Fact（観察事実）**
- C-1: `[AuxPairMidSeries + _to_epoch_ns + loader/stream]` は実装され、`_stream_aux_pair_mid` で `ORDER BY` + `ns <= prev` による monotonic/unique fail-fast が入っています。`__post_init__` / `__setstate__` で read-only 化も実装済みです。対象: [aux_loader.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/aux_loader.py)
- C-2: `align_to` は `searchsorted(side="left")` + `raw_ts[pos]==target_ns` の exact-match 判定で、`pos==size` を `in_range` で防御し、欠番は `NaN` 伝播です。対象: [aux_loader.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/aux_loader.py)
- C-3: `EvaluationContext` / `RegistryEvaluator` は `aux_pair_bars` から `aux_pair_mid_close` へ契約交換され、`RegistryEvaluator.__setstate__` と `_freeze_aux_pair_mid` で unpickle 後 re-freeze を実装。対象: [_base.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/_base.py), [evaluator.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/evaluator.py)
- C-4: P5 は `ctx.aux_pair_mid_close` 直参照へ移行し、長さ不一致のみ fail-fast、欠番は `NaN` 伝播です。対象: [pair_specific.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/primitives/pair_specific.py)
- C-5: `AlignedAuxBundle.as_evaluator_kwargs()` は `aux_pair_mid_close` を返す実装に更新されています。対象: [aux_loader.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/aux_loader.py)
- C-6: run_ga 側は値源を `aux_pair_mid_index` へ更新済みですが、ログキー名は `aux_pair_bars_count` のままです。対象: [run_ga.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py)
- C-7: テストは golden / 境界 / pickle re-freeze / DB→align→P5 統合 / V15 fail-fast を追加済みです。対象: [test_aux_loader_align.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_aux_loader_align.py), [test_pair_specific.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/primitives/test_pair_specific.py), [test_parallel_eval.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/test_parallel_eval.py)

**Interpretation（解釈・判定）**
1. C-1: **APPROVE**  
2. C-2: **APPROVE**  
3. C-3: **APPROVE**  
4. C-4: **APPROVE**  
5. C-5: **APPROVE**  
6. C-6: **INCONCLUSIVE**（全体置換漏れの網羅確認は、このターンの制約上 grep 実査不能）  
7. C-7: **APPROVE**

[Critical] なし

[Warning] `AuxPairMidSeries` の docstring は「構築時 fail-fast 検証」を謳っていますが、`__post_init__` では monotonic/unique/dtype/length の明示検証はしていません。  
修正案: `__post_init__` に以下を追加  
- `ts_epoch_ns.dtype == int64`, `mid_close.dtype == float64`  
- 1次元・同一長  
- `np.all(np.diff(ts_epoch_ns) > 0)`（strict monotonic + unique）

[Warning] `align_to` 側ターゲット時刻が `_normalize_bar_time` されていないため、target `bar_time` に秒/マイクロ秒が含まれる入力でサイレントに `NaN` 増加する余地があります。  
修正案: `target_ns` 生成時に `_normalize_bar_time` を適用するか、秒/マイクロ秒非ゼロを fail-fast で弾く。

[Suggestion] 観測系の一貫性のため `aux_pair_bars_count` ログキーは `aux_pair_mid_count` へ改名（必要なら移行期間だけ両方出力）。

**特に確認したい点への回答**
1. `align_to` の exact-match ロジック: 実装は正しいです（空 raw / `target<first` / `pos==size` すべて `NaN` 側に倒れる）。  
2. read-only 契約: `AuxPairMidSeries.__setstate__` + `RegistryEvaluator.__setstate__` + `_freeze_aux_pair_mid` で主要 pickle/worker 経路は維持されています。  
3. P5 golden equivalence: 方針として妥当です。旧計算式と新計算式の同値性は `assert_array_equal` で押さえられています。  
4. 置換漏れ: 提示差分内の機能経路は概ね置換済み。ただし repo 全体の残存識別子は **INCONCLUSIVE**。  
5. `_to_epoch_ns` 整数経路: float 非依存で丸め誤差は入りません。  
6. CSV `build_aux_bundle`: `aux_pair_mid_index` が空でも現実装は壊れません（空のまま運用可能）。

**全体判定**
**INCONCLUSIVE**（実装品質は高く重大欠陥は未検出。ただし C-6 の全体置換漏れ網羅確認をこのターン制約下で完了できないため）