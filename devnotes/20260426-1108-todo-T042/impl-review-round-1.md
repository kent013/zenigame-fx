[Critical] Stage B のハードゲート閾値が 0.05 に変更された旨は `config/alpha_factory/default.yaml:114` や各ドキュメントで明示されていますが、API 本体である `StageGateConfig` の既定値が依然として 0.20 のままです（`src/alpha_factory/stage_gate.py:84`）。`StageGateConfig()` を直接生成するコード（例: `tests/alpha_factory/test_swim_lane.py:210` や他の多数のテスト／手動実行パス）では新しいスケールが一切反映されず、trade-level への再スケールを導入した設計意図と齟齬を起こします。YAML ローダ経由以外の経路で Stage B を評価すると依然として旧値 0.20 が適用され、今回の T042 目的を満たせません。`StageGateConfig` のデフォルト値と同クラスを利用するテスト／ヘルパを 0.05 に揃える対応をお願いします。

[Warning] `docs/alpha_factory/sharpe-rescale.md` で根拠として参照している `devnotes/20260426-1030-phase0-sharpe-rescale/…` や `reports/sharpe-rescale/run-16-distribution.json` がリポジトリ内に存在せず（`ls devnotes/20260426-1030-phase0-sharpe-rescale` 等が Not Found）、Run 14〜16 の観測値を第三者が追確認できません。北極星制約の監査性を担保するため、参照パスを実在させるか、利用可能な場所への参照に修正してください。

[Suggestion] 上記 Critical の修正後、Stage B 閾値 0.05 が確実に適用される経路を回帰テストでカバーしておくと安心です（例: `StageGateConfig` デフォルトを用いるユニットテストに pass/fail の境界ケースを追加）。

全体判定: CHANGES_REQUESTED