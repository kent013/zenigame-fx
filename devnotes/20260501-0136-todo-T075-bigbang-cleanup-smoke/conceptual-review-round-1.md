## Verdict
NEEDS_REVISION

## 前提 (C4)
- `verified`: 提示本文から、T075 は `Phase 1 = 純ライブラリ + 単体テスト`、`Phase 2 = run_ga.py adapter`、`read-only`、`SmokeDoDStatus = pass/fail/inconclusive`、`5 run 連続検証`、`dual-path 並走禁止` を意図している。
- `verified`: 提示本文上、T075 は `FM1-FM5`、`RollbackDecision 3値`、`DeletionTarget`、`SmokeDoDResult` を新規 SSOT として置こうとしている。
- `unverified / INCONCLUSIVE`: synthesis §12.1-12.4 / §16 / §18.3、T071-T074、synthesis §11.2 の原文はこのターンでは未提示。したがって「条文どおりか」の断定はできず、以下は「設計破綻リスク」と「本文内自己矛盾」を中心に見ている。
- `falsification-first`: まず「この設計のままだと SSOT 逸脱・責務混線・数値先行が起きる」点を優先して反証した。

## Critical (必修正)
- [C1] **T075 が親 SSOT を“参照”でなく“再定義”している。**
  Fact: 本文に `FM1-FM5 (T075 で SSOT 定義)`、`new_cascade 名前空間は採用しない (Round 22 改訂候補)` とある。  
  Interpretation: 「T058-T074 全17設計」と「synthesis」は `T075 で touch しない` 前提なのに、T075 側で意味論を起こしている。T075 は `親 SSOT の local projection` に下げるべきで、親条文の改訂が必要な点は `dependency / blocked-by` として明示しないと C1 違反になる。

- [C2] **DoD8 の責務配置が破綻している。**
  Fact: `SmokeDoDResult.items` は `DoD1-DoD8 全網羅`、一方で `FiveRunConsistencyResult` が別にあり、DoD8 は epoch 汚染で 5 run 依存とされている。  
  Interpretation: `1 run で確定できる DoD` と `5 run 集約でしか確定できない DoD` が同じ `SmokeDoDResult` に入ると API 意味論が曖昧になる。`PerRunDoDResult(DoD1-DoD7)` と `CrossRunDoDResult(DoD8)` を分離するか、DoD8 は per-run では常に `inconclusive` とする規約を SSOT 化すべき。

- [C3] **FM threshold をこの段階で SSOT 化するのは不適切。**
  Fact: `FM1=0.3, FM3=2, FM4=0.7, FM5=0.5` を「T075 設計判断値」として置いている。  
  Interpretation: これは「仕組みが機能していない段階で値を弄るな」「数値操作禁止」に正面衝突する。しかも 5-run smoke は `n=5` で、閾値校正の根拠として弱すぎる。T075 Phase 1 では `threshold-free classification` か `manual review required` に留め、数値確定は別レビューに切り出すべき。

- [C4] **`evaluate_rollback_decision` の truth table が硬すぎて危険。**
  Fact: `FM1 and FM4 -> rollback`, `FM1 xor FM4 -> delay_one_cycle`, `その他の fail も delay_one_cycle` と定義している。  
  Interpretation: 単独 FM1 または単独 FM4 が重篤でも自動 rollback に到達できない。`DoD hard fail` も FM に畳み込まれて delay 扱いになり得る。少なくとも `severity` か `hard_fail` 軸を分け、`rollback` は `FM1/FM4 の同時発火` だけに固定しない方がよい。

- [C5] **`observability_metrics_snapshot: Mapping[str, Decimal]` は SSOT 漏れの温床。**
  Fact: status field 方式継承を掲げつつ、実データ側で untyped な数値辞書を持っている。  
  Interpretation: これは `scaffold 数値 field なし` と緊張するだけでなく、`値伝搬漏れ` を起こしやすい。T071 の SSOT に従うなら、ここは `typed projection` か `report_ref + schema_version` に絞るべきで、自由形式の `Mapping[str, Decimal]` は避けるべき。

- [C6] **削除対象が“代表例のみ”では big-bang cleanup の設計として不足。**
  Fact: `DeletionTarget tuple は代表例のみ、詳細設計で全網羅` と読める。  
  Interpretation: T075 の主題が `旧 path 削除 + smoke` である以上、概念設計段階でも `全件列挙の生成手順` と `受入条件` は必要。最低でも「各 target が synthesis §12.1/12.2 のどの条文に対応するか」を 1 対 1 で持つ規約まで書かないと、同日削除の網羅性を担保できない。

## Warning (要検討、 詳細設計で解消可)
- [W1] **`new_cascade` 非採用の判断自体は成立し得るが、T075 本文だけでは理由が足りない。**  
  T058-T074 で既に採用していないなら、T075 は「なぜ非採用で一貫したのか」を後付けで要約すべきで、単に `Round 22 改訂候補` とするだけでは弱い。

