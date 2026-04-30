[VERDICT] APPROVED

[Critical]
- なし

[Warning]
1. `§3.1` の「`select_warmstart_candidates` が cooldown/rolling/epoch filter を担う」記述は、`§7.2`/`§11.2`（build 側で filter 実施）と軽微にずれています。文言だけ同期するとより明確です。  
2. `§12.4`/`§12.5` のテスト名に `select_warmstart_candidates_*_cooldown/max_reuse/epoch_age_2_excluded` が残っており、責務分離（build 側）との対応が読み手にやや分かりづらいです。

[Suggestion]
1. テストの責務名を最終同期してください（例: cooldown/max_reuse/epoch_age は `build_warmstart_candidates_*` へ寄せる）。  
2. `§3.1` を `build=filter` / `select=selection+constraints` と1行で明示すると、詳細設計への引き渡しがさらに堅くなります。