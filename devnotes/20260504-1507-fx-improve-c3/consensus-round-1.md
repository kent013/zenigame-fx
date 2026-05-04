**結論（Run-30 の 1 本化）**  
`P1は APPROVE（ただし MODIFY 必須）`です。  
実行方針は「**calibrate-gate 系の自動適用経路を一時停止し、cycle 1 の閾値 -0.0172 を固定して再現性を検証**」に一本化してください。

**MODIFY が必須な理由（重要）**  
`run_ga.py` の優先順位が `CLI > history > yaml` なので、`enabled=false` だけでは `history` から閾値が上書きされうるためです。  
したがって P1 は次の意味で定義すべきです。  
- calibrate 停止  
- threshold 固定（-0.0172）  
- history 由来の自動適用をこの run では遮断（archive 伝搬漏れ防止）

---

Q1への回答  
- (a) 妥当です。振動源候補（自動制御）を止めるのは Falsification-first に合致します。  
- (b) これは「新規チューニング」ではなく「既知ベースラインへのロールバック実験」なので Structural 扱いでよいです。  
- (c) 反証条件は概ね十分ですが、`stage_a_pass` だけでなく **live_criteria 充足個体数** と **イントラデイ/両方向/swap-spread net 違反の有無** を同時判定に入れてください。`(b)` は INCONCLUSIVE 判定を許容する形にするのがC8準拠です。

Q2への回答  
妥当です。  
ただし現時点は「root cause **候補**」であり、確定ではありません（Run-29/30 の検証で確証化）。

Q3への回答  
妥当です。  
- (c) 支持時: dead-band/hysteresis/max_delta の設計改善へ進む  
- (a) 支持時: seed 固定で GA variance を先に定量化

Q4 最終確定  
Run-30 は以下で確定してください。  
**「calibrate-gate の自動制御を止め、閾値を -0.0172 に固定し、history 上書きを遮断した状態で 1 回検証する」**。  
これが「1仮説 + 1最小変更」に最も整合します。