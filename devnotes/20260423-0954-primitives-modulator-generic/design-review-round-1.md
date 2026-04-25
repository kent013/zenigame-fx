判定は **NEEDS_REVISION** です。  
反証優先で見たとき、現状設計のままでは「look-ahead 回避」と「FX ペア横断の妥当な探索範囲」に未解決点があります。  
対象: [detailed-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260423-0954-primitives-modulator-generic/detailed-design.md)

**Must-fix**
1. **M1 の `threshold/scale` 範囲が設計本文の根拠と矛盾**  
Fact: 本文に「USDJPY 時間足 ATR は 0.05-0.5」とある一方、`threshold high=0.02`, `scale high=0.01`。  
Interpretation: JPY 系で実質飽和し、GA が有効探索できない。  
修正: `price-unit` 維持なら上限を大幅拡張、または ATR を pip/ADR 正規化してペア非依存化。

2. **M4 が `as_of` を使わず、look-ahead 防止を型だけで担保している**  
Fact: `EconomicEventSnapshot.as_of` は定義されるが `_m4_compute_all` 内で未使用。  
Interpretation: 「snapshot で as-of 制約」と書きつつ実行時には制約なし。将来イベントの事前既知性を過大評価するリスク。  
修正: 少なくとも `as_of` を実際に評価経路で使う仕様に変更。MVP近似を残すなら「厳密非対応」を DoD から外して明示。

3. **`_M4_WARN_FLAG/_M5_WARN_FLAG` がテスト順序依存を作る**  
Fact: module-level mutable flag は test 間で保持され、`pytest.warns` が不安定化し得る。  
Interpretation: test isolation 要件に抵触。  
修正: flag廃止で warnings フィルタ（`once`）に任せるか、テストで確実にリセット可能な API を用意。

4. **4段伝搬チェックの「consumer 参照」が実運用で未完了のまま通る設計**  
Fact: snapshot 未接続でも M4=1.0, M5=0.5 で継続。  
Interpretation: 伝搬漏れを隠しやすい（既知の再発パターン）。  
修正: production path では missing snapshot を fail-fast（例: evaluator strict mode）にし、テストで必須化。

**Should-consider**
1. M3 の「同一 bar の spread 使用」が実行タイミング契約に依存するため、`signal at close -> execute next bar` を仕様明記。  
2. M5 の datetime を tz-aware 前提でバリデーション（naive 混入時の `bisect` 比較例外回避）。  
3. F6 の `_SESSION_RANGES_UTC` 移動は、F6 出力同値の回帰テストを1本追加。  
4. `directional_generic.category_counts()` と registry 全体 count の意味差を docs に明記し誤用防止。

**観点別まとめ（1-9）**
1. API後方互換: **概ねOK**（kwargs前提）。  
2. look-ahead bias: **M1/M2/M5/M6は概ね妥当、M4は要修正**。  
3. registry整合: **設計上OK**。  
4. 数値安定: **概ねOK**。  
5. warning発出: **要修正**。  
6. ParamSpec range: **M1が要修正**。  
7. テスト網羅: **概ね良いが warning/strict伝搬の検証追加推奨**。  
8. F6移動: **大筋OK、回帰試験を追加推奨**。  
9. DoD達成可能性: **現状のままでは条件付き（strict伝搬未完）**。

参考文献（設計判断の根拠）: Wilder (1978) *New Concepts in Technical Trading Systems*、Lopez de Prado (2018) *Advances in Financial Machine Learning*、Harris (2003) *Trading and Exchanges*。