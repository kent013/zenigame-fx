全体判定は **CHANGES_REQUESTED** です。Round 1 の主要論点はほぼ解消できていますが、1点だけ実装前に潰すべき Critical が残っています。

**[Critical] cache key が `bar_time` のみ**
- Facts: 設計では cache hit 条件が `cache_valid && bar.bar_time == cached_bar_time`。一方で依存マトリクスでは `equity` が `bar.bid.close / bar.ask.close` に依存。
- Interpretations: 同一 `bar_time` で価格が異なる bar が入力される経路（重複タイムスタンプ、再サンプリング、データ補正）があると stale snapshot を返し得ます。Round 1 の invalidation 網羅性観点で未解消です。
- 修正提案: cache key を `bar_time` 単独でなく `bar_identity`（例: `id(bar)`）か `bar_time + bid.close + ask.close` に強化し、`同一時刻・異価格` の回帰テストを追加。

**[Warning] 前提の未検証項目が実装ゲートに落ちていない**
- Facts: P4/P5/P6/P7/P8 は `To verify in detailed design` のまま。
- Interpretations: C4 の運用としては良い整理ですが、未検証のまま実装着手できる状態です。
- 修正提案: 「実装開始条件チェックリスト（全 To verify を Verified 化）」を成功基準に追加。

**[Warning] Position mutation ガードの test 手法**
- Facts: static grep ベースの検出を提案。
- Interpretations: rename・間接代入・将来リファクタで漏れやすいです。
- 修正提案: 静的チェックに加えて、ランタイムで `snapshot.positions` の参照整合性を検証するテストを1件追加。

**[Suggestion] C8(INCONCLUSIVE) の明文化をもう一段**
- Facts: n=1 警告は明記済み。
- Interpretations: 良化していますが、performance verdict の判定条件がまだ「目標未達=失敗」に寄りやすいです。
- 修正提案: 「selection invariance が満たされ、性能は n 不足なら INCONCLUSIVE」を明示。

---

ご指定の6観点への回答です。

1. **C3/C4 解消性**: 概ね解消。ただし上記 Critical（key 粒度）で stale 反証余地が残る。  
2. **P1-P8 追加要否**: 追加推奨あり。`P9: cache key が snapshot 依存変数を十分に識別する`。  
3. **依存マトリクス漏れ**: field 漏れはほぼ無し。trigger 側で「同一時刻・異価格」の扱いを補強すべき。  
4. **新規8テスト十分性**: 大枠十分。`duplicate timestamp with different prices` ケースを追加すると完成度が上がる。  
5. **follow-up TODO 明示**: 十分。加えて「再着手条件（shadow一致率100%など）」を定量化するとよい。  
6. **C7/C8 反映**: C7 は適切。C8 は改善済みだが、INCONCLUSIVE 条件を判定文に明示するとより準拠。