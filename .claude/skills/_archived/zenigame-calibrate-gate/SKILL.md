---
name: zenigame-calibrate-gate
description: Stage A Adaptive Gateの stage_b_ratio を前回Runのgate_statsに基づいてLLM判断で自動調整する
argument-hint: "[run_id]"
---

# Stage A Gate キャリブレーション

前回Runの`gate_stats`（サマリーJSON内）を読み取り、`config/alpha_factory/default.yaml`の`stage_a_gate_stage_b_ratio`を次Runに最適な値に調整する。

**判断主体はLLM（Claude）**。gate_statsの全体像を見て合理的な stage_b_ratio を決定する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_id` ($1) | No | 分析対象のrun_id（例: run_20260302_203408）。省略時は最新Runを自動検出 |

---

## 手順

### Step 1: サマリーJSONの取得

`run_id` 引数がある場合はそのIDで、省略時は最新のサマリーJSONを検出:

```bash
ls -t .cache/alpha_factory/runs/*_summary.json | head -1
```

サマリーJSONを `Read` で読み込み、`gate_stats` セクションを取得する。

### Step 2: gate_statsの確認

`gate_stats` が空（`{}`）または存在しない場合:
```
ℹ️ gate_stats未検出（Stage A Gate無効のRunまたはT151実装前のRun）。キャリブレーションをスキップします。
```
→ 処理を終了（default.yamlは変更しない）。

### Step 3: 現在の設定値の読み取り

`config/alpha_factory/default.yaml` から現在の Gate 設定を `Read` で取得:
- `stage_a_gate_stage_b_ratio`（現在値）

### Step 4: 新しい stage_b_ratio の決定

以下の情報をもとに、LLM（自分自身）が次Runの `stage_a_gate_stage_b_ratio` を決定する。

**判断材料**:
- `gate_stats.a_pass_rate`: 前Runの実績A-PASS率（ゲート後）
- `gate_stats.total_gate_blocked`: ゲートでブロックされた総数
- `gate_stats.total_a_pass`: Stage A通過総数
- `gate_stats.total_evaluated`: 評価総数
- `gate_stats.stage_b_ratio`: 前Runで使用した stage_b_ratio

**判断ガイドライン**:

1. **基本方針**: stage_b_ratio は「毎世代、hard_pass した個体のうち上位何%を Stage B に送るか」を制御する。ランキングベース選択のため、位相ラグの問題はない。

2. **調整の目安**:
   - ゲートブロック数がゼロまたは非常に少ない → hard_pass 自体が少ない（A条件側の問題）。ratio は変更不要
   - A-PASS率が5%未満 → ratio を 0.02 上げる（ゲートを緩める）
   - A-PASS率が30%以上 → ratio を 0.02 下げる（ゲートを締める）
   - それ以外 → 変更なし

3. **クランプ**: 最終値は `[0.10, 0.30]` の範囲に収める

4. **変更幅の制限**: 前回の ratio からの変更幅は ±0.05 以内とする

**決定ロジック（擬似コード）**:
```
a_pass_rate = gate_stats["a_pass_rate"]
prev_ratio = gate_stats["stage_b_ratio"]

new_ratio = prev_ratio

if a_pass_rate < 0.05:
    new_ratio += 0.02  # ゲート緩め
elif a_pass_rate > 0.30:
    new_ratio -= 0.02  # ゲート締め

# クランプ
new_ratio = max(0.10, min(0.30, new_ratio))

# 変更幅制限
new_ratio = max(prev_ratio - 0.05, min(prev_ratio + 0.05, new_ratio))

# 小数第2位に丸める
new_ratio = round(new_ratio, 2)
```

### Step 5: default.yamlの更新

新しい ratio が現在値と異なる場合のみ `Edit` で更新する:

```yaml
stage_a_gate_stage_b_ratio: {new_ratio}
```

### Step 6: 報告

```
## Gate キャリブレーション完了

| 項目 | 値 |
|------|-----|
| 前Run | {run_id} |
| 前Run stage_b_ratio | {prev_ratio} |
| 前Run A-PASS率 | {a_pass_rate} |
| 前Runゲートブロック数 | {total_gate_blocked} |
| **新しい stage_b_ratio** | **{new_ratio}** |
| 変更理由 | {判断の根拠を1-2行で} |
```

ratio に変更がない場合:
```
## Gate キャリブレーション: 変更なし

前Runのgate_statsを確認しましたが、現在の stage_b_ratio {current} は適切です。変更しません。
```

---

## 注意事項

- default.yaml の `stage_a_gate_stage_b_ratio` のみを変更する
- 判断の根拠を必ず報告に含める（透明性）
- gate_statsが存在しないRunではスキップ（安全側に倒す）
