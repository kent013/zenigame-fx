# 最終改善計画: Run 10 → Run 11

## 合議ステータス: CONSENSUS REACHED (Round 1, --repeat 圧縮モード)

合議ループは時間制約により 1 ラウンドに圧縮。Codex 独立分析（analysis-codex.md）と Claude 自己分析（analysis-claude.md）の方向性が完全に一致しており、追加合議の効用は低いと判断。

## cycle_focus

`mixed`: TODO 由来 1 件 + GA 分析の含意確認

## 確定施策一覧

| # | 施策名 | 内容 | 変更対象 | 優先度 | 変更分類 | target_metric | failure_mode | causal_path | falsification | success_criterion | 合議結果 |
|---|--------|------|---------|--------|---------|--------------|-------------|------------|---------------|-------------------|---------|
| C1 (T031) | Stage A trade_count feasibility 制約 | regime-participation-constraint Phase 1: trade_count=0 を selection_score の feasibility 要素で淘汰 | `src/alpha_factory/config.py`, `config/alpha_factory/default.yaml`, `scripts/alpha_factory/run_ga.py`, `scripts/alpha_factory/generate_run_report.py`, `tests/scripts/test_alpha_factory_run_ga.py` | Critical | Structural（新ガード追加） | trade_count, total_pnl | trade_count=3 集中 / A→B 遷移率ゼロ | feasibility 制約がない → trade_count=0 個体が淘汰されず A pass の大半を占める → B-pass=0 が固定化 | RPC 導入後も Stage A pass 個体の trade_count 分布が下限 1 未満集中のまま、または B-pass=0 が継続 | Run 11 で Stage A 通過個体の trade_count 中央値が 5 以上、または B-pass≥1 個体出現 | APPROVED |

## 却下された提案

| # | 提案 | 却下理由 |
|---|------|---------|
| - | T031 以外の TODO 同時着手 | 1 サイクル変更箇所最小化、T031 単独の効果測定を優先 |
| - | live_criteria 緩和 / Stage 期間調整 | 禁止事項 1, 4 違反 |
| - | trade_count を直接 fitness に組み込む（罰則化） | 禁止事項 6 と区別が曖昧、構造的制約（feasibility）として導入する方が筋が良い |

## 保留事項（次 Run 検証申し送り）

| # | 仮説 | 最小変更案 | 検証条件 |
|---|------|----------|---------|
| H1 | RPC 導入で B 全滅の根本要因が exposed される（feasibility だけでは B-pass 出ない） | T035（B reason_codes 集計）を次サイクルで採用 | Run 11 で B-pass=0 のまま、かつ trade_count 分布が改善している |
| H2 | active_clause=0 への収束は単純式の探索空間優位ではなく初期 primitive 偏在が主因 | T037（clause 発火カウンタ）を 2-3 サイクル後に採用 | Run 11/12 で n_nodes 分布が依然 2 集中 |

## 次フェーズへの申し送り

T031 詳細設計は `devnotes/20260425-0937-regime-participation-constraint/detailed-design.md` を SSoT として使用。Phase C-1 では当該ファイルを参照リンクするのみで再設計しない。Phase 3 (implement) では T031 既存設計通りに実装する。
