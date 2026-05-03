**本分析の前提 (C4)**
- Verified: 提示された設計書とコード断片（`stage_gate.py` / `cross_pair.py` / `parallel_eval.py`）を根拠に評価。
- Unverified: C1で要求される `docs/devnotes` 実ファイル全文確認・`git log -S` 履歴追跡・全caller grepは、今回の「コマンド実行禁止」条件下では未検証。
- Verified: C3/C7対象の相関・因果claimは本設計内に実質なし（統計因果の新規主張なし）。

**Facts**
- 施策は責務境界（A'）を維持する意図で、canonical計算を`stage_gate.py`側に限定。
- `CrossPairResult`にsidecarを載せ、`evaluate_stage_c`でdual-pathログ後にsanitizeする設計。
- `_log_canonical_dual_path`は`pair_label`を任意引数追加で後方互換を狙う設計。

**Interpretations (反証優先)**
- いくつかの「厳密契約」が現状案だと未達です。特に sanitize の常時保証と識別子fail-fastの厳密性は修正が必要です。

---

### 施策1 `_PairSidecarInputs` + `CrossPairResult` field
**判定: APPROVE**
- [Warning] `frozen=True`でも`list/dict`は可変で、後段変更で観測値が変わる余地。  
  修正案: sidecar格納時に`tuple`化、または「不変前提」をテストで固定。
- [Suggestion] private型を他moduleからimportする契約をdocstringに明記（将来の循環依存再発防止）。

### 施策2 `_log_canonical_dual_path(pair_label追加)`
**判定: REQUEST_CHANGES**
- [Critical] `stage_label=="C_cross_pair"`時のfail-fastが`pair_label is None`のみ。空文字/空白を通す。識別子契約が不完全。  
  修正案: `not isinstance(pair_label, str) or not pair_label.strip()`でも`ValueError`。
- [Warning] 「51 caller後方互換」は実測未提示。  
  修正案: helper単体テストで全stageラベルの互換ケースを明示追加。

### 施策3 `_run_pair_sharpe` 3-tuple化
**判定: REQUEST_CHANGES**
- [Warning] `metric_unavailable`でsidecarを捨てるため、`3 entries/genome`観測目標と衝突し得る。  
  修正案: sidecarは保持し、`canonical_skipped_reason`付きでログ。
- [Warning] メモリ影響を`N/A`扱いは不正確（trades/equity/bars保持が増える）。  
  修正案: 設計書にワーカー当たり上限見積りを明記し、超過時はsidecar縮退。

### 施策4 `evaluate_cross_pair` sidecar集約
**判定: APPROVE**
- [Warning] `bars=list(pair_bars[pair])`を3ペア分保持するためピークRSS増分が出る。  
  修正案: `run_backtest`が非破壊ならコピー回避（参照渡し）を検討。
- [Suggestion] 「既存集約経路非干渉」を固定する回帰テスト（`metrics`キー完全一致）を強化。

### 施策5 `evaluate_stage_c` dual-path配線 + sanitize
**判定: REQUEST_CHANGES**
- [Critical] sanitizeが条件付きで`finally`保証ではない。「常にsanitize」の契約に対して脆い。  
  修正案: dual-path全体を`try ... finally`化し、`CrossPairResult`なら常に`replace(..., _shadow_sidecar_inputs={})`。
- [Warning] disabled modeでもper-pairで重い経路に入る設計余地がある。  
  修正案: `enabled=False`時は軽量ログ専用分岐に分離。
- [Warning] `pair`キー値の妥当性検証がない。  
  修正案: ループ内で`pair`非空チェックを追加し契約違反を早期検出。

### 施策6 18テスト追加
**判定: REQUEST_CHANGES**
- [Warning] B2/B3（メモリ予算）をmerge gateにするなら、少なくとも自動計測スモークを1本は必要。  
  修正案: CI外でも再現可能な計測テスト/スクリプトをテスト計画に組み込む。
- [Warning] `parallel_eval._extract_cross_pair_result`経由のsanitize非漏洩を直接検証する統合テストが不足。  
  修正案: Stage C→extractまでのE2Eテストを追加。

---

**横断判定（追加観点）**
- ルックアヘッドバイアス: **APPROVE**（新規未来参照経路は見当たらない）。
- メモリ制約 24GB/6worker: **INCONCLUSIVE**（設計上の増分はあるが実測証跡未提示）。
- パフォーマンス: **REQUEST_CHANGES**（canonical追加3回分の影響見積り・抑制策が不足）。
- C1/C2準拠度: **INCONCLUSIVE**（履歴grep・広域検索の実証は未提示）。

---

**全体判定: CHANGES_REQUESTED**  
主ブロッカーは 1) `pair_label` fail-fast厳密化、2) sanitizeの`finally`常時保証、3) メモリ/性能の検証計画強化 です。