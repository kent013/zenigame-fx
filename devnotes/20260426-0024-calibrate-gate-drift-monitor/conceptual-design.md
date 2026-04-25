# 概念設計: calibrate-gate threshold drift 監視

## 背景

リーク監査 (2026-04-26) の灰色項目 (INCONCLUSIVE) として検出。

`scripts/alpha_factory/calibrate_gate.py` は前 Run の archive Parquet から実 pass
rate を集計し、`stage_gate.stage_a.threshold` を deterministic に動的調整する
（target=0.15 ± 0.05、`prev_threshold` を起点に incremental 更新）。

直接的な leak ではないが、**過去 Run の選抜傾向が next Run の通過条件に弱く伝搬**
するため、run 跨ぎで threshold が単調にドリフトしているか / pass rate が不安定か
を監視する仕組みが無い。現状 JSONL ログは stderr 出力のみで永続化されない。

## 目的

直近 N (3〜10) Run について `target_pass_rate` / `actual_pass_rate` /
`prev_threshold` / `new_threshold` / `decision` をクロスラン横断で観察できる
最小限の monitoring を導入する。閾値の暴走 / monotone drift を early-warning
できるようにする。

## 成功条件

1. calibrate-gate 実行ごとに decision 履歴が永続化される（追記型）
2. 直近 N Run の drift 表が短時間で生成できる（CLI またはスキル）
3. drift 異常パターン（例: 5 Run 連続 tighten / threshold が ceiling に貼り付く /
   actual_pass_rate が target ± 2×tol を逸脱）を検出可能
4. 結論は観察記録のみ（C3 collider bias 回避）。閾値変更 logic への自動 feedback はしない

## 失敗モード

- 履歴ファイルが run と同じ commit に含まれてリポジトリが膨らむ → reports/ 配下の
  追記専用 JSONL に置き、generate_run_report のフックで pull / aggregate
- drift 警告が誤検知過剰 → アラート閾値は保守的に設定し、人間判定前提

## 想定アプローチ

A. **JSONL 永続化 + on-demand 集計**
   - calibrate_gate スクリプトが既存 stderr 出力に加え `reports/calibrate-gate/history.jsonl`
     にも 1 行追記
   - 集計 CLI `scripts/alpha_factory/calibrate_gate_drift.py --last N` で
     直近 N Run のテーブルを stdout に表示
   - run-report / improve-cycle から呼び出す

B. **既存 run-report への組み込み**
   - generate_run_report.py が JSONL を読み、対応 Run の calibrate decision 行を
     run-report.md の付録に貼る

C. **Skill 化**
   - `.claude/skills/zenigame-fx-calibrate-gate-monitor/` を新設し、CLI を呼ぶ thin wrapper

A + B + C を段階導入。Phase 1 = A のみ（CLI と JSONL 永続化）、
Phase 2 = B 組み込み、Phase 3 = C skill 化。

## 制約

- **判断は記録のみ**。calibrate-gate の制御則は変えない（C3 / 既存 SKILL の方針継承）
- run_id ごとに 1 行（重複追記の場合は run_id+timestamp で uniq 化）
- JSONL schema は SSoT として `docs/alpha_factory/concepts/` に明記
- 実装モード: `incremental`（calibrate_gate.py の追記改修と新規 CLI）
- 優先度: `Low` — 現状 leak は確認されておらず、ドリフト観察は予防的監視

## 次ステップ

- 詳細設計で JSONL schema, drift detection rule, CLI 引数を確定
- Phase 1 のみで minimal pass / 後続 Phase は別 TODO 化
