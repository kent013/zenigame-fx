**全体判定**
`CHANGES_REQUESTED`

方向性は `A'` で妥当です。`cross_pair.py` に canonical 計算責務を持ち込まず、観測ポリシーを `stage_gate.py` に残す判断は Round 1 の Critical を正しく反映しています。ただし、`CrossPairResult._shadow_sidecar_inputs` の寿命・pickle・payload 混入に未解決の Critical があります。

**本分析の前提**
- C1: `docs/alpha_factory/stage-gates.md:174`、`docs/alpha_factory/swim-lane.md:72`、step 1.5/1.6/1.7 devnotes、`git log -S` を確認済みです。
- C4: `cross_pair.py` の `_run_pair_sharpe` caller、`stage_gate.py` の `CrossPairResult`、`parallel_eval.py` の返却経路、`archive.py` の抽出経路を確認済みです。
- C3/C7: 今回は相関分析ではないため collider/sample-size claim は行っていません。

**Critical**
- [Critical] `_shadow_sidecar_inputs` は `del sidecar_map` だけでは破棄されません。  
Facts: `evaluate_stage_c` は `cp_result` を `cross_pair_payload["result"]` に格納します。`parallel_eval.evaluate_genome` はその `stage_c` と `_extract_cross_pair_result(c_result)` の結果を `GenomeStageResult` として返します。該当経路は `src/alpha_factory/stage_gate.py:1548`、`src/alpha_factory/stage_gate.py:1555`、`src/alpha_factory/parallel_eval.py:372`、`src/alpha_factory/parallel_eval.py:378` です。  
Interpretation: sidecar を `CrossPairResult` field に載せると、canonical log 後も StageResult payload 内に残ります。これは「ephemeral」「archive/payload に流れない」「memory short-lived peak」という設計主張に反します。  
修正提案: canonical log 後、StageResult を作る前に `cross_pair_payload["result"] = replace(cp_result, _shadow_sidecar_inputs={})` のように sanitized `CrossPairResult` へ差し替えてください。Acceptance E1/E2 は「payload に key がない」だけでなく「payload 内 `CrossPairResult._shadow_sidecar_inputs` が空」を検証対象にしてください。

- [Critical] `MappingProxyType({})` default は multiprocessing 経路を壊す可能性が高いです。  
Facts: `parallel_eval` は worker pool 使用時に `self._pool.map(...)` で `GenomeStageResult` を親プロセスへ返します。該当箇所は `src/alpha_factory/parallel_eval.py:625` です。`uv run python` で確認したところ、`pickle.dumps(MappingProxyType({}))` は `TypeError: cannot pickle 'mappingproxy' object` でした。  
Interpretation: `CrossPairResult` に `MappingProxyType({})` を default field として追加すると、空 sidecar の skipped 経路でも pickling 失敗リスクがあります。これは実装後に並列評価全体を止める Critical です。  
修正提案: default は `field(default_factory=dict, repr=False, compare=False)` か、pickle 可能な `tuple[tuple[str, ...], ...] = ()` 系にしてください。immutability が必要なら、payload 返却前の sanitize と shallow copy で担保する方が安全です。

- [Critical] `_PairSidecarInputs` を `cross_pair.py` に定義し、`CrossPairResult` の型として `stage_gate.py` から参照する設計は循環依存を誘発します。  
Facts: 現状 `cross_pair.py` は `CrossPairResult` を `src.alpha_factory.stage_gate` から import しています。該当箇所は `src/alpha_factory/cross_pair.py:36` です。  
Interpretation: `stage_gate.py` 側の dataclass field に `cross_pair.py` 定義の `_PairSidecarInputs` を通常 import で使うと循環 import になります。`from __future__ import annotations` で実行時回避はできますが、責務境界として脆いです。  
修正提案: sidecar dataclass は `stage_gate.py` の `CrossPairResult` 近傍に定義し、`cross_pair.py` が `CrossPairResult` と一緒に import する形にしてください。あるいは `CrossPairResult` field は `Mapping[str, object]` にして、`stage_gate.py` 側で Protocol/duck typing に留めてください。

**Warning**
- [Warning] 「参照保持のみ」の記述は現行コードと完全には一致しません。  
Facts: `evaluate_cross_pair` は `_run_pair_sharpe` に `bars=list(pair_bars[pair])` を渡しています。該当箇所は `src/alpha_factory/cross_pair.py:276` です。さらに `parallel_eval` でも `pair_bars_map` を list 化しています。該当箇所は `src/alpha_factory/parallel_eval.py:351` です。  
Interpretation: deep copy ではないため大きな問題ではありませんが、「cp_inputs の参照そのもの」とは言い切れません。メモリ見積りの前提は少し弱まります。  
修正提案: 設計文は「deep copy なし、list は既存経路の shallow copy を許容」に修正してください。B2 実測 merge 条件は維持でよいです。

- [Warning] `repr` / equality に sidecar が混ざると snapshot 比較が不安定になります。  
Facts: dataclass field は明示しない限り `repr` と `compare` に含まれます。  
Interpretation: ephemeral field が `CrossPairResult` の表示・等価性に混ざると、既存テストや deep snapshot のノイズになります。  
修正提案: `_shadow_sidecar_inputs` は `field(default_factory=dict, repr=False, compare=False)` を指定してください。

**Suggestion**
- [Suggestion] `pair_label` を実 pair 名にする判断は妥当です。  
Facts: 後段集計は `(genome, pair)` join を想定しています。  
Interpretation: `target/anchor1/anchor2` より `EUR_USD` のような実 pair 名の方が run 横断で安定します。  
修正提案: 役割識別を log に出さない方針で進めてよいです。ただし将来 target/anchor role 分析が必要になった場合は、dual-path log ではなく Stage C payload 側の `target_pair` / `anchor_pairs` と join する前提を明記してください。

**方向性判断**
- `A'` は採用方向でよいです。
- ただし現行 Round 2 のままでは、sidecar が payload/IPC に残るため `APPROVED` にはできません。
- Round 3 では「log 後に sanitized `CrossPairResult` へ差し替える」「`MappingProxyType` を使わない」「sidecar 型の循環依存を避ける」の 3 点を反映すれば、概念設計として承認可能です。