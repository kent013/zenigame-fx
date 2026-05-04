**前提（C4）**
- `verified`: Run-28でStage Aは`142/640`通過、Stage B/Cは`0`。
- `verified`: Stage A通過個体の`trade_count`は`median=55`、bestは`48`。
- `verified`: Stage Bで`fold_trade_count_min=10`未満が多数（`trade_count_below_min:7/8/9`中心）。
- `verified`: `live_criteria.trade_count_min=50`に対し、`stage_a.min_exposure_trade_count=1`。
- `inconclusive`: この乖離が「意図設計」か「不整合バグ」か（設計文書の明示根拠未提示）。
- `inconclusive`: primitive偏在・cross-pair差の定量（データ未提示）。

**Facts（C6）**
- Stage A改善の主因は閾値`0.0 -> -0.0172`（通過率が0%→22.2%）。
- Stage B失敗は実質2層:
  - 統計不足（fold成立不足、`all_folds_unavailable`含む）
  - 成立foldでも性能不足（`trade_sharpe_stage_b max=0.040 < 0.05`、`positive_fold_ratio max=0.5 < 0.6`）
- 低取引群（48-51）が上位に残る現象がある。

**Interpretations（C6）**
- I1は**有力だが単独根因ではない**。  
  理由: fold不足は説明できるが、fold成立後のSharpe/ratio不足は別問題。
- 禁止事項#6の兆候は**spuriousよりreal寄りの構造リスク**。  
  理由: 現行ゲートで低取引個体が生存しやすい。
- Stage B AND条件は厳しいが、現時点では「厳しすぎる」より「入力個体品質不足」の寄与が大きい。

**仮説ごとの反証可能性（C9）**
- H1: 「Stage Aの`min_exposure=1`がボトルネック」
  - 反証テスト: Run-29で`min_exposure=50`に同期（他固定）。
  - 予測: Stage A通過数は大幅減、`all_folds_unavailable`/`trade_count_below_min`は大きく減る。
  - 反証条件: それでもfold不足がほぼ同率ならH1棄却方向。
- H2: 「低取引bestは本物シグナル」
  - 反証テスト: 同戦略群のfold別Sharpe分布とpair別再現性を確認。
  - 反証条件: fold間・pair間で符号/順位が不安定なら偶然優位（spurious）寄り。
- H3: 「Stage B条件が主犯」
  - 反証テスト: まずH1実施後に失敗内訳再計測。
  - 反証条件: unavailable解消後も`median_oos_sharpe`不足が支配的なら、主犯は条件でなく信号品質。

**次サイクル候補**
- `Critical(1)`: `stage_a.min_exposure_trade_count`を`live_criteria.trade_count_min(=50)`へ同期（単一変更）。
- `Warning(2)`: Run-29でStage B失敗理由の再分解（unavailable由来か、Sharpe/ratio由来か）。
- `Warning(3)`: 低取引上位クラスター（48-51）のfold安定性監査（禁止事項#6の早期検知）。

**Q1-Q5への短答**
- Q1: 反証可能。上記H1テストで可能。予測は「A通過急減、fold不足減、ただし性能不足は残存可能」。
- Q2: 現状は**realな構造的萌芽**と判定（本物シグナル断定は不可、`INCONCLUSIVE`）。
- Q3: 1つに絞るなら**I1（min_exposure=50同期）**。
- Q4: 設計意図かバグかは**INCONCLUSIVE**。ただし運用上は不整合（実質バグ相当）として扱うのが妥当。
- Q5: cycle 2は「高情報量の単一変更」を事前登録し、反証条件を先に固定して評価する（今回ならI1）。

**全体判定**
- **CONCERN**（CRITICAL_DRIFTまでは未到達だが、#6の芽は明確に監視対象）。