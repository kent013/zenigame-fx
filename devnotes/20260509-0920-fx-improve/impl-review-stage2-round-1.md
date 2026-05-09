前提: コマンド実行・実ファイル確認なしで、提示 diff のみを反証優先（C9）でレビューしました。

**ファイル別判定**

- [reports/calibrate-gate/history.jsonl](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T091-stage2/reports/calibrate-gate/history.jsonl)
  - [Critical] T091段階2の実装スコープ外の履歴データが大量に追記されています。`history` は実行時の threshold 適用に影響し得るため、再現性・汚染防止の観点でこのPRに含めるべきではありません。
  - [Suggestion] この変更は別PRに分離、または除外してください。

- [src/alpha_factory/archive.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T091-stage2/src/alpha_factory/archive.py)
  - 判定: 概ね設計一致
  - [Suggestion] `trade_count_full_dataset` は `stage_a` 未設定時に未計算のままなので、将来の呼び出し順逸脱に備えるなら defensive test を追加すると安全です。

- [scripts/alpha_factory/run_ga.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T091-stage2/scripts/alpha_factory/run_ga.py)
  - [Warning] `trade_count_full_dataset=tc_full if (tc_full or 0) > 0 else None` により、`0` が `None` に潰れます。`0件` と `欠損` の区別が失われ、replay/report 解釈が曖昧になります。
  - [Suggestion] `0` は `0` として保持し、欠損のみ `None` にする方が契約が明確です。

- [tests/alpha_factory/test_archive.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T091-stage2/tests/alpha_factory/test_archive.py)
  - 判定: 良好
  - [Suggestion] 「payload lacks is_full」の検証は、`None` 値だけでなく「キー自体なし」ケースも明示的に1本追加すると後方互換の主張が強くなります。

- [tests/scripts/test_run_ga_individual_cache_entry.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T091-stage2/tests/scripts/test_run_ga_individual_cache_entry.py)
  - [Warning] `_coerce_optional_int` の単体検証は十分ですが、段階2の本丸である `_update_cache` の「`tc_full`優先 / legacy fallback / malformed fallback」の挙動を直接検証するテストが不足しています。
  - [Suggestion] `_update_cache` に対する3ケース（新列あり・新列なし・新列不正）を追加してください。

**質問への回答**

1. 設計一致性  
- 実装本体（4列追加 + selection切替 + helper）は概ね一致。  
- ただし `history.jsonl` 追記はスコープ外。

2. 4段伝搬契約  
- `GENOMES_SCHEMA -> _create_row_template -> collect_stage_*` は接続確認できました。  
- `flush` は差分提示がなく、schema駆動実装前提なら接続される見込みですが、この資料だけでは最終段は厳密には INCONCLUSIVE。

3. `_coerce_optional_int` の堅牢性  
- 指定された拒否条件（NaN/pd.NA/np.bool_/list/dict/inf/非整数/負数）は実装・テストとも概ね妥当。  
- 漏れとしては重大なものは見当たりません。

4. 後方互換性  
- `_update_cache` の `tc_full -> tc_legacy -> 0` fallback は実装上成立。  
- ただし挙動の直接テストが不足。

5. T044契約遵守  
- `collect_stage_b` 後も `row["trade_count"]` を維持するテストがあり、verify されています。

6. 既存14失敗の扱い  
- 「mainでも同失敗」の証跡がこの場では未確認のため厳密には INCONCLUSIVE。  
- ただし内容説明上、T091段階2スコープ外とみなす判断自体は妥当です。

**全体判定**

- **CHANGES_REQUESTED**  
  - 主理由: `history.jsonl` のスコープ外・実行影響あり得る変更（Critical）。  
  - 併せて `_update_cache` 直接テスト不足と `0`/`None` の意味混同を解消すると、段階2はより堅牢です。