# Calibrate-Gate Drift Observation — Template

**TODO**: T051 (Low、運用観察用)
**起点監査**: [audit-codex.md §2 (20)](../../devnotes/20260427-0050-bug-hunt-audit/audit-codex.md) — INCONCLUSIVE
**前提**: T040 で `scripts/alpha_factory/calibrate_gate_drift.py` + JSONL 永続化が完成済。

## 観察手順

Run 23+ ごとに以下を実行し、本ファイルを次のテンプレートで毎月 1 ファイルずつ保存する:

```bash
uv run python scripts/alpha_factory/calibrate_gate_drift.py --last 5
```

期待出力 (例):
```
## Calibrate Gate Drift (last 5 runs)

| run_id | decision | prev_t | new_t | actual | target | gap | clamped |
|--------|---------|-------|------|--------|--------|-----|---------|
| run_22 | tighten | 0.078 | 0.178 | 0.30   | 0.15   | +0.15 |        |
| run_23 | ...     | ...   | ...  | ...    | ...    | ... |        |
| ...    |         |       |      |        |        |     |        |

Alerts:
- monotone tighten: N/5 (ALERT if N >= 4)
- monotone loosen: N/5
- threshold clamp: N/5
- pass_rate band excess (max |gap|=...)
```

## 観察記録ファイル命名

`reports/calibrate-gate/observation-YYYY-MM.md`

各ファイルは以下のテンプレートで構成:

```markdown
# Calibrate-Gate Observation YYYY-MM

## 観察対象 Run
- Run NN (YYYY-MM-DD): decision=..., new_t=..., actual=..., target=...
- Run NN+1 ...

## drift CLI 出力 (実行コマンド + 結果貼り付け)

## アラート発火状況
- [x] monotone_tighten: N/5
- [ ] monotone_loosen: 0/5
- [ ] threshold_clamp: 0/5
- [ ] pass_rate_band_excess: max |gap|=...

## 解釈
- (人間判定: drift の有無、原因仮説、対応の必要性)

## 対応 (該当時のみ)
- [x] freeze: yaml で `calibrate.enabled=false` に設定 (commit hash)
- [ ] root cause 調査の TODO 起票 (link)
- [ ] control law 修正検討の TODO 起票 (link)
```

## アラート発火時の対応 path

| アラート | 推奨対応 |
|---------|---------|
| monotone_tighten 4/5 | target_pass_rate=0.15 が現状の fitness 分布に対し過剰の可能性。yaml で `calibrate.enabled=false` に freeze し、root cause 調査の TODO 起票 |
| monotone_loosen 4/5 | target_pass_rate が低すぎる可能性。同上、freeze + 調査 |
| threshold_clamp 3/5 | floor/ceiling 飽和。control law の clamp 範囲再検討 |
| pass_rate_band_excess | actual が大きく逸脱。dataset 期間や bars 数の急変有無を確認 |

## 北極星制約

判断主体は人間。本機構は記録・集計のみで calibrate-gate 制御則は変更しない (C3 collider bias 回避)。アラート発火 → 自動修正は行わない。

## 関連

- 親概念: [docs/alpha_factory/concepts/calibrate-gate.md](../../docs/alpha_factory/concepts/calibrate-gate.md)
- drift CLI: `scripts/alpha_factory/calibrate_gate_drift.py` (T040)
- 永続化 SSoT: `src/alpha_factory/calibrate_gate_history.py` (T040)
