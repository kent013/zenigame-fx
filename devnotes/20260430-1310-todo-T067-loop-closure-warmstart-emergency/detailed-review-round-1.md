[VERDICT]  
**CHANGES_REQUESTED**

[Critical]  
1. Emergency時カウントのSSOT不整合（実装骨子 vs テスト計画）  
Fact: [loop_closure.py](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/ga/loop_closure.py) では `WARMSTART_EMERGENCY_SHARE=0.25` かつ `CA_RATIO=0.5`。  
Fact: [test_loop_closure.py](/Users/ishitoya/repository/zenigame-fx/tests/alpha_factory/ga/test_loop_closure.py) 計画に `test_compute_warmstart_counts_emergency_returns_19_19_for_pop192` がある。  
Interpretation: `pop=192` なら emergency は `total=48, ca=24, da=24` が整合。`19/19` は仕様矛盾。  
Required fix: テスト名/期待値を 25%仕様に一致させる（または仕様側を変更するなら synthesis/概念/詳細を同時更新）。

2. `update_warmstart_state` の順序非決定性（Determinism要件違反リスク）  
Fact: `selected_ids = set(...)` をそのまま走査して新規 record を append している。  
Interpretation: set走査順はプロセス間で不安定になり得るため、`reuse_records` の並びが揺れる。比較・スナップショット・再現性に影響。  
Required fix: 新規追加は `for genome_id in sorted(selected_ids):` 等で順序固定。

3. `prev_epoch` 20% cap の適用位置がランキング前で、入力順依存  
Fact: `select_warmstart_candidates` で `epoch_filtered` を作る際、`candidates` の生順で cap 消費し、その後に CA/DA ソートしている。  
Interpretation: 上限枠を低スコア個体が先取りし、高スコア個体が落ち得る。`archive.members` 順に依存し、選抜品質・説明可能性を損なう。  
Required fix: cap判定は少なくとも lane別ソート後（`ca_rank/da_rank + genome_id`）に適用、または生順を明示的に固定（`genome_id` 昇順）して仕様化。

[Warning]  
1. `WarmstartReport.relaxation_steps` が「発動順」になっていない  
Fact: `tuple(sorted(set(ca_relax)|set(da_relax)))` は辞書順。  
Interpretation: 監査ログが仕様コメント（発動順）と不一致。  
Fix案: 順序保持 union を実装。

2. filter drop観測値が実質欠落  
Fact: `cooldown_filter_drops/max_reuse_filter_drops/epoch_age_2_plus_drops` を report で常に 0 固定。  
Interpretation: build側で落ちた実数が追跡不能になり、原因分析が弱い。  
Fix案: build側で `candidates + stats` を返す。

3. `is_boost_applicable` を `ca_ratio==0.5` で推定している  
Interpretation: 将来 ratio 変更時に誤判定しやすい。  
Fix案: 真偽値を明示引き回し。

4. `new_dataset_epoch_id` が実質未使用（非空チェックのみ）  
Interpretation: 将来の誤読ポイント。使わないなら削除、使うなら利用箇所を明示。

[Suggestion]  
1. `prev_epoch_cap` の丸め規約（floor/ceil/min1）を明文化してテスト化。  
2. Determinismテストを「入力順shuffleしても同一結果」に拡張。  
3. `admit_warmstart_to_da_with_eviction` 後に Archive不変条件を専用アサートで毎回検証。

観点1-17の総評  
主要構造（7 dataclass、契約チェック、emergency条件、責務分離、Phase 2申し送り、Decision Pending管理）は概ね良好です。  
ただし上記 Critical 3件は、SSOT整合・再現性・選抜品質に直結するため Round 1 で解消が必要です。