**Fact（観察事実）**
- C-1 `AuxPairMidSeries` 判定: `REQUEST_CHANGES`  
  `searchsorted` 前提となる `raw_ts` の strict monotonic/unique を load 時に fail-fast する設計は妥当です。  
  ただし `pair_not_found` 分岐の `np.empty` が read-only 化されておらず、契約不一致です。`_to_epoch_ns` 擬似コードに `if False` が残っており、実装意図が曖昧です。
- C-2 `align_to -> aux_pair_mid_close` 判定: `APPROVE`  
  `side="left"` + `raw_ts[pos]==target_ns` は exact-match 判定として正しいです。`pos==size` は `in_range` で防御され、off-by-one はありません。forward-fill 不使用で look-ahead 抑止も維持されています。
- C-3 契約 swap (`aux_pair_bars` -> `aux_pair_mid_close`) 判定: `REQUEST_CHANGES`  
  方向性は正しいです。  
  ただし後方互換フィールド削除は `build_aux_bundle` の CSV 経路と既存テスト・呼び出し側の置換漏れリスクが高く、設計上の監査項目が不足しています。
- C-4 P5 書換 判定: `APPROVE`  
  P5 が `mid_close + bar_time` のみ消費という前提なら semantic equivalence は成立します。NaN 伝播も「miss -> NaN」の設計で一致します。
- C-5 parallel/pickle 判定: `INCONCLUSIVE`  
  `numpy` 配列自体は picklable です。  
  ただし read-only flag が worker 復元後も維持されるかは実測確認が必要です（設計書に検証項目が不足）。
- C-6 phase marker 分割 判定: `APPROVE`  
  raw index 構築フェーズと align 後フェーズを分離して観測する方針は妥当です。
- C-7 テスト計画 判定: `REQUEST_CHANGES`  
  主要ケースは押さえていますが、strict-match 境界（`pos==size`, `target<first`, `equal last`, `duplicate fail-fast`）と pickle roundtrip、CSV 経路保全が不足です。
- C-8 smoke 判定: `INCONCLUSIVE`  
  検証方針は妥当ですが、`best genome 完全一致` は並列実行で不安定化し得るため pass/fail 指標としては脆いです。

**[Critical]**
- 契約削除の波及監査不足（C-3/C-7）  
  修正案: `aux_pair_bars` 参照箇所を「コード・テスト・CSV loader・report生成」まで対象にしたチェックリストを設計に明記し、最低1本 `CSV build -> align -> P5` 統合テストを追加。
- `pair_not_found` 空配列の read-only 契約欠落（C-1）  
  修正案: 空配列生成ヘルパを作り、常に `setflags(write=False)` を適用。
- `_to_epoch_ns` 実装契約の曖昧さ（C-1）  
  修正案: float 経路を完全削除し、整数式を固定（`days/seconds/microseconds` から ns 計算）して単体テストで固定値検証。

**[Warning]**
- read-only flag の pickle 復元挙動が未検証（C-5）  
  修正案: `pickle.dumps/loads` 後の `arr.flags.writeable` を検証するテストを追加し、必要なら worker 側で再 freeze。
- golden を `allclose` で比較すると NaN/bit差を見逃す可能性（C-4/C-7）  
  修正案: `np.testing.assert_array_equal`（NaN 同位置を許容する比較ロジック）で bit-level 同等性を検証。
- smoke の合格条件が過度に厳密（C-8）  
  修正案: `P5 golden一致 + live_criteria判定一致 + RSS削減量` を主判定にし、`best genome 完全一致` は参考指標へ。

**[Suggestion]**
- `epoch_ns` は M1 では過剰精度ですが、`raw/target` の単位 SSOT を守る意味で維持は合理的です。
- `align_to` の exact-match 契約を docstring に明文化し、`forward-fill禁止` を明示して将来改変を防ぐと安全です。

**特に確認事項への回答**
- 1) `searchsorted(left)+equality` は正しいです。`pos==size` も安全です。  
- 2) `_to_epoch_ns` 整数経路は必要です。M1でnsは過剰だが契約一貫性のため妥当です。  
- 3) bit-identical は「同一演算順序・同一型変換」なら成立見込み。テストで `array_equal` を必須化すべきです。  
- 4) 契約 swap の全置換漏れは高リスク。削除自体は可ですが監査テスト必須です。  
- 5) CSV 経路破壊リスクは現時点で未否定。統合テスト追加まで `INCONCLUSIVE`。  
- 6) read-only と pickle は `INCONCLUSIVE`。roundtrip テストで確証を取るべきです。

**全体判定**
- `CHANGES_REQUESTED`  
  方向性は適切で、設計の核（columnar化・exact-match・P5等価）は良いです。  
  ただし契約移行監査と境界テストを補強しないと、後退リスクを十分に潰し切れていません。