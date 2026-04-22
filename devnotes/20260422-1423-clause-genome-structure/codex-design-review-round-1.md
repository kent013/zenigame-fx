## 各レビュー項目への所見（1〜8、Fact/Interpretation 分離）
1. 関数シグネチャ整合  
Fact: このセッションではコマンド実行不可のため、指定ファイル本文を確認できていません。  
Interpretation: `PrimitiveEvaluator Protocol / compute_composite / enforce_consistency` の整合は **INCONCLUSIVE** です。

2. 境界条件の網羅  
Fact: `detailed-design.md` の境界仕様記述（`θ_on/θ_off` 等号、`time_stop`、`session_close_utc=None`、空 directional、`denom=0`）を未読です。  
Interpretation: 網羅性評価は **INCONCLUSIVE** です。

3. ヒステリシス挙動の正当性  
Fact: 状態遷移表または擬似コードを未確認です。  
Interpretation: 「保有継続/新規なし」の非対称機械が閉じるかは **INCONCLUSIVE** です。

4. `enforce_consistency` の完全性  
Fact: 異常入力の分岐仕様（repair vs raise）未確認です。  
Interpretation: 完全性・例外方針の妥当性は **INCONCLUSIVE** です。

5. 旧コード削除方針と skip 方針  
Fact: `src/ga/` と `tests/ga/` の現状依存関係、pytest 収集条件を未確認です。  
Interpretation: `src/ga/` 非変更で collection 成功するかは **INCONCLUSIVE** です。

6. spread フィルタ受け渡し契約  
Fact: clause-backtest-integration 側 I/F 記述を未確認です。  
Interpretation: 契約明示の十分性は **INCONCLUSIVE** です。

7. `params: dict` mutability  
Fact: frozen dataclass 定義・コピー方針・hash 方針の明文化有無を未確認です。  
Interpretation: 共有参照/不変性の落とし穴 mitigation は **INCONCLUSIVE** です。

8. テストケース網羅性  
Fact: テスト一覧と期待振る舞い対応表を未確認です。  
Interpretation: 網羅性判定は **INCONCLUSIVE** です。

## Falsification 結果（H1〜H4）
- H1 (`max_clause=1` でもフラット式と非等価保証)  
  反証結果: **判定不能（INCONCLUSIVE）**  
  理由: 等価性/非等価性の定義と構成則を未確認。

- H2 (`src/ga/` 非変更でも pytest collection 成功)  
  反証結果: **判定不能（INCONCLUSIVE）**  
  理由: 収集対象・import 経路・skip 条件未確認。

- H3 (`enforce_consistency` 冪等)  
  反証結果: **判定不能（INCONCLUSIVE）**  
  理由: `f(f(x))` を破る補正規則（乱数・順序依存・丸め）有無未確認。

- H4 (`DslStrategy` 境界条件が望ましい挙動で網羅)  
  反証結果: **判定不能（INCONCLUSIVE）**  
  理由: 境界仕様の明文化とテスト対応未確認。

## 致命的指摘 (Blockers)
- C1 Design-first を満たすための一次資料本文を確認できていない状態で、技術的承認は出せません。  
- 現状は Fact 不足で、H1〜H4 の falsification を実施不能です。

## 改善提案 (Non-blocking)
- 次の最小断片を貼ってください（その場で再レビューします）。  
1. `detailed-design.md` の関数シグネチャ節  
2. 境界条件・状態遷移（hysteresis）節  
3. `enforce_consistency` ルール一覧  
4. `src/ga/` 非変更方針と pytest 収集方針節  
5. spread I/F 契約節  
6. テストケース一覧（ケース名＋期待値）

## 判定: NEEDS_REVISION

（注）これは設計内容の否定ではなく、一次資料未確認による監査不能判定です。本文共有後、C1〜C9 に沿って即時に本判定へ更新します。