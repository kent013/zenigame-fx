結論を先に固定します。  
E は **`archive=120`、`warmstart=20%`、`inflow=8/per_run_max=12`（pop=192基準）**。  
F は **`P2=session 3 bucket 固定`**。6 bucket は現partitionでは不採用で確定です。

1. **反論1（archive total）**
採用は **120**（CA 72 / DA 48）です。

- `100` は zenigame 比率準拠だが、FX単一pairでは「銘柄多様性」で補えない
- `96` はさらに短期循環化して記憶層が薄い
- `120` なら `archive/pop=0.625` を維持でき、単一pairの多様性補完に妥当

記憶半減期（近似）:
- `target_inflow=8` のとき入替率 `8/120=0.0667`
- 半減期 `ln(2)/0.0667 ≈ 10.4 runs`
- 全更新目安 `120/8=15 runs`

2. **反論2（warmstart share）**
採用は **20%** です（33%は不採用、25%も見送り）。

- pop192: `0.20*192=38体`
- 通常内訳: **CA:DA = 2:1**（`26:12`）
- emergency: **1:1**（`19:19`）

補足:
- epoch序盤の供給不足を避けるため、`warmstart_ramp` を入れる  
  `run1=0%`, `run2=10%`, `run3=15%`, `run4+ =20%`

3. **反論3（inflow / per_run_max）**
採用は **pop比例**（Round 11 比率を維持）です。

- `target_inflow = round(0.04 * pop)`
- `per_run_max = round(0.06 * pop)`

結果:
- pop192: `target=8`, `max=12`
- pop256: `target=10`, `max=16`

理由:
- pop変更（192→256 promotion）に連動して自動スケールする
- 固定値より運用一貫性が高い

4. **反論4（bypass K 動的式）**
pop192用は以下で確定します。

- 通常:
  - `K_raw = target_inflow - n_mission - n_progress`
  - `K = clamp(K_raw, 2, 6)`
- emergency:
  - `K_raw = (target_inflow + 2) - n_mission - n_progress`
  - `K = clamp(K_raw, 4, 8)`

品質床は既確定のまま維持:
- `invariant_feasible=True`
- `margin_inf percentile <= 70`

5. **反論5（P2 6 bucket 解禁可否）**
**解禁不可で確定**。session 3 bucket を維持します。

サンプル数（1 block=1営業日×1bucket）:
- 3 bucket:
  - Stage B pooled: 125/bucket
  - C-lite単窓: 30/bucket
  - Stage C: 60/bucket
- 6 bucket化（概ね半減）:
  - B: 62/bucket
  - C-lite: 15/bucket
  - C: 30/bucket

`C-lite=15` は C7 規律に抵触。現設計では6 bucket不採用が妥当です。

6. **反論6（vol/aux の扱い）**
採用は **(a)**。monitorだけで終わらせず archive metadata に保持します。

保持項目:
- `vol_regime_pass_pattern`
- `aux_factor_pattern`
- `dataset_epoch_id` と合わせて後段分析/eviction補助に使用

7. **反論7（cross_pair_pass_tag）**
採用は **(ii) 連続値**、ただし実装は **(iii) per-pair生値も保存**します。

- evictionで使う主キー: `shadow_robustness_score`（連続）
- 監査/説明用: 5通貨それぞれの指標（per-pair）を保存
- binary tag は派生値として保持可だが主キーには使わない

8. **論点E+F 確定案（最終値表）**

| 項目 | pop=192 baseline | pop=256 promotion |
|---|---:|---:|
| archive_total | 120 | 160 |
| archive_CA / DA | 72 / 48 | 96 / 64 |
| target_inflow/run | 8 | 10 |
| per_run_max | 12 | 16 |
| warmstart_share | 20%（rampあり） | 20%（rampあり） |
| warmstart CA:DA (通常) | 26:12 | 34:17 |
| warmstart CA:DA (emergency) | 19:19 | 26:25 |
| max_per_source_run | 2 | 2 |
| max_per_session_pattern | 2 | 2 |
| max_family | 2 | 2 |
| max_reuse | 3 | 3 |
| cooldown | 2 runs | 2 runs |
| bypass K (通常) | clamp(8 - nm - np, 2, 6) | clamp(10 - nm - np, 2, 6) |
| bypass K (emergency) | clamp(10 - nm - np, 4, 8) | clamp(12 - nm - np, 4, 8) |
| P2 bucket | 3 固定 | 3 固定 |
| vol/aux | archive metadata保存 | archive metadata保存 |
| cross-pair | 連続score + per-pair保存 | 連続score + per-pair保存 |

INCONCLUSIVE:
- `warmstart_ramp` の段差（0/10/15/20）は F-1 smoke 後に微調整余地あり
- `shadow_robustness_score` の重み式は運用ログで再同定対象