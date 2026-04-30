[Suggestion] src/alpha_factory/primitives/modulator_generic.py:343 と src/alpha_factory/primitives/pair_specific.py:762  
`as_of_strict=True` 分岐で `np.searchsorted` でカットオフを求めていますが、その直後に `np.min(np.abs(available - t))` を計算しており、結局 prefix 全体を毎バー走査しています。これでは設計ドキュメントで狙っていた「bisect で O(log E)」の効果が出ず、イベント件数が多いケースでは従来同様に O(N×E) の計算負荷になります。`event_times` が昇順であることを利用し、`cutoff` 直前の要素（必要なら `cutoff` の先頭要素）だけを見て差分を計算するようにすれば、意図どおり O(1) で近傍イベントを評価できるので検討してみてください。

全体判定: APPROVED