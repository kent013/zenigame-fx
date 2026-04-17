---
name: zenigame-alpha-sieve
description: Alpha Sieve（OOS検証）の実行・結果分析・対照表生成を行う
user-invocable: true
---

# Alpha Sieve 実行・分析スキル

Alpha Sieveを実行し、OOS検証結果を分析する。1プロセス・1回のpreloadで全個体を評価する。

## 使い方

```
/zenigame-alpha-sieve run <run_ids...>          # 指定Runのadaptive_pass個体を評価
/zenigame-alpha-sieve run --all-new             # 未評価の全Runを評価
/zenigame-alpha-sieve run <run_ids> --score-bypass-top-n 10  # T479: bypass経路も含む
/zenigame-alpha-sieve analyze                   # 全結果の統合分析（レジーム別・対照表）
/zenigame-alpha-sieve compare                   # adaptive_pass vs non-adaptive比較
```

## 実行フロー

### `run` モード

1. 対象Run IDを特定（引数指定 or --all-new で未評価Run自動検出）
2. **1プロセス・1回のpreload**で全Run全個体を評価
3. 結果をDB + Parquetに保存（`sieve_source` カラム付きで永続化）
4. Run単位でanalyze（レジームveto判定）実行
5. **T439: sieve_score計算 + sieve_pass_archive自動更新**
6. **T441: Sieveレポート自動生成**

**コマンド:**
```bash
# 通常実行（adaptive_pass個体のみ）
uv run python scripts/trading/run_alpha_sieve.py --run-id <RUN_ID_1> <RUN_ID_2> ... --direct

# T479: score_bypass 経路も含めて実行
uv run python scripts/trading/run_alpha_sieve.py \
  --run-id <RUN_ID_1> <RUN_ID_2> ... --direct --score-bypass-top-n 10
```

**重要な注意事項:**
- `--run-id`は複数指定可能。全て1プロセスで処理される（preload 1回）
- backtestパラメータは最初のRunのconfig_snapshotから自動継承（GA本体と同じ条件）
- ユニバースはデフォルトでRandomUniverseProvider(seed=42, n_stocks=50)
- **別プロセスで複数回起動しない**。必ず1コマンドに全Run IDをまとめる

### T479: Score Bypass 経路

`adaptive_mission_pass=0` が長期継続する状況で Sieve フィードバックループを維持するために、C-PASS 個体から `adaptive_mission_worst_gap` 昇順 → `adaptive_mission_score` 降順で上位 N 体を追加で Sieve に送るバイパス経路。

**使い方:**
- **自動実行（GA Run完了時）**: `config/alpha_factory/default.yaml` の `sieve_warmstart.score_bypass_top_n`（デフォルト10）が自動的に適用される
- **手動実行（このスキル）**: `--score-bypass-top-n <N>` オプションで指定（デフォルト0=無効）

**sieve_source カラム**: 各個体には選抜経路が記録される:
- `adaptive_pass`: 正規経路（adaptive_mission_pass=True）
- `score_bypass`: バイパス経路（T479）
- `unknown`: T478以前の legacy エントリ

この値は `AlphaSieveRun.sieve_source` DB列と `sieve_pass_archive.json` の entry `source` フィールドに永続化され、warmstart 注入時のログにも出力される（因果追跡用）。

**使用上の禁止事項:**
- `sieve_source` を adaptive_live_criteria 閾値緩和の根拠として使用しない
- bypass 経路を優先する設計変更を行わない

### `analyze` モード

全Sieve結果を読み込み、以下を出力:
1. 全個体ランキング（OOS Sharpe順）
2. レジーム別集計（6レジーム × Sharpe/Net/TC/WR）
3. 対照表をdevnotesに出力
4. adaptive再判定（OOSでもadaptive基準を満たすか）
5. **T441: Sieveレポート自動生成**

### `compare` モード

