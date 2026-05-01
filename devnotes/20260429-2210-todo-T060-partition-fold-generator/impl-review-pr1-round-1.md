**本分析の前提（C4）**
- `Verified`: 本レビューは、あなたが提示したテキスト情報のみを根拠に実施（指示どおりコマンド実行・書き込みなし）。
- `Verified`: そのため `git diff` / `grep` / `ruff` / `mypy` の実測証跡は未取得。
- `Verified`: 判定は「提示情報ベースの設計・実装整合レビュー」として実施。

**主要 findings（重大度順）**
1. `Blocker` H1 未反証: `PeriodLabel` の fold suffix base 3値が dead code 化している疑い。  
対象: [partition.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T060-pr1/src/alpha_factory/partition.py)  
Fact: fold label は `f"fold_{k}_{train|embargo|test}"` 動的生成と記載。  
Interpretation: `FOLD_TRAIN/FOLD_EMBARGO/FOLD_TEST` を直接参照しないなら SSOT 一貫性が弱い。
2. `Blocker` H2 未反証: `PartitionGenerator.generate` のスライス順序入替 regression 検出力が不足の疑い。  
対象: [partition.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T060-pr1/src/alpha_factory/partition.py), [test_partition.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T060-pr1/tests/alpha_factory/test_partition.py)  
Fact: 提示テスト一覧では `stage_a=8w` と `embargo_after_a=1w` の明示検証が読み取れない。  
Interpretation: 型検査は通っても順序誤りを見逃す余地がある。
3. `Blocker` H5 未反証: helper 依存テストの同方向バイアス懸念。  
対象: [test_partition.py](/Users/ishitoya/repository/zenigame-fx/worktrees/todo-T060-pr1/tests/alpha_factory/test_partition.py)  
Fact: `_canonical_24m_window()` / `_canonical_stage_b()` の共通利用が記載。  
Interpretation: helper 側の誤りがあると複数テストが同時に誤って通る可能性がある。

**反証仮説 H1-H5（C9）**
| 仮説 | 判定 | 根拠 |
|---|---|---|
| H1 | FAIL | fold suffix base の実利用を反証できる情報なし |
| H2 | FAIL | 順序入替を確実に検出するテスト証拠が不足 |
| H3 | PASS | UTC厳密 reject を明示テスト（JST/Pacific/naive）で支持 |
| H4 | PASS | `label=stage_b` + `62w` + 末端整合チェックで fold 単体契約は成立 |
| H5 | FAIL | fixture 独立性を反証する情報不足 |

**A1-F6 判定表**
| 観点 | 判定 | コメント |
|---|---|---|
| A1 | FAIL | H1未反証（fold suffix base のSSOT利用が不明確） |
| A2 | PASS | `tzinfo` + `utcoffset()==0` 厳密化は意図どおり |
| A3 | PASS | `end > start` 半開区間制約あり |
| A4 | PASS | 10領域構造・`all_periods`・`c_lite_periods` 定義は整合 |
| A5 | FAIL | H2未反証（順序誤り耐性が弱い可能性） |
| A6 | PASS | 104w整合 + cursor二重guard は妥当 |
| A7 | PASS | Fold連続性と index 制約あり |
| A8 | PASS | rolling-origin 定義は整合 |
| A9 | PASS | 62w整合 + 末端一致guard は妥当 |
| A10 | NIT | 動的label設計自体は妥当、ただしA1課題あり |
| B1 | NIT | 34件計画は充足見込み、独立性はH5懸念 |
| B2 | PASS | UTC厳密性の検証項目あり |
| B3 | PASS | 命名は振る舞い記述型で規約整合 |
| B4 | PASS | 純関数テストで isolation 妥当 |
| B5 | PASS | short/long・連続性違反の境界テストあり |
| C1 | NIT | import hit 範囲は実grep証跡未確認 |
| C2 | PASS | partition 層が status 非依存なのは設計整合 |
| C3 | PASS | 上流 deterministic 切り出しで collider 回避方針に整合 |
| C4 | PASS | 定数集約方針は整合 |
| C5 | PASS | 半開区間規範との整合は良好 |
| C6 | PASS | schema_version 非関与は整合 |
| D1 | NIT | 2ファイル限定 touch は実diff証跡未確認 |
| D2 | NIT | 逆流/未配線は実grep証跡未確認 |
| D3 | NIT | ついで対応混入なしは実diff証跡未確認 |
| E1 | NIT | line-by-line一致は実ファイル照合証跡不足 |
| E2 | NIT | ruff/mypy clean の実行証跡不足 |
| F1 | PASS | devサーバー不要方針に整合 |
| F2 | PASS | テスト命名規約に概ね整合 |
| F3 | PASS | 外部I/Oなしの isolation 方針に整合 |
| F4 | NIT | lint/type clean は証跡待ち |
| F5 | PASS | look-ahead bias は対象外で妥当 |
| F6 | PASS | C3/C7 対象外判断は妥当 |

**修正提案（blocker対応）**
- `PeriodLabel` の fold suffix base を実利用する（例: `f"fold_{k}_{PeriodLabel.FOLD_TRAIN.value}"`）か、未使用なら enum から削除して責務を明確化。
- `PartitionGenerator` の順序回帰耐性を強化するテスト追加。  
  例: 各 period の「ラベル順」と「期待週数（8/1/6/1/6/1/6/1/12）」を個別に固定検証。
- helper 非依存の独立ケースを最低1-2本追加し、H5（同方向バイアス）を潰す。

[REQUEST_CHANGES]