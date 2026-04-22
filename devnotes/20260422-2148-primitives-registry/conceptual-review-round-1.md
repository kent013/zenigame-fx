VERDICT: NEEDS_REVISION
REASONS:
- `required_data` を導入すると述べつつ、`compute / evaluate` 契約が `bars, idx, params` しか受け取らないため、`("ohlc", "atr")` や `("ohlc", "vix_daily")` のような非 OHLC 系列を実際にどう渡すかが未定です。宣言だけ先に固定すると、T010-b/T010-c で契約破壊的な見直しが発生しやすく、後戻り回避の観点で弱いです。
- `PrimitiveDomain = generic / pair_specific` を正式化する一方で、`RegistryEvaluator` と `compute` 署名に pair 固有文脈を渡す場所がありません。`pair_specific` を名前だけ先に確定し、実行契約が generic 前提のままだと、後続で evaluator 側の大きな再設計が必要になります。
- category 語彙を docs 側 4 値に寄せ、GA 側 2 値 slot との対応を移行 TODO に先送りしている点は、評価軸 5 の「既存コード資産の整合」に対して不十分です。骨格段階で少なくとも「正式 category と GA slot の対応契約」を同時に固定しないと、`_dummy_registry` と正式 registry の二重管理が長引きます。
- `required_data` を単なる `tuple[str, ...]` として自由記述にしているため、後続 32 primitive 実装で語彙ゆれが起きやすいです。missing-data 検査の基盤にしたいなら、骨格段階で最小限の canonical vocabulary か命名規約を決めるべきです。ここを曖昧にすると、後続 TODO の受入後に統一修正が必要になります。
- 受入基準の `既存 333 tests + 1 skip が維持` は verifiable ですが、設計受入基準としては脆いです。全体件数は外部要因で変動しうるため、この TODO の成立条件としては「対象テスト群」「契約テスト」「型チェック」のような局所的基準に落とした方が後続レビューで判定しやすいです。
- イントラデイ / ロングショート / コスト反映の絶対制約には直接違反していません。ただし本 registry が将来の primitive 契約を固定する層である以上、少なくとも「これらの制約を阻害しない contract になっているか」の検証が必要です。現状は特に `required_data` と evaluator 文脈不足のため、制約非違反を積極的に担保できていません。

REVISION_ITEMS (NEEDS_REVISION の場合のみ):
- [R1] `PrimitiveSpec.compute` と `RegistryEvaluator.evaluate` の入力契約を再定義し、`required_data` で宣言した系列を受け取れる `EvaluationContext` ないし `DataBundle` を導入すること。少なくとも `bars` 以外の補助系列を渡せる設計を骨格で固定する。
- [R2] `pair_specific` primitive が必要とする文脈を明示すること。例: `pair`, `quote/base`, `session calendar`, `pip/point metadata` など。不要なら `pair_specific` 導入自体を後続へ延期し、骨格では `generic` のみに絞る。
- [R3] GA 側 slot 語彙と primitives-registry 側 category 語彙の対応表を「後続 TODO」ではなく本設計の正式契約に含めること。少なくとも `slot_from_category(...)` 相当の責務と受入基準を先に固定する。
- [R4] `required_data` の語彙を完全 enum まで行かなくてもよいので、最小限の canonical naming rule を定めること。例: `ohlc`, `atr`, `spread`, `calendar`, `macro.*` のような名前空間規約。
- [R5] 受入基準を局所化すること。全体テスト件数固定ではなく、「新 registry 契約テスト」「GA 側との対応表テスト」「mypy/ruff clean」のように、この TODO 単体で判定可能な基準へ置き換える。
- [R6] import 副作用登録を後続に送るなら、本 TODO の時点で「明示的 bootstrap を採るのか、副作用 import を採るのか」を方針決定しておくこと。少なくとも production path で登録漏れをどう検出するかを受入基準に含める。

NOTES:
- 骨格だけにスコープを絞る判断自体は妥当で、North Star からの逸脱ではありません。問題は「骨格で固定する契約」が後続の directional/modulator/pair-specific 実装を十分に受け止める形になっていない点です。
- `_dummy_registry` をこの TODO で触らない判断も妥当ですが、その代わり二重管理期間を短く保つための接続契約は今ここで強めるべきです。
- 禁止事項 1, 2, 3, 4, 6, 7 への直接違反は見当たりません。主な懸念は「後続で contract を壊して設計をやり直すリスク」です。