adaptive_mission_pass=Y個体 vs C-Sharpe上位（adaptive=N）個体のOOS成績を比較。

## 結果の保存先

| 種別 | 場所 |
|------|------|
| 日次結果Parquet | `.cache/alpha_sieve/{run_id}/` |
| DB集計 | `alpha_sieve_runs`テーブル（T479: `sieve_source` カラム含む） |
| Sieve pass archive | `.cache/alpha_factory/sieve_pass_archive.json`（T479: `source` フィールドおよび `reinjection_details` 含む） |
| Sieve レポート | `reports/alpha-sieve/{yyyy-mm}/sieve-report-{YYYYMMDD}-{HHMM}.md`（年月ブロック） |
| **Run単位レポート** | `reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md`（年月ブロック） |
| **指標サマリー** | `reports/alpha-sieve/sieve-metrics-summary.md`（トップレベル） |

## Sieve レポート

`--direct`/`--analyze`実行後にMarkdownレポートが自動生成される（`--no-report`で無効化可能）。

### レポート内容
1. 個体ランキング（sieve_score上位30体）
2. レジーム別集計（6レジーム x Sharpe/Net/TC/WR + adaptive基準gap）
3. GA Stage C成績との対照表
4. Sieve pass archive状況
5. adaptive vs non-adaptive群比較

### 出力先
- `reports/alpha-sieve/{yyyy-mm}/sieve-report-{YYYYMMDD}-{HHMM}.md`（書き込み時刻の年月ブロックに配置）

### 過去分レポート生成
```bash
uv run python scripts/trading/run_alpha_sieve.py --run-id RUN_482 RUN_483 ... --analyze
```

## Sieve Warmstart（T439）

### 自動動作
`--direct`実行完了後、sieve_score計算 + sieve_pass_archive更新が自動実行される。

- sieve_score: レジーム別adaptive基準gapのspectral集約（0-1）
- Gate 0: OOS Net>0, Sharpe>0, TC>=100
- Gate 1: TDL/TDH Sharpe<-2.0なら除外（hard fail）
- Gate通過個体は `.cache/alpha_factory/sieve_pass_archive.json` に保存
- 次GA Run起動時、`sieve_warmstart.enabled=true`（default.yaml）ならarchiveから自動注入

### warmstart注入の制約
- 動的budget: warmstart枠 * sieve_share比率で配分（デフォルト0.33）
- 同一family上限2体、同一個体は直近8Runで最大2回、cooldown 2Run
- 候補不足時はWinners枠に自動返却

### archive更新失敗時
Run自体の成功判定には影響しない（警告ログのみ）。

## Workerパス（dramatiq）

dramatiq workerパスでも、`analyze_alpha_sieve` actor完了後に以下が自動実行される:
1. sieve_score計算 + sieve_pass_archive更新（排他ロック付き）
2. Run単位レポート生成（`reports/alpha-sieve/{yyyy-mm}/sieve-R{run_number}.md`、年月ブロック）
3. Sieve指標サマリー更新（`reports/alpha-sieve/sieve-metrics-summary.md`）

いずれもnon-critical（失敗してもanalyze自体の成功判定に影響しない）。

## パラメータ継承ルール

- backtestパラメータ（min_bar_volume, use_spread_cost等）は**最初のRunのconfig_snapshot.runから自動継承**
- 必須キー（min_bar_volume, use_spread_cost, vpr_cap）が欠損している場合はエラー終了
- ユニバースはGAと同じものを使う（現状はRandomUniverseProvider seed=42 n_stocks=50）

## よくあるミス（禁止事項）

1. **別プロセスで個体を1体ずつ評価しない** -- preloadが毎回走って20分xN体かかる
2. **ユニバースを実験群と対照群で揃えない** -- UniverseBuilderとRandomUniverseProviderは別の銘柄セットを返す
3. **backtestパラメータを手動指定しない** -- 必ずconfig_snapshotから自動継承する
