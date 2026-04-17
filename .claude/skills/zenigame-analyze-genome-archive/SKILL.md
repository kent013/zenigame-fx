---
name: zenigame-analyze-genome-archive
description: Alpha FactoryのGA実行結果（ゲノムアーカイブ）を深層分析する
argument-hint: "[run_id]"
---

# ゲノムアーカイブ深層分析

Alpha FactoryのGA実行結果を分析し、改善点を特定する。

## 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `run_id` ($1) | No | 分析対象のrun_id（例: run_20260219_182245）。省略時は最新Runを自動検出 |

**手法ドキュメント**: `docs/alpha-factory/analysis-methodology.md` を必ず最初に読み、単位・計算式・注意事項を理解してから分析を開始すること。

## 重要: 単位の確認

**全ての分析でこのルールを厳守**:

| メトリクス | 単位 | 値の例 | 意味 |
|-----------|------|--------|------|
| net_return / gross_return | **%** | `1.08` | IC比 **1.08%**（10,800円）。108%ではない |
| sharpe | **無次元（Raw、非年率化）** | `0.19` | mean/std。√252は掛けない |
| win_rate | **比率 [0, 1]** | `0.51` | 51%の勝率 |
| max_dd | **%（常に負値）** | `-2.5` | 2.5%のドローダウン |
| trade_count | **整数** | `61` | 評価窓全体でのトレード数 |
| cost (gross - net) | **%** | `0.79` | IC比 0.79%（7,900円） |

**金額換算**: `値(%) × 1,000,000 / 100`

## 分析手順

### Step 1: 統合分析スクリプトを実行

```bash
# 全セクション（run_id省略時は最新Run自動検出）
uv run python scripts/trading/analyze_genome_archive.py {{run_id}}
```

スクリプトが出力するセクション:
0. Mission Dashboard（D*スコアカード、Top-5 gap、fail_reason分解）
1. 基本統計（A/B/C-PASS、Best B-Sharpe）
2. GA進化効果（meta_source別A-PASS率）
3. コスト構造（per-trade gross/cost/net、mean of ratios）
4. 構造多様性（ユニーク組み合わせ、n_signals分布）
5. パラメータ分布（time_stop, max_pos等）
6. トレード回数 vs Sharpe（四分位分析）
7. 日付窓効果（月別B-Sharpe、A-PASS率）
8. 世代別進化（A-PASS率、B-Sharpe推移）
9. Top個体詳細（B-Sharpe Top 10）
10. C-PASS分析（B→Cデケイ、fail reasons、pass_count）
11. Mission Gap Score（D*追跡、Top-5 gapスコアボード、Gap分布統計）
12. プリミティブ別パフォーマンス（B-Sharpe貢献度）
13. 新プリミティブ効果（`--new-primitives`指定時）
14. Clause構造分析（n_clauses分布、local_gate使用、構造多様性）

### Step 2: 新プリミティブ効果（該当する場合）

直近のRunで新しいプリミティブが追加された場合:

```bash
uv run python scripts/trading/analyze_genome_archive.py {{run_id}} --new-primitives シグナル名1,シグナル名2
```

### Step 3: 特定セクションの深堀り（必要に応じて）

```bash
# 特定セクションのみ再実行
uv run python scripts/trading/analyze_genome_archive.py {{run_id}} --sections basic cost c_pass

# Top個体数を変更
uv run python scripts/trading/analyze_genome_archive.py {{run_id}} --top-n 20
```

### Step 4: 追加分析（スクリプトでカバーされない分析）

以下はスクリプトに含まれない分析で、必要に応じて手書きで実行:

- **特定シグナルのパラメータ感度分析**（signals parquetをparam_*でビン分けしてB-Sharpe比較）
- **コンテンツハッシュ重複検出**（content_hashでgroupbyして重複確認）
- **個体の詳細JSON構造確認**（genome_json parquetから特定個体を復元）

```python
# パラメータ感度分析の例
s = pd.read_parquet(f'.cache/alpha_factory/runs/signals_{run_id}.parquet')
sig = s[s['signal_name'] == 'TargetSignal'].merge(
    ap[['genome_id', 'stage_b_sharpe']], on='genome_id'
)
sig['k_bin'] = pd.cut(sig['param_k'], bins=5)
print(sig.groupby('k_bin')['stage_b_sharpe'].agg(['mean', 'count']))
```

## 結果の報告形式

スクリプト出力をベースに以下の構造で報告:

```
## 分析サマリー
- Run ID: ...
- 総個体数: ... / A-PASS: ... / B-PASS: ... / C-PASS: ...
- Best B-Sharpe: ... (閾値0.2までの距離: ...)

## GA進化効果
- offspring A-PASS率: ...% vs random: ...%

## 主要発見
1. (最も重要な発見)
2. ...
3. ...

## 改善提案
1. (優先度★★★) ...
2. (優先度★★☆) ...
3. (優先度★☆☆) ...
```

## 注意事項

- **スクリプトはBashツールで直接実行**する（Taskエージェントに投げず直接実行すること）
- 分析結果の数値には**必ず単位を明記**（%, 円, 比率, 無次元 等）
- Stage AとBのtrade_countは直接比較不可（窓日数が異なる）
- per-trade指標は **mean of ratios** で計算（スクリプト内で準拠済み）
- 0除算防止: trade_count=0の個体はNaN化してから除算（スクリプト内で準拠済み）