- [W2] **`1 cycle = 7 days` は運用 cadence 未固定なら早い。**  
  `ROLLBACK_DELAY_CYCLE_DAYS=7` は、現時点では `delay_one_cycle` の実装詳細に見える。概念設計では `1 cycle` のまま保ち、日数化は run cadence SSOT 側に寄せた方が安全。

- [W3] **`dual-path 並走禁止` と `旧実装の同居` の境界定義が必要。**  
  「ソースツリーに残る」こと自体は並走ではなく、「runtime から到達可能」「feature flag で切替可能」「同じ出力契約を二経路で生成できる」ことが並走、という operational definition を置くとぶれない。

- [W4] **`RollbackTrigger = Literal["FM1","FM4"]` と `trigger_fms: frozenset[FailureModeKind]` の粒度が混在している。**  
  `observed_fms` と `rollback_relevant_fms` を分けた方が型が明確になる。

- [W5] **`SmokeDoDItem.dod_id: Literal["DoD1"-"DoD8"]` は API SSOT として粗い。**  
  Python の Literal としては成立しない表記なので、`Literal["DoD1", ..., "DoD8"]` を明記した方が §11.2 的に安全。

- [W6] **collider bias 規範は「継承」だけでなく non-goal が要る。**  
  T075 では `stratified audit を判定しない`、`因果解釈を返さない`、`比率差は observability 上の検知に限定` まで書くと T072-T074 と衝突しにくい。

## Suggestion (改善案)
- [S1] **SSOT の書き方を修正する。**  
  `T075 で SSOT 定義` ではなく、`T075 local normalization of synthesis/T071-T074 identifiers` と表現を落とす。親 SSOT 改訂が必要な点は `Requires synthesis Round 22 before merge` とする。

- [S2] **DoD を二層に分ける。**  
  `PerRunSmokeDoDResult` と `CrossRunSmokeDoDResult` を分け、`BigBangCleanupReport` が両者を束ねる構造にすると責務が素直になる。

- [S3] **FM 判定を “数値閾値” ではなく “evidence class” で始める。**  
  例: `hard_evidence / warning_evidence / inconclusive`。閾値は後続 TODO で校正し、T075 は evidence を収集・整形する役に留める。

- [S4] **削除対象は dataclass より manifest 規約を先に置く。**  
  `path, category, source_section, source_clause, removal_mode, owner` 程度の最小 manifest 規約を決めると、詳細設計で grep/dump 手順に落としやすい。

- [S5] **rollback は 3値維持でもよいが、条件は 2段階化する。**  
  `classify_smoke_outcome` と `decide_release_action` を分ける。前者は事実認定、後者は運用判断。Fact / Interpretation 分離にも合う。

## Approved 部分
- `Phase 1 = 純ライブラリ、Phase 2 = run_ga.py adapter` の分離は妥当。big-bang 切替の前に read-only 検証器を作る順序は良い。
- `SmokeDoDStatus = pass/fail/inconclusive` は、C8 INCONCLUSIVE と整合している。
- `early gate ではない / read-only` を invariant に置いているのは良い。T075 が runtime 制御に侵食しない境界が明確。
- `dual-path を長期間残さない`、`切替コミット 1-shot` の方向性自体は、使命と cleanup の趣旨に合っている。
- `status field 方式継承` を明示している点は正しい。ただし数値辞書への逃げ道は塞いだ方がよい。

## 学術文献 (任意)
- Bailey 系は、閾値校正や smoke 成否から性能一般化を強く言い過ぎないための参照として置くのは有効。特に「少数 run から強い性能結論を出さない」補強に向く。
- Lo の Sharpe 関連は、5-run smoke を性能評価や改善証明に使わないための牽制としては有効。ただし T075 の主目的は release safety なので、本文中では補助参照に留めるのが適切。
- rollback 戦略は学術より SRE / release engineering の実務知見の方が近い。T075 では「自動復旧条件」より「自動昇格させない条件」を先に明記する方が設計に合う。

## 総評
現状案は方向性自体は悪くありません。特に `read-only smoke checker`、`inconclusive 許容`、`Phase 1/2 分離` は堅いです。ただし Round 1 の反証観点では、`親 SSOT の再定義`、`DoD8 の責務混線`、`閾値の先行 SSOT 化`、`rollback 条件の過度な単純化` の4点が強い破綻候補です。ここは詳細設計ではなく、概念設計の段階で直しておくべきです。

結論として、T075 は「cleanup/smoke を司る設計」である以上、数値で賢く判定するより、まず `何を事実として観測し、どこまでを T075 が決め、どこからを上位 SSOT / manual review に委ねるか` を引き直した方がよいです。その修正が入れば、以降の詳細設計はかなり安定します。