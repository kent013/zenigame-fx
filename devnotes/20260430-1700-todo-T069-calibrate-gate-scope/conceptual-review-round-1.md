# T069 概念設計レビュー Round 1

## 0. 本レビューの前提 (C4)
- 本レビューは、提示された T069 概念設計本文のみを根拠にしたテキストレビューである。リポジトリ内の `synthesis.md`、T058/T059/T067 の原文、git 履歴、実コードは今回の制約上独立検証していない。
- verified: 提示本文上では、T069 の狙いが「3 Run freeze」「|Δ|<=0.03」「scope key=dataset_epoch_id」「big-bang migration」を扱うこととして明示されている。
- verified: 提示本文上では、T058 が `dataset_epoch_id` 必須化と history schema v2、T067 が Emergency mode、T059 が `dataset_epoch_id` 生成を担当すると整理されている。
- verified: 提示本文上では、T069 は Phase 1 / Phase 2 に分割され、Phase 1 は library 中心、Phase 2 は script/config/docs 配線として設計されている。
- verified: 提示本文上では、`decide()` 不変、`decide_with_freeze()` 新設、`DecisionLabel` へ `skip_frozen` 追加、`threshold_delta_abs_max <= 0.03` の contract 強化が提案されている。

## 1. 結論
NEEDS_REVISION

## 2. Critical (設計の根幹を揺るがす欠陥、 必須修正)
- [C1] `scope key=dataset_epoch_id` を 4 軸へ拡大解釈している。  
  Fact: §3.2 で `scope_key = (base_config_hash, dataset_epoch_id, instrument, stage_gate_version)` と再定義し、「dataset_epoch_id は必要条件」と解釈している。  
  Interpretation: これは strict 準拠ではなく概念の拡張であり、同一 `dataset_epoch_id` 内でも `base_config_hash` や `stage_gate_version` の変化で freeze count が再スタートしうる。synthesis が「3 Run freeze を epoch 単位で課す」意図なら、意味が変わる。ここは詳細設計送りではなく、概念で「freeze を数える主キーは正確に何か」を確定すべき。
- [C2] 「3 Run freeze」を「3 history row freeze」に置き換えており、Run 単位 SSOT が崩れている。  
  Fact: §3.3/§4.1 で `epoch_run_count = len([matching records])` と定義している。  
  Interpretation: retry、二重 append、再実行、将来の backfill があると、1 Run で複数 row が積まれ freeze が早期解除される。North Star の制約は「3 Run」であり「3 record」ではない。`applied_from_run_id` などの Run 識別子を用いた distinct count を概念で固定しないと壊れる。
- [C3] `skip_frozen` の state 反映経路が本文中で自己矛盾している。  
  Fact: §6.7 では「`load_calibrated_threshold` は `skip_frozen` record を `new_threshold == prev_threshold` として返すため自然に継承される」と書かれている一方、§9 F5 では「`decision in {tighten, loosen}` filter により `skip_frozen` は load 対象外で config 値が採用される」と書かれている。  
  Interpretation: `run_ga.py` の有効 threshold source が 2 通りに分裂している。これは API SSOT と state SSOT の不整合であり、詳細設計に送ってはいけない。`skip_frozen` を state 解決に含めるのか含めないのか、概念で単一化が必要。
- [C4] big-bang を掲げながら、破壊的 contract 変更を Phase 2 に分割している。  
  Fact: §6.1 で `threshold_delta_abs_max <= 0.03` を `__post_init__` で即時 contract 化する一方、§6.3/§11 では `default.yaml` 更新を Phase 2 に送っている。  
  Interpretation: 現行 YAML が 0.03 超なら、Phase 1 単独マージで fail-closed を引く。synthesis §9.3/§12.1 が big-bang/no migration を求めるなら、validator 強化・設定更新・caller 配線は原則同一 cut で扱うべきで、2 段階分割は概念レベルで再整理が必要。

## 3. Warning (修正推奨だが概念設計でブロックしない)
- [W1] C2 parallel-path 検証の範囲が import graph に偏っている。  
  Fact: §2 は `calibrate_gate` の import 経路だけを点検している。  
  Interpretation: これでは `history.jsonl`、`DecisionLabel`、threshold state を読む下流 consumer の並列経路検証になっていない。少なくとも `alpha_sieve` / monitoring / DSR / report 系の「decision 値を読むか」「history 行数を意味解釈するか」は consumer inventory として概念に明記した方がよい。
