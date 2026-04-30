全体判定: `CHANGES_REQUESTED`

**Fact**
- `run_records` 入れ子辞書化、`_normalize_dt` 導入、`dataset_cfg` hard guard、`reset` 3-flag + audit 追加は確認できました。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L118)  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L166)  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L358)
- ただし同ドキュメント内で整合性が崩れている箇所が残っています。

**Interpretation**
- Round 2 の主要指摘は大半が解消済みです。
- しかし `max_runs/epoch=6` 契約を壊す仕様変更が入っており、ここは Critical です。

[Critical] `max_runs/epoch` の意味が崩壊  
- 現在の説明だと `runs_in_current_epoch` は `status=="started"` のみカウントで、completed/failed を cap から除外しています。これだと同一 epoch で実質無制限に run できます。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L149)  
修正提案: `runs_in_current_epoch` は「その epoch で予約済み回数」の単調増加カウンタに戻し、status とは分離してください（例: `slots_consumed_in_epoch`）。

[Critical] 仕様記述のシグネチャ不整合  
- `reserve_run_slot(run_id, *, dataset_cfg)` に変更した一方で接続例は `reserve_run_slot(run_id)` のままです。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L167)  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L319)  
- `_load_state_or_init(dataset_cfg)` 呼び出しに対し、定義は `_load_state_or_init(self)` のままです。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L178)  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L226)  
修正提案: 呼び出し側・定義側を1つの最終シグネチャに統一してください。

[Warning] lock 仕様の矛盾  
- 本文は「1 Run 終了まで他 Run は lock 待ち」とありますが、擬似コードは reservation 中だけ lock を保持しています。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L403)  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L171)  
修正提案: 「短時間クリティカルセクションのみ排他」に文言を修正してください。

[Warning] `MARGIN_DAYS=7` が本文ロジックに未反映  
- 改訂表には追加済みですが、実際の設計本体では `timedelta(weeks=1)` のままです。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L250)  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L431)  
修正提案: 本文コードも `MARGIN_DAYS` 定数参照に統一してください。

[Warning] T059 を 24m 有効化なしで通せる、という記述が hard guard と衝突  
- `dataset_cfg != current_window` で abort するなら、現行 6m config では実行不能です。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L182)  
[default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml#L8)  
修正提案: 「T059 実装は可能だが runtime 有効化は24m PRと同時」を明記するか、暫定モード（abortではなく明示 skip）を定義してください。

[Suggestion] 文書メタ更新  
- タイトル・最終更新表示が Round 3 に更新されていません。  
[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L1)  
修正提案: Round 3 表記へ更新してレビュー履歴と一致させてください。

残課題は上記 2 Critical を閉じれば、承認にかなり近いです。