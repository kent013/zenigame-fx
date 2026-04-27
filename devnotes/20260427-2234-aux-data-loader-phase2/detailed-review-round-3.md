**前提（この Round 3）**
- `verified`: 本レビューは「設計書改訂の妥当性レビュー」であり、実装コードの存在確認は対象外。
- `verified`: Round 1 指摘への対応は、提示された改訂マトリクスの内容を根拠に評価。
- `unverified`: 改訂本文（detailed-design.md の実際の記述全文）と実装差分は未確認。

**C9 Falsification-first（設計レベル反証）**
- 反証1: 空 `bars` / align再計算問題は未解消ではないか。  
  結論: `if not bars` 早期 return + `AuxAlignmentCache` 追加で設計上は反証成立せず。
- 反証2: migration portability / 月次lag不整合は残るのではないか。  
  結論: SQL直書き→Python backfill + series別lag により設計上は解消方向。
- 反証3: preflight が Stage B 不足・stale見逃しのままではないか。  
  結論: `extended_period` と coverage/freshness 指標追加で大幅改善。設計としては妥当。
- 反証4: 運用回帰（DEFAULT_SERIES落ち、再実行性不足）が残るのではないか。  
  結論: wrapper完全列挙 + assert test + step別ログで設計上は対策済み。

**施策判定（設計書ベース）**
1. 施策1: `APPROVE`  
2. 施策2: `APPROVE`  
3. 施策3: `APPROVE`  
4. 施策4: `APPROVE`  
5. 施策5: `APPROVE`  
6. 施策6: `APPROVE`  
7. 施策7: `APPROVE`  
8. 施策8: `APPROVE`  
9. 施策9: `APPROVE`  

**新規 Warning（設計レベル、非ブロッカー）**
- [Warning] `latest_effective_from >= extended_start` は freshness 条件としては弱め。実装時に「`extended_end` 近傍 freshness」も併記すると安全です。
- [Warning] `AuxAlignmentCache` は key（instrument/stage/bar-range/as_of_strict）と invalidation 条件を明文化すると事故を防げます。
- [Warning] `_normalize_bar_time` で丸め衝突が起きた場合の fail-fast 契約（重複検出）を1行入れると堅いです。

**全体判定**
- **`APPROVED`（設計書として）**  
Round 1 の Critical 7件は、提示された改訂方針で設計レベルでは妥当に塞がれています。上記 Warning は実装時チェック項目として扱えば十分です。