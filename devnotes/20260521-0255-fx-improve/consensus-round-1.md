**候補評価（R84）**

| 候補 | 判定 | 分類 | target_metric | failure_mode | causal_path | falsification | success_criterion |
|---|---|---|---|---|---|---|---|
| P1 再現性検証（別 seed） | **APPROVE** | **Structural**（評価プロトコル強化。GA改善値の最適化ではない） | `mission_count(seed)`、`mission_rate`、`genotype_family_count` | Run83が lucky seed 依存で次 run で mission 消失 | seed 変更のみで同一設定を再実行し、seed感度を直接観測 | seed変更 run で mission=0 かつ多様性増えずなら仮説棄却 | 追加 seed run で mission個体が再出現（最低1）し、family が単一集中から拡張傾向 |
| P2 stress の cost-robustness 化 | **MODIFY**（今ラウンドは診断化まで） | **Structural**（整合性修正） | `stress_cost_degradation`（非ゼロ分布）、`mission_after_cost_stress` | 既存 stress が実質ノーオペで robustness 未検証のまま進む | per-trade cost を増やす stress へ変えると初めて cost耐性を測れる | 導入後も degradation 全ゼロなら実装/定義不整合継続 | degradation が有意に非ゼロ化し、mission 生存率を判定可能 |
| P3 cross-pair ii-lite 計測→gate 昇格 | **REJECT（R84では）** | **Structural**（配線追加） | `ii_lite_coverage`、`graduation_count` | 実装面積が大きく loop 停止リスク増 | 計測・判定・gate配線で既存通過条件に広範囲影響 | 配線変更で既存判定が不安定化したら失敗 | R84の「低リスク最小変更」方針に不適合のため見送り |

**総合推薦（R84で1つに収束）**

- **先にやるべきは再現性（P1）**。理由は「ゼロ実装リスクで反証力が最大」だからです。
- 整合性問題（stress）は重要ですが、R84では **コード変更を伴う修正は入れず**、次サイクル先頭の Structural 修正として確定キュー化するのが安全です。

**R84の 1反証可能仮説 + 1最小変更**

- **仮説（反証可能）**: 「Run83の mission 達成は lucky seed ではなく、同一設定で seed を変えても mission 個体は再出現する」
- **最小変更**: `seed` のみ変更して R84 を実行（他パラメータ・ロジック不変更）

**成功/失敗判定（事前固定）**

- 成功: mission個体 `>=1` を確認
- 失敗: mission個体 `=0`（この場合、次サイクルで P2 を最優先実装し、cost robustness を先に正す）

**cycle_focus 判断（ga_improvements 確定の是非）**

- **確定するが「最小スコープ」に限定**  
  `ga_improvements = reproducibility_validation_only (seed perturbation only)`  
  ロジック変更・閾値変更・gate追加は **今回は凍結**。

**全体判定**

- **CONSENSUS REACHED**