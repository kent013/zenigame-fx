**観察事実**
- Run-14 は `WF 60/10` へ短縮後、`insufficient_folds=100%` は解消した一方で、`Stage A pass=0%` となり全個体が Stage A で落ちた。
- 直前 Run-13 の calibrate 由来 `gate=0.4172` を、別分布（WF 60/10）にそのまま適用している。
- Run-10〜13 の推移では、gate 上昇に伴い A_pass は `73% → 40% → 22%` と低下しており、Run-14 で 0% まで落ち切った。

**解釈（C9 falsification-first）**
- まず反証対象: 「WF短縮そのものが悪い」  
  反証手順として、同じ `WF 60/10` のまま gate を開放して A_pass 回復有無を確認すべき。
- 現時点の最有力因果は「WF変更後の分布に対し、旧WFで校正された gate が過剰」。
- したがって、今サイクルで最も検証力が高いのは、WFを固定し gate だけを外すアブレーション。

**推奨案（1件）**
- **案A**を採用: `stage_a.threshold=0` に一時リセットし、**1サイクルは calibrate-gate を凍結**。  
  理由:
  - `config-only` で即日実行可能（最短復旧）。
  - 原因仮説（gate過剰）を直接反証できる。
  - 失敗しても「WF短縮側の問題」が切り分けできる。

- 禁止事項照合:
  - 「仕組みが機能していない段階で値を弄るな」に抵触しない。これは最適化チューニングではなく**機能回復のためのベースライン復元**。
  - C6（Fact/Interpretation分離）・C8（INCONCLUSIVE許容）・C9（反証先行）に整合。

- 今サイクル実行仕様:
  - `target_metric`: `Stage A pass率`（主）、`best_fit`/`pnl`（従）
  - `failure_mode`: `A_pass <= 5%` または `best_fit` が Run-13 比で極端悪化
  - `causal_path`: `WF変更 -> fitness分布変化 -> 旧gate過剰 -> Stage A全滅`
  - `falsification`: gate=0でもA_passが回復しないなら上記因果を棄却
  - `success_criterion`: `A_pass >= 20%`（最低復旧ライン）、かつ `Stage A 全滅` 再発なし

**全体判定**
- **Cycle 4 の最善は案A**。  
- 案Bは恒久対策として次段（Aで回復確認後）に実装、案CはA失敗時の退却線として保持。