- [W2] `skip_frozen` の転記漏れ対策が docs/log まで SSOT 化されていない。  
  Fact: §11 には docs 更新があるが、logger の必須出力項目は任意扱いに近い。  
  Interpretation: 重点項目の「転記漏れ」観点では、少なくとも `decision=skip_frozen`、`dataset_epoch_id`、`epoch_run_count`、`freeze_window`、`next_run_index_in_epoch` のログ契約は概念で固定した方が安全。
- [W3] T059 依存の fail-closed 条件が弱い。  
  Fact: §5.1 docstring では `dataset_epoch_id=None` は `ValueError` としている。  
  Interpretation: ただし caller 側で「epoch id が空なら calibrate 自体を起動しない」の運用契約までは本文で固定されていない。詳細設計で迷わないよう、概念で明文化した方がよい。

## 4. Suggestion (詳細設計で考慮)
- [S1] `FreezeStatus` は `epoch_distinct_run_count` のように名前自体で「row count ではない」ことを示した方が誤読しにくい。
- [S2] `decide_with_freeze()` は frozen 時の `new_threshold` のソースを docstring で明記した方がよい。`config.current_threshold` なのか、caller 注入の resolved threshold なのかを曖昧にしない。
- [S3] `skip_frozen` を `DecisionLabel` に入れるなら、archive/history/report での集計分類も先に名前だけは揃えておくと後続の配線漏れが減る。

## 5. Falsification-first 観察 (失敗モード追加候補)
- 同一 Run の二重 append が起きると、3 Run 未満で freeze が解除される。現設計の防御は不足している。`record count` ではなく `distinct applied_from_run_id count` が必要。
- 同一 `dataset_epoch_id` のまま `base_config_hash` が変わると、同一 epoch 内で freeze が再開する。現設計はこれを許容しており、synthesis の strict 解釈とは衝突する可能性が高い。
- `skip_frozen` の state 解決が caller によって「config を採る」「前回 threshold を継承する」に分裂する。本文内自己矛盾のため防御不能。
- Phase 1 だけ先に入ると、validator 強化で起動拒否しつつ caller 未配線のままになる可能性がある。big-bang と 2-phase の整合が未処理。
- `DecisionLabel` に `skip_frozen` を追加しても、monitoring/report 側が未知ラベルを reject する consumer があれば壊れる。本文はそこを未検証。
- `dataset_epoch_id` 欠落時に `ValueError` で止める方針はあるが、run 開始前の preflight 契約が無いと障害発見が遅れる。防御は部分的。
- `F8: 同 scope record が多数でも issue なし` という扱いは弱い。多数化の原因が duplicate append なら issue であり、反証が不十分。

## 6. 強み (継続すべき設計判断)
- `decide()` を不変に保ち、freeze を wrapper に分離する方針は妥当。責務分離が明確で、既存単体テストの破壊範囲も小さい。
- Emergency mode を T067 に切り分け、T069 を freeze/scope に限定している点は概念の境界管理としてよい。
- `|Δ|<=0.03` を config contract として fail-closed に寄せる方向性自体は、数値の暴走を防ぐ設計として筋がよい。
- F1-F9 のように失敗モードを先に列挙している姿勢は、Falsification-first と整合している。

## 7. 次 Round への申し送り (NEEDS_REVISION 時のみ)
- `scope key=dataset_epoch_id` を strict に守るのか、4 軸 composite scope に改めるのかを概念で再決定すること。後者を採るなら、synthesis との差分を「逸脱ではなく改訂」として明示する必要がある。
- freeze 判定は「history row 数」ではなく「distinct Run 数」で定義し直すこと。`applied_from_run_id` を使うのか、別の run identity を使うのかを概念で固定すること。
- `skip_frozen` が state 解決で load 対象か否かを 1 つに決め、`run_ga.py` / `load_calibrated_threshold` / docs の説明を単一 SSOT に揃えること。
- big-bang の原則に従い、validator 強化・`default.yaml` 更新・caller 配線・docs 更新の原子的適用境界を概念で確定すること。少なくとも「Phase 1 単独では merge しない」か「Phase 1 単独でも安全」のどちらかは明記が必要。
- consumer inventory を追加し、`skip_frozen` と `dataset_epoch_id` の影響先を `scripts/calibrate_gate.py` 以外にも明示すること。特に history/report/monitoring 系は概念で棚卸ししておくべき。