全体判定: `CHANGES_REQUESTED`

**Fact**
- Round 3 までの Critical 2 件は解消されています。  
`slots_consumed_in_epoch` への置換: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L154)  
シグネチャ統一 + caller 反映: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L108) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L227) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L321)
- lock 方針、`MARGIN_DAYS`、3段階移行の追記も反映済みです。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L415) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L90) [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L401)

**Interpretation**
- Round 1-3 の Critical 群は実質クローズできています。
- ただし、実装者が誤読しうる新規の設計矛盾が残っているため、最終承認はまだ早いです。

[Critical]
- 該当なし（Round 1-3 起因の Critical は解消）。

[Warning] 移行方針の記述が自己矛盾
- 「T059 PR では `run_ga.py` から呼ばない」とある一方で、同文書内に `run_ga.py` 組込み例と変更対象表が残っています。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L403)  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L355)  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L321)  
修正提案: Phase 1/2 の「この PR で触るファイル」を明示分離し、`run_ga.py` 例は Phase 2 セクションへ移動してください。

[Warning] lock timeout 仕様が未閉包
- `LOCK_NB` 取得失敗時の処理が `...` のままで、10秒 timeout 契約がアルゴリズム化されていません。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L179)  
修正提案: 「再試行間隔」「締切時刻」「timeout 例外名」を擬似コードで確定してください。

[Warning] `EpochDatasetMismatch` が上位ハンドリングから漏れ
- 予約時に raise される例外を except 節が拾っていません。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L189)  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L322)  
修正提案: `EpochDatasetMismatch` を reserve 失敗ハンドリングに含め、運用ログを一貫化してください。

[Suggestion] `run_id` 重複予約ガードを明記
- 現在の不変条件だと重複 `run_id` で上書きとカウンタ不整合の余地があります。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L205)  
修正提案: `if run_id in run_records[current_epoch]: raise DuplicateRunIdError` を追加してください。

判定理由: 過去 Critical は解消済みですが、上記 3 Warning は「実装分岐の混乱」につながるため、設計文書としてはもう一段の整合化が必要です。