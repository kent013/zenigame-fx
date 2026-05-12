## QA Critical (1個) + Warning (2個)
### Critical
- 変更内容: `graduation_criteria.require_cross_pair_pass` を shadow モード時は自動バイパスする条件付き判定へ修正し、Stage C 卒業を再び有効化する。
- 期待効果: 高（Run57-74 の graduation=0/18 という構造的ボトルネックを除去し mission 進度を再開）。
- 実装複雑性: 低（判定ガードの追加と設定整合確認のみ）。
- 禁止事項抵触: なし（禁止事項1-8 非該当、閾値緩和にも該当せず）。

### Warning 1
- 変更内容: T501-T506 Mission Shortfall fitness を移植し、mission_gap を fitness_pen に組み込む。
- 期待効果: 高（Stage A/B 通過個体のうち mission 近傍へ選択圧を集中でき、Bonferroni fail を縮小）。
- 実装複雑性: 中（fitness パイプラインとアーカイブ書式の差分吸収が必要）。

### Warning 2
- 変更内容: Stage A gate に `n_fold_effective >= wf_min_safe_folds` のハードチェックを追加し、Run60 型アーティファクトを排除する。
- 期待効果: 中（擬似的な高 sharpe 個体を除外し、探索リソースを実質的エッジへ集中）。
- 実装複雑性: 低（既存ゲート条件への単一ガード追加）。

## QB 棄却
- Q1: live_criteria.total_pnl を 50000 円から相対指標へ緩和する案は、禁止事項4「live_criteria 緩和」に抵触するため棄却。

## QC 先人の知恵 vs 現行設計
zenigame で mission 達成 203 RUN を支えた仕組み（Mission Shortfall fitness、明示的 graduation 判定など）は、同一 GA フレームで実績検証済みの「先人の知恵」であり、未成熟な zenigame-fx 固有ロジック（mission_inf_gap 単独最適化や shadow 卒業ロック）よりも早く構造的失敗 0/18 を反転させる最短径と判断する。Phase2 の新要素は、先人ロジックを再導入したうえで補助的に評価すべき。

## QD 全体判定: CHANGES_REQUESTED