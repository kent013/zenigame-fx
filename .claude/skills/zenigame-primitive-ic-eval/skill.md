# Primitive IC 評価実行

プリミティブ単体の予測力を Spearman rank IC で計測する。improve-cycle からは呼ばれない（手動 or 定期実行）。

---

## フロー

### Step 1: 前提確認

- `.cache/alpha_factory/primitive_ic/latest_summary.json` の存在確認 + 生成日時確認（30日超なら再計算推奨）
- `src/trading/alpha_factory/dsl/primitives/` の git diff 確認 → 変更があれば `--force_rebuild` 推奨

### Step 2: IS期間の自動取得

最新 Run レポートまたはメタデータから `date_pool` を取得し `--is_dates` として渡す:

```bash
latest_n=$(uv run python scripts/alpha_factory/get_latest_run_number.py) || exit 1
latest_report=$(find reports/run-reports -maxdepth 2 -name "run-${latest_n}.md" -not -path '*/old/*' | head -1)
```

レポートから IS 期間を読み取る。見つからなければユーザーに確認。

### Step 3: IC 評価実行（バックグラウンド）

```bash
nohup uv run scripts/ic_eval/run_primitive_ic.py \
  --start_date {eval_start} --end_date {eval_end} \
  --is_dates {is_start}:{is_end} \
  --horizon h5 --workers 2 --ionice \
  --output_dir .cache/alpha_factory/primitive_ic \
  > .cache/alpha_factory/primitive_ic/run.log 2>&1 &
```

PID を記録。タイムアウト 90 分でログ監視。

### Step 4: 完了後サマリー表示

- IC ランキング（TOP10 / BOTTOM10）
- RETIRE 候補一覧（verdict=RETIRE のプリミティブ）
- 推奨アクション: `/zenigame-primitive-ic-sync` の実行を案内

### Step 5: 完了報告

- `.cache/alpha_factory/primitive_ic/ic_report.md` を参照先として案内
