[VERDICT]  
**CHANGES_REQUESTED**

[Critical]  
1. `prev_epoch 20% cap` が「全体上限」になっていません。  
Fact: `select_warmstart_candidates` で `prev_epoch_cap` を1回計算した後、`ca_sorted` と `da_sorted` に同じ `cap` をそれぞれ適用しています。  
Fact: `prev_epoch_admitted=ca_prev_admitted + da_prev_admitted` と加算しており、CA/DAで別枠として扱われています。  
Interpretation: 全体上限20%ではなく、実質「CAで20% + DAで20%」になり得ます（例: `target_total=38` なら cap=7 だが最大14まで許容される）。要件「prev_epoch 20% 上限」に不一致です。  
Required fix: cap をグローバル予算として管理してください（例: CA選抜後に実際採用した prev_epoch 数を引いた残予算を DA に適用）。

2. DA側 cap 適用タイミングが重複除外前で、予算消費が歪みます。  
Fact: `da_filtered` は `_apply_prev_epoch_cap_in_sort(da_sorted, cap=...)` で作成した後に、`ca_ids` 除外しています。  
Interpretation: CAで既に選ばれた genome が DA 側 cap を先に消費し、その後除外されるため、実効的に DA 側の prev_epoch 枠が目減りします。選抜品質と説明可能性に影響します。  
Required fix: DA側は `ca_ids` 除外後のプールに対して cap を適用するか、前項の「グローバル残予算」方式に統合してください。

[Warning]  
1. `epoch_age` の下限検証がありません（負値許容）。  
Fact: `epoch_age is None` と `epoch_age==0` 整合性は検証していますが、`epoch_age < 0` を弾いていません。  
Interpretation: callerバグ時に不正値が静かに通る余地があります。

2. `__all__` に `WarmstartFilterStats` が含まれていません。  
Interpretation: 外部利用/テスト方針によっては export 一貫性が崩れます。

3. `StagePassStatus` が未使用です。  
Interpretation: ruff 設定次第で `F401` になります。

[Suggestion]  
1. 追加テスト: `prev_epoch` が CA+DA 合算で必ず cap 以下になること。  
2. 追加テスト: DA は `ca_ids` 除外後に cap 評価されること。  
3. docstring に「cap は global budget」であることを明記。

Round 1 指摘（C1/C2/C3 + W/S）の修正意図自体は適切です。  
ただし上記 Critical 2件が残るため、Round 2 は APPROVED にはできません。