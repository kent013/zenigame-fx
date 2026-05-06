**判定**  
最小修正 1 点を入れれば **APPROVED** でよいです。

**指摘（最小修正）**
1. **Warning**: `pq.read_table(archive_path)` が hook 側にあると、sidecar 生成の失敗で `run_ga` 本体が落ちる経路が残ります。  
   [scripts/alpha_factory/run_ga.py:1711](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1711)  
   [scripts/alpha_factory/run_ga.py:1724](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/run_ga.py:1724)  
   `write_stage_a_top_fold` 内に「read→build→write」を寄せて fail-open を一貫させるか、少なくとも `read_table` だけは狭い例外処理で warning + skip にしてください。

**質問への回答**
1. Round 1 Critical/Warning 全採用方針は妥当です。上の 1 点だけ詰めれば承認可能です。  
2. 20 列は過不足ありません。`n_selected` / `fold_sign_n_valid` / `pfre_n_valid` は分母の監査性を上げるので冗長ではないです。  
3. `> 0.0` は実装上は整合しますが、`fold_sign_ratio` は「符号反転率(0..1)」なので意味は「正」ではなく「非ゼロ（反転あり）」です。  
   [src/alpha_factory/statistics.py:252](/Users/ishitoya/repository/zenigame-fx/src/alpha_factory/statistics.py:252)  
   列名は `fold_sign_nonzero_ratio` 系のほうが誤読を減らせます（少なくとも説明文で明示）。  
4. `summary.json` に `diagnostics_stage_a_top_fold` を追加しても既存 consumer は基本壊れません。`run-report`/`analyze-run` は未知 field を無視する構造です。  
   [scripts/alpha_factory/generate_run_report.py:671](/Users/ishitoya/repository/zenigame-fx/scripts/alpha_factory/generate_run_report.py:671)  
   ただし新指標をレポート表示したいなら、その表示追加は次サイクルで別責務として切るのが自然です。