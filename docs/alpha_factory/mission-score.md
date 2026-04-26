# mission_score — live_criteria 4 軸 soft 合算スコア

**TODO**: T043 (Phase 0)
**実装**: `src/alpha_factory/stage_gate.py::_compute_mission_score`
**Archive 列**: `mission_score: float | None` (`GENOMES_SCHEMA`)
**起点監査**: [audit-codex-round-2.md §3-4](../../devnotes/20260426-1010-ga-audit-r16/audit-codex-round-2.md)

## 目的

`live_criteria` の 4 軸 hard pass/fail のみでは「使命達成までの距離」が 0/1 でしか測れない。Run 14 (pnl=0) と Run 15 (pnl=8,660 / sharpe=0.069) のどちらが mission に近いかを判定不能、という問題が Run 1〜16 監査で観測された。`mission_score` は **連続値の進捗指標**として archive と report に記録する観測専用スコア。

**重要**: `mission_score` は **GA fitness や `stage_c.passed` には影響しない**。当面は observation only。Phase 1 以降で GA fitness 組み込みを再評価する。

## 数式

各軸 `i` ∈ {sharpe, total_pnl, max_drawdown, trade_count} について `lower_i` / `target_i` を定義:

| 軸 | lower | target | 向き | スケール (T042 後) |
|----|------|--------|------|------------------|
| sharpe | 0.0 | `live_criteria.sharpe_min` | 大きいほど良い | **annualized** (`_annualize_trade_sharpe` 経由)、[sharpe-rescale.md](sharpe-rescale.md) |
| total_pnl | 0.0 | `live_criteria.total_pnl_min` | 大きいほど良い | 通貨単位（JPY） |
| max_drawdown_frac | `live_criteria.max_drawdown_max` | 0.0 | **小さいほど良い (逆向き)** | fraction (0-1) |
| trade_count | 0 | `live_criteria.trade_count_min` | 大きいほど良い、ただし `> trade_count_max` で score=0 (範囲制約) | trade 数 |

### 軸別スコア (clip + 線形正規化)

正方向軸（sharpe / total_pnl / trade_count）:
```
score_i = clip((metric_i - lower_i) / (target_i - lower_i), 0, 1)
```

逆方向軸（max_drawdown_frac）:
```
score_i = clip((lower_i - metric_i) / (lower_i - target_i), 0, 1)
```

### floor 0.1 にスケール（log 表示可能化）
```
score_i' = 0.1 + 0.9 × score_i      ∈ [0.1, 1.0]
```

### 幾何平均
```
mission_score = (Π_i score_i')^(1/4)   ∈ [0.1, 1.0]
```

幾何平均を採用する理由は、1 軸が 0 score（floor=0.1）に落ちると合成全体が引き下げられ、**「全軸での合成達成の困難さ」を反映**するため。算術平均だと一軸の超過で他軸の不足を打ち消せてしまう。

## 性質

- 全軸 target 達成 → `mission_score = 1.0`
- 全軸 lower 以下 → `mission_score = 0.1`（log 表示で `log(0.1) = -1`）
- 1 軸が 0 score、他 3 軸 target 達成 → `(0.1 × 1.0³)^(1/4) ≈ 0.5623`
- `Sharpe = None`（base 評価で trade を出せず計算不能）→ `mission_score = None`（report で「未計測」表示）

## 北極星制約との整合

AGENTS.md 禁止事項 #2「見た目の数値をよくしようとする改善」に **抵触しない**。

- hard `live_criteria` は不変
- GA fitness (`sharpe`) も不変
- `mission_score` は archive / report への観測指標追加のみ
- 「mission_score を上げる」ことは GA selection に直結しないため hack を誘発しない

将来 `mission_score` を GA fitness に組み込む場合は、別 TODO で改めて設計レビューする（北極星制約との整合性を再確認）。

## report 表示

`scripts/alpha_factory/generate_run_report.py` が以下を出力:

- `mission_score` 分布（n / mean / median / std / min / max）
- best mission_score 個体の identifier (`individual_name`, generation, instrument)
- Stage C 評価で Sharpe=None の個体（trade を出していない）は計測対象外として明示

## 学術背景

連続的な多目的スコアリングの選択は文献に複数の流儀があり、本実装は以下の方針で固定:

- **Min-max 正規化 + 幾何平均**: 各目的を [0, 1] に正規化した上で幾何平均を取る合成は、Multi-objective optimization の Achievement Scalarizing Function（要確認: Wierzbicki 1980 系列）と発想を共有する。
- **floor 0.1 スケーリング**: 完全 0 を避けることで log 表示可能化と微小改善の visibility 確保。Bailey & López de Prado (2014) "The Deflated Sharpe Ratio" のような Sharpe ベース連続スコアと組み合わせ可能（要確認）。

具体的な重み付けや凸性制御は Phase 1 で再評価する。

## 変更履歴

- 2026-04-26: T043 初期実装（Phase 0）。Codex Round 2 §3-4 で数式合意。
