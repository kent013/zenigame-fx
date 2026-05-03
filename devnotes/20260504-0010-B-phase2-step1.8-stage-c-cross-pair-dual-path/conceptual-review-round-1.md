**本分析の前提**
- 提示された設計文のみを根拠にしたレビューです。`docs/alpha_factory/`、`devnotes/`、`git log`、実コードの独立検証は、この round では実施していません。
- したがって本文中の「Verified」は「提示文書内でそう整理されている事実」として扱います。Round 2 の詳細設計承認では独立検証が必須です。
- C9 に従い、まず「案 A は採用すべきでない」根拠から評価します。

**全体判定**

`CHANGES_REQUESTED`

方向性そのものは `B` / `C` より `A` 系が妥当です。ただし、提示された **案 A の切り方のまま** は勧めません。推奨は **他案 = A'** です。

A' の要点:
- `cross_pair.py` は **per-pair sidecar input を保持して返すだけ**
- canonical 計算と dual-path log は **stage_gate.py 側で実行**
- つまり「cross_pair を少しだけ開ける」が、「canonical 判定ロジックを cross_pair に持ち込まない」

**各観点**

- [Critical] 案 A は `cross_pair.py` に canonical 計算責務まで持ち込みすぎです。  
  Facts: 案 A は `cross_pair.py` から canonical helper を直接呼び、`CrossPairConfig` に `dual_path_enabled` / `live_criteria` / `window_days` を追加する設計です。  
  Interpretation: これは cross-pair 評価器が Stage C の shadow 観測ポリシーまで知る形で、責務境界が悪いです。mission に必要なのは「per-pair backtest 結果を失わないこと」であり、「cross_pair 内で canonical を計算すること」ではありません。設計上の切れ目が一段深すぎます。  
  修正提案: `cross_pair.py` は `bars/trades/equity_curve/bt` の sidecar を返すだけに留め、canonical 計算と `_log_canonical_dual_path(...)` 呼び出しは `stage_gate.py` で行ってください。

- [Critical] `CrossPairConfig` への dual-path 用 field 追加は、今回の目的に対して伝搬面が広すぎます。  
  Facts: 提案では `parallel_eval.py` / `swim_lane.py` / `CrossPairConfig` / `cross_pair.py` に dual-path 用情報を流します。  
  Interpretation: これは今回もっとも避けるべき「値の転記漏れ・伝搬漏れ」面を増やします。しかも追加される値は cross-pair の本来の pass/fail には不要で、観測専用です。  
  修正提案: `CrossPairConfig` には dual-path 用 field を入れないでください。Stage C caller が保持する既存の `live_criteria` / `window_days` を、そのまま `stage_gate.py` 側の shadow 計算に使う方が安全です。

- [Warning] `metrics["canonical_per_pair"]` / `metrics["legacy_per_pair"]` を公開的な `metrics` 空間に混ぜるのは境界が弱いです。  
  Facts: 提案は `CrossPairResult.metrics` に sidecar を格納し、archive には載せない前提です。  
  Interpretation: `metrics` は事業的な評価値の空間に見えるため、ephemeral な shadow object を混ぜると downstream の誤使用や serialize 漏れを誘発します。  
  修正提案: どうしても `metrics` を transport に使うなら、`_shadow_dual_path` のような予約 namespace に隔離し、`payload` / archive へ絶対に流れないことをテストで固定してください。

- [Warning] メモリ見積りは blocker ではないものの、まだ「低リスク仮説」です。  
  Facts: 提案は 3 pair 分の `trades/equity_curve` の短時間保持を想定し、概算で worker 3GB を下回るとしています。  
  Interpretation: 大勢としては妥当です。ただし安全性の根拠はまだ実測前提で、Round 1 では「問題ない」と断定できません。  
  修正提案: B2 を merge 条件に格上げしてください。加えて、保持するのはコピーではなく参照であること、canonical 計算後に sidecar を即時破棄することを詳細設計で明文化すべきです。

- [Warning] C1/C4 はこの round では未充足です。  
  Facts: 本レビューは提示文のみで、参照 docs/devnotes/git を独立検証していません。  
  Interpretation: 方向性判断 round としては進められますが、詳細設計 approval の根拠としては不足です。  
  修正提案: Round 2 では少なくとも「`CrossPairResult.metrics` がどこまで payload/archive に流れるか」「`_run_pair_sharpe` の caller 全件」「`cp_inputs` 構築経路」を抜粋で提示してください。

- [Suggestion] `pair_label` 追加は妥当です。`fold_index` 流用案 A2 は却下でよいです。  
  Facts: `B_fold` の `fold_index` は fold 識別子であり、cross-pair の pair 識別とは意味が異なります。  
  Interpretation: `pair_label` 追加は step 1.6 の拡張と同型の backward-compatible 拡張です。一方 A2 は SSOT を汚します。  
  修正提案: A3 を採用し、`stage_label="C_cross_pair"` では `pair_label` 必須 fail-fast にしてください。

- [Suggestion] `pair_label` には役割名ではなく実 pair 名を使うべきです。  
  Facts: 後段集計は `(genome, pair)` join を想定しています。  
  Interpretation: `target/anchor1/anchor2` より `EUR_USD` のような実 pair 名の方が、run 横断・target 横断の集計でぶれません。  
  修正提案: `pair_label` は実 pair 名を正とし、必要なら role は別 field にしてください。

**案の方向性判断**

推奨案は **他案 = A'** です。  
「A/B/C の三択だけ」で答えるなら **A** ですが、**現行の案 A のままではなく、上記 2 つの Critical を反映した A に限定**です。

Facts:
- `B` は target pair しか観測せず、ii-lite の集約判定を構成する anchor 側の constituent observability を欠きます。
- `C` は canonical 観測を完成させず、mission 必須軸の observability 完成という step 1.8 の目的に届きません。
- per-pair の `trades/equity_curve/bt` を捨てない変更は、少なくとも `cross_pair.py` 側に必要です。

Interpretation:
- したがって、mission 整合で見ると `B` と `C` は弱すぎます。
- ただし「cross_pair を少し改修する必要がある」ことと、「cross_pair の中で canonical まで計算する」ことは別です。
- 最適な切り方は、**cross_pair では sidecar 保持まで、canonical 計算は stage_gate** です。これが観測価値・改修規模・依存方向・伝搬漏れリスクのバランスが最も良いです。

**結論**

案 A の問題は「方向」ではなく「切り込み位置」です。  
step 1.8 は **A' で進める**べきです。Round 2 では次の 3 点を固定するとよいです。

1. `cross_pair.py` は per-pair sidecar を返すだけ  
2. canonical 計算と log emit は `stage_gate.py` に残す  
3. `pair_label` を新設し、`C_cross_pair` で必須 fail-fast にする

この修正が入るなら、私は方向性として承認に寄せます。