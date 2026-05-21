全体判定: **CHANGES_REQUESTED**

前提: このレビューでは、提示された概念設計文だけを根拠に評価しています。  
前提: ユーザー指定によりコマンド実行とファイル読取コマンドを使っていないため、`run_ga.py:779`、`nsga2_selection.py`、`cpps_archive.py`、`loop_closure.py`、`docs/alpha_factory/`、`devnotes/20260513-1915-todo-phase2-integration-step3-7/`、`git log` の現物確認は未実施です。

**最重要論点**
- 推奨は **案A（`BCEvaluationResult` 忠実）** です。  
Fact: 案Aは Stage B 評価で得た値を selection 軸に使う案です。  
Fact: 案Bは archive 行の holdout metric を流用して Pareto 軸を組む案です。  
Interpretation: 案Bは holdout を探索器の最適化対象に昇格させるため、Stage C / cross-pair を「最低条件・検証系」として扱う契約を壊します。  
Interpretation: 案Bは「見かけ数値改善」と「GA ハック」の禁止事項に最も近いです。  
修正提案: selection に入れる Pareto 軸はすべて Stage B 時点で閉じる値に限定してください。`mission_inf_gap` も Stage B 可観測量だけで定義し、Stage C / holdout / archive 由来値は shadow-only に留めてください。

**1. 使命との整合性**
- [Critical] Stage C holdout metric 流用の案Bは不整合です。  
Fact: North Star は live_criteria 全充足 + cross-pair(ii-lite) 通過です。  
Fact: 概念設計の案Bは archive holdout metric を selection に使います。  
Interpretation: 検証用レーンを探索用レーンへ戻すため、使命達成の証拠力が落ちます。  
修正提案: Pareto 軸は案Aに固定してください。成功判定も `Stage C 通過数` ではなく `mission candidate 再現率` を主指標に置いてください。
- [Warning] 多様性増加と mission 達成は同義ではありません。  
Fact: 提示された観測は Stage C pass の seed variance と primitive-set の集中です。  
Interpretation: live_criteria 全充足への因果はまだ示されていません。  
修正提案: 詳細設計に「mission candidate 出現率」「live_criteria 各項目の同時充足率」を acceptance criteria として明記してください。

**2. 禁止事項違反**
- [Critical] 案Bは実質的な holdout 最適化です。  
Fact: archive holdout metric は検証結果です。  
Interpretation: それを parent/survivor 選抜に使うのは禁止事項 2, 3, 8 に抵触しやすいです。  
修正提案: archive は diversity memory と admission のみに使い、selection 軸の値源泉には使わないでください。
- [Warning] `mission_inf_gap` の定義が未確定です。  
Fact: 軸名だけが示され、算出窓と使用入力が未記述です。  
Interpretation: 未定義のまま入れると、cross-pair や holdout 情報の逆流が起きます。  
修正提案: 各項の式、時間窓、入力元、Stage provenance を 1 行ずつ固定してください。

**3. 実現可能性**
- [Warning] step3 で `BCEvaluationResult` 全体を per-individual payload として持つ設計は重い可能性があります。  
Fact: `BCEvaluationResult` は名前からして評価詳細を多く含みうる構造です。  
Interpretation: multiprocessing 境界で大きい payload を流すと性能とメモリの両方が悪化します。  
修正提案: selection 専用に `ParetoFeaturesLite` のような scalar sidecar を切り出してください。
- [Suggestion] `default OFF で bit-exact` の方針は妥当です。

**4. 期待効果の妥当性**
- [Critical] 「seed variance の主因は多様性保存欠如」という因果仮説は、まだ反証されていません。  
Fact: 提示された根拠は少数 seed の極端な分岐と 1 ファミリー集中です。  
Interpretation: 代替仮説として、目的関数のミスアライン、初期集団分布、mutation/crossover の表現制約、Stage B gate の狭さも残っています。  
修正提案: 詳細設計で少なくとも `baseline / NSGA-II only / CPPS only / NSGA-II+CPPS` の4条件を分離し、同一設定で比較する計画を必須化してください。
- [Warning] C7 的に標本が少ないです。  
Fact: 提示値だけでは seed 数が少数です。  
Interpretation: 「主因」まで言い切るには不足です。  
修正提案: 結論文言を「有力仮説」に下げ、実装後の判定基準を先に固定してください。
- [Warning] C3 的に collider bias の危険があります。  
Fact: Stage C pass 群だけを見ると survivor subset です。  
Interpretation: その subset 上の相関で軸の妥当性を語ると誤読しやすいです。  
修正提案: 軸評価は「全 evaluated 個体」または「selection 前 cohort」で行ってください。

**5. リスク**
- [Critical] NSGA-II と CPPS を同じ step5 で同時に効かせると、効果の帰属ができません。  
Fact: 両方とも diversity に効く仕組みです。  
Interpretation: これでは C9 falsification-first に反します。  
修正提案: まず `NSGA-II only` を配線し、その後に `CPPS admission` を別 flag で積んでください。
- [Warning] archive スキーマ伝搬漏れのリスクが高いです。  
Fact: AGENTS.md には schema 値伝搬漏れ禁止が明記されています。  
Interpretation: T102 は config から archive consumer まで触るため、破綻点が多いです。  
修正提案: 詳細設計に「config → GAConfig → runtime meta → archive row → consumer/test」の接続表を入れてください。

**6. スコープの適切さ**
- [Warning] step3 + step5 は妥当です。  
Fact: step4/6/7 を外しているため big-bang ではありません。  
Interpretation: ただし step5 の中で NSGA-II と CPPS を同時導入すると再び広すぎます。  
修正提案: PR も rollout も `step3`、`step5a(NSGA-II)`、`step5b(CPPS)` に分けてください。
- [Suggestion] `loop_closure warmstart` を scope 外に置いた判断は妥当です。

**7. メモリ制約**
- [Warning] 24GB / 6 worker 制約に対する定量見積りがありません。  
Fact: 概念設計には payload と archive のサイズ見積りがありません。  
Interpretation: selection 用 sidecar と archive row が肥大化すると 3GB/worker を超える可能性があります。  
修正提案: 詳細設計に「個体数 × 世代 × row size」の概算を入れ、selection では trade/equity 配列を持たない方針を固定してください。
- [Suggestion] crowding / non-dominated sort 自体の計算量より、評価結果の保持形式の方を先に削るべきです。

**8. 前提検証（C4）**
- [Warning] 現行コード前提の verified 状態は、このレビューでは満たしていません。  
Fact: ファイル実読をしていません。  
Interpretation: `run_ga.py:779` などの現況を私は確認できていません。  
修正提案: 詳細設計の先頭に、現 HEAD からの抜粋と「verified な前提一覧」を付けてください。

**9. Design-first（C1）**
- [Warning] `docs/alpha_factory/`、対象 devnotes、`git log` 参照済みとは判定できません。  
Fact: このレビューは提示文のみで行いました。  
Interpretation: C1 完了のレビュー記録にはなりません。  
修正提案: 次版では、参照した設計契約と git 変更点を箇条書きで添付してください。

**seed variance 主因仮説への反証候補**
- [Warning] 反証候補1は「selection ではなく objective misalignment が主因」です。  
Fact: 観測は diversity 崩壊を示します。  
Interpretation: それでも live_criteria に近い軸で選んでいなければ、NSGA-II 化だけでは mission は増えません。  
修正提案: Pareto 軸が live_criteria にどう接続するかを明文化してください。
- [Warning] 反証候補2は「表現と変異の探索半径不足」です。  
Fact: 1 モチーフ収束は selection だけでなく mutation topology でも起きます。  
Interpretation: NSGA-II を入れても family が広がらない可能性があります。  
修正提案: parent lineage concentration と mutation novelty を shadow 指標に追加してください。
- [Warning] 反証候補3は「CPPS が効いて、NSGA-II は効かない」です。  
Fact: 両者は別機構です。  
Interpretation: 同時導入では主因判定ができません。  
修正提案: 導入順を分離してください。

結論として、**方向性自体は妥当**です。  
結論として、**selection 実配線を進めるなら案A固定、NSGA-II と CPPS の分離、Stage B 完結の軸定義、反証計画の先出し**が承認条件です。