# REJECTED: ターゲット層の読み違え (Codex Round 1 で発覚)

profile-optimize cycle 1/3 で本概念設計を起案したが、 Codex Round 1 design review で以下の前提誤りを指摘された:

1. `evaluate_all_bars` の 5.236s は **primitive 前計算 (signal 値 prefetch)** であり、 composite all-bars JIT の削減対象ではない
2. `compute_composite_at_bar_jit` 自体は profile tottime 0.392s (本番投影 116s = 1.9 分) のみで、 dispatch overhead 削減は ROI 小
3. clause 契約は 1-3 個で、 私のメモリ見積 (32 clauses) は前提不整合

→ cycle 1/3 のターゲットを **B (`_indicators.py` wilder_smooth + rolling_max/min Numba 化)** に切替。 詳細は `devnotes/20260505-1857-indicators_numba_jit/`。

参照:
- conceptual-review-round-1.md (Codex 指摘原文)
- profile_20260505_171107.txt (再分析対象 profile)
