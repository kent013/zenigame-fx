# 詳細設計: calibrate-gate threshold drift 監視 Phase 1

親: `conceptual-design.md`

## 使命・制約

- 使命: 直近 N Run の calibrate-gate decision を横断観察し、threshold の単調ドリフト
  / actual_pass_rate の暴走を early-warning する
- 制約: 判断主体は人間。本機構は記録・集計のみ。閾値制御則は変更しない（C3 collider bias）
- AGENTS.md C8 遵守: drift 「あり / なし」を二値判定せず、観察値とアラート条件を出力

## failure_mode / causal_path / falsification / success_criterion

| 項目 | 内容 |
|------|------|
| failure_mode | calibrate-gate が 5 Run 連続 tighten / loosen で threshold が monotonic drift し、Stage A 通過率が target band を恒常的に逸脱する状態に気付けず、後続 Stage B/C の selection bias が累積する |
| causal_path | (a) target_pass_rate=0.15 が現状の fitness 分布に対し過剰 / 不足 → (b) actual_pass_rate が tol 外 → (c) tighten/loosen 連発 → (d) threshold が floor/ceiling に貼り付く → (e) Stage A が「全通し」or「全否定」状態化し選抜が機能停止 |
| falsification | drift 表で「直近 N Run 中 K 回以上 tighten / loosen」「actual−target の累積偏差」が閾値以下なら drift なしと結論。閾値超なら investigation 起票 |
| success_criterion | (1) JSONL 履歴に直近 5 Run 分が永続化、(2) drift CLI が 1 秒以内に出力、(3) アラート条件が誤検知 < 20% で抜け検出 < 20% |

## 変更箇所

| # | ファイル | 変更内容 |
|---|----------|---------|
| 1 | `scripts/alpha_factory/calibrate_gate.py` | 既存 `_emit` 直後に `_append_history()` を呼び、`reports/calibrate-gate/history.jsonl` に追記 |
| 2 | (新規) `scripts/alpha_factory/calibrate_gate_drift.py` | `--last N` で history.jsonl の末尾 N 行を読み、Markdown テーブル + アラート判定を出力 |
| 3 | (新規) `src/alpha_factory/calibrate_gate_history.py` | history record dataclass + read/append 関数 |
| 4 | (新規) `tests/alpha_factory/test_calibrate_gate_history.py` | 追記 / 読込 / drift 判定のユニットテスト |
| 5 | `.gitignore` | `reports/calibrate-gate/history.jsonl` は commit する（運用記録）。逸脱なし |
| 6 | `docs/alpha_factory/concepts/calibrate-gate.md` | drift 監視節を追記、JSONL schema を明記 |

Phase 2 以降:
- generate_run_report.py で drift 表を run-report.md に組み込み（別 TODO）
- Skill `.claude/skills/zenigame-fx-calibrate-gate-monitor/` 新設（別 TODO）

## JSONL schema (history.jsonl, 1 record / 1 line)

```json
{
  "run_id": "run_20260426_001234",
  "applied_at": "2026-04-26T00:12:34+09:00",
  "n_rows_total": 96,
  "n_rows_used": 80,
  "aggregation_mode": "last_k_generations",
  "aggregation_window": 5,
  "actual_pass_rate": 0.123,
  "target_pass_rate": 0.15,
  "tol": 0.05,
  "prev_threshold": 0.0977,
  "new_threshold": 0.0934,
  "delta": -0.0043,
  "decision": "loosen",
  "var_fitness_pen": 1.23e-2,
  "clamped_by_delta": false,
  "clamped_by_floor_or_ceiling": false,
  "stage_b_pass_count": 2,
  "stage_c_pass_count": 0,
  "live_criteria_gap": 0.31
}
```

- 一意性: `(run_id, applied_at)` で重複排除可能
- ファイル先頭にコメント行は置かず、純 JSONL

## drift 判定ルール（Phase 1 conservative）

```
window_n = 5
recent = read_history(last=window_n)

# Rule 1: monotonic decision
n_tighten = sum(1 for r in recent if r.decision == "tighten")
n_loosen  = sum(1 for r in recent if r.decision == "loosen")
alert_monotone = (n_tighten >= 4) or (n_loosen >= 4)

# Rule 2: threshold 貼り付き
n_clamped = sum(1 for r in recent if r.clamped_by_floor_or_ceiling)
alert_clamp = n_clamped >= 3

# Rule 3: actual_pass_rate 累積逸脱
gaps = [r.actual_pass_rate - r.target_pass_rate for r in recent]
alert_band = any(abs(g) > 2 * recent[-1].tol for g in gaps)
```

3 つのうち 1 つでも True なら CLI exit code 10（warn）。全 False なら exit 0。

## 出力例 (Markdown)

```
## Calibrate Gate Drift (last 5 runs)

| run_id | decision | prev_t | new_t | actual | target | gap |
|--------|---------|-------|------|--------|--------|-----|
| run_07 | tighten | 0.080 | 0.090 | 0.21   | 0.15   | +0.06 |
| run_08 | tighten | 0.090 | 0.095 | 0.19   | 0.15   | +0.04 |
| ...    |         |       |      |        |        |     |

Alerts:
- monotone tighten: 4 / 5
- threshold clamp: 0
- band breach: 1
```

## 波及変更

- AGENTS.md: なし
- skill: zenigame-fx-calibrate-gate.SKILL.md に「履歴は reports/calibrate-gate/history.jsonl
  に追記される」一文追加
- config: なし
- docs: 概念説明 1 節追加

## ルックアヘッドバイアスチェック

監視機構自体は集計のみで GA / fitness に逆流しない。calibrate-gate の制御則は不変。

## パフォーマンスチェック

- 追記: 1 record × ~500 bytes。N Run 分でも数十 KB
- 読込: 末尾 N 行の tail read（10 行 < 1 ms）

## テスト計画

- append: 同 run_id+timestamp 重複時の挙動（後勝ち or skip → skip）
- read: ファイル不在 / 不正 JSON 行を skip
- drift rule: 各 alert 条件が正しく fire / fire しない
- CLI: exit code 0 / 10 の切替

## リスク

- history.jsonl が commit 対象に含まれることでリポジトリが branch 跨ぎでマージ
  競合 → append 専用 + sort by applied_at で merge resolver を文書化
- 監視結果に基づき threshold を手動調整した場合、自動制御則と人手介入の混在で
  drift 解析が複雑化 → 手動介入は別 record（`source: "manual"`）として記録

## Codex レビュー

別フェーズで実施。本 TODO 登録時点では設計 round-1 のみ。
