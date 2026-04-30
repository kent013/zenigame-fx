全体判定: `CHANGES_REQUESTED`

**観察事実 (Fact)**
- [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L24) で `main@ea56484` 基準・`T058 未実装` を明示し、前提ズレは是正されています。
- [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L62) で epoch ID は `(start,end)` canonical に変更済みです。
- [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L149) で `reserve_run_slot` の単一原子的 reservation に統合されています。
- [calibrate_gate.py](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/calibrate_gate.py#L28) で既に `fcntl.flock` 運用実績があります。
- [default.yaml](/Users/ishitoya/repository/zenigame-fx/config/alpha_factory/default.yaml#L8) は現状 6m dataset のままです。

**解釈 (Interpretation)**
- Round 1 の主要な設計欠陥はほぼ解消されていますが、運用時に事故化し得る未閉包が残っています。
- 特に「6m運用のまま24m用epoch_idを発行する可能性」と「status管理の世代切替時整合性」は、live_criteria達成以前に再現性を崩すため Critical です。

1. `fcntl` 実用性  
[Suggestion] macOS/Linux 前提なら妥当です。  
修正提案: [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L154) の `FileLock` 抽象表現はやめ、既存実装に合わせて `fcntl.flock` 明示に統一してください（依存追加不要）。

2. `latest_data_end_floor` safety margin 1 week  
[Warning] 根拠が未計測です。1 week は advance を過度に遅延させる可能性があります。  
修正提案: margin を定数化し、`latest`, `margin_days`, `floor`, `next_window.end` を毎回ログ出力して実測で再校正してください。

3. `compatibility_fingerprint` 項目  
[Warning] 現項目は概ね妥当ですが、互換性事故を防ぐ鍵が不足しています。  
修正提案: `epoch_id_format_version` と `state_schema_version` を fingerprint 判定対象に追加してください。

4. `anchor_origin` の意味と 6m→24m 移行  
[Critical] 現状 6m 期間のまま T059 を動かすと、24m想定の epoch_id が先に発行され、後の24m有効化時に ID 再利用汚染が起こり得ます。  
修正提案: `reserve_run_slot` 時に「実際の `cfg.dataset` が epoch window 契約と一致しないなら abort」の hard guard を入れてください。

5. `mark_run_status` 経路  
[Critical] [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L166) で epoch advance 時に `run_ids_in_current_epoch` を全消去するため、旧epochの実行中 run が後から status 更新できない経路があります。  
修正提案: run status を `current epoch` 配列ではなく `run_id -> record` の辞書（または `epochs` 階層）で保持し、少なくとも terminal になるまで保持してください。

6. `--reset-epoch-state` 権限  
[Warning] flag 単体は誤操作余地があります。  
修正提案: 対話確認ではなく `--reset-epoch-state --yes-reset-epoch-state --reason "..."` の二重明示 + `audit_log.jsonl` 追記を必須化してください。

7. 24m memory gate を T059 DoD に含めるか  
[Warning] 含めるべきです。現記述は方針メモで、DoD の拘束力が弱いです。  
修正提案: 「24m有効化PRの前提条件」として RSS 実測基準を明文化し、T059 DoD にリンクしてください。

8. 見落とし論点（timeout / schema bump / epoch_index）  
[Suggestion] `lock timeout 10s` は妥当だが定数化・ログ化してください。  
[Warning] `schema_version` bump policy を明文化してください（互換破壊時は fail-closed + reset 必須）。  
[Suggestion] `epoch_index` は metadata 限定の方針を維持し、ID/判定キーには使わないと明記してください。

追加の Critical 1 件:
- [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L130) の `anchor_origin` 例は `Z`、[conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260429-2113-todo-T059-epoch-window-manager/conceptual-design.md#L238) の比較は `.isoformat()`（`+00:00`）で、文字列比較だと偽不一致になります。  
修正提案: 比較前に両者を datetime に正規化してから比較してください。