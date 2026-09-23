# 分析 (cycle 18): dd厳格化 5%→3% (初の funnel-binding な dd 引き上げ)

## 前提
cycle17 R99: dd厳格化 20%→5% は R98(dd20%) とビット同一 = in-loop 安全だが hollow (達成 dd max2.676% を全く拘束せず)。Codex ガイダンス「5%合格後に3%」。

## 観察事実（Facts）
- R99 StageC (n=634) dd_pct: p50 1.48 / p90 1.79 / p99 2.08 / **max 2.676**。全 634 が dd≤3% (dd<=2%:621)。
- ★ Stage B passer (funnel) dd_pct: p50 1.77 / p90 2.93 / **max 6.90**、**dd>3%: 175/2010**、dd>5%: 1。
- → dd5% は funnel から 1 個体しか除外しない (∴ビット同一)。**dd3% は 175 個体 (dd 3-5%) を選抜から除外** = 初の funnel-binding な dd 引き上げ。

## 解釈・推論（Interpretations）
### 1. dd3% は dd5% と異なり in-loop で実際に作用する
達成 StageC は全て dd≤2.676% (3% クリア) だが、進化途中の Stage B 個体 175 が dd 3-5%。dd3% gate はこれらを選抜から外す → funnel が変わる (dd5% のビット同一とは異なる)。これが dd 軸で初の「意味ある (binding) 引き上げ」。

### 2. 崩壊 vs 安全の二仮説
- 安全: StageC 産出系統は全て dd≤2.676% (低 dd)。dd 3-5% 個体が stepping stone でなければ、除外しても StageC 634 維持。
- 崩壊: dd 3-5% 個体が探索の踏み石なら、除外で funnel 縮小・StageC 減少 (74k 同型の in-loop 効果が dd 軸で初発現)。
- 切り分け: R100 (seed70, dd3%) vs R99 (seed70, dd5%, StageC634) 反実仮想。

## 次サイクル候補
- **[Critical] dd5%→3% 引き上げ、R100 seed70 反実仮想で in-loop 検証**。判定:
  - StageC≈634 維持 → dd3% 安全 = 意味ある dd 引き上げ成功 → 採用、さらに dd 2.5%/2% へ詰めて dd in-loop 天井を探索。
  - StageC 顕著減少/崩壊 → dd3% が funnel-binding で破壊的 → dd in-loop 天井は 3-5% 間。dd5% を validated frontier 確定し別軸へ。
- **[Warning] post-hoc 信仰禁止 (74k教訓)・in-loop 検証必須**、3 seed 非崩壊で正式採用。

## 全体判定
**dd5% は安全だが hollow (ビット同一)。dd3% は Stage B funnel の 175 個体を拘束する初の binding な dd 引き上げ** → in-loop 効果が dd 軸で初めて問われる。R100 (seed70, dd3%) で R99(dd5%, StageC634) との反実仮想により安全/崩壊を切り分け。安全なら意味ある閾値引き上げ成功、崩壊なら dd in-loop 天井 3-5% 確定。
