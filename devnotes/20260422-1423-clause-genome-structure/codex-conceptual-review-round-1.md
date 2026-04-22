## 各レビュー項目への所見

1. 目的との整合性  
Fact: `conceptual-design.md` 本文、および比較対象である現行 `src/dsl/genome.py` の内容がこの会話には提示されていません。私は今回の制約下ではローカルファイル本文を確認できていません。  
Interpretation: `max_clause=1 でもフラット 4 式と等価ではない` を満たすかは、Clause の意味論と旧 Genome の評価経路を対照しないと判定不能です。C1 と C4 により、現時点で適合/不適合の主張はできません。

2. 必須 5 要素の網羅  
Fact: directional/local_gate 型分離、重み和正規化、ヒステリシス、time_stop & session close、spread フィルタの採否・責務分担が分かる本文断片が未提示です。  
Interpretation: 網羅性レビューは設計本文の責務表または構成図がないと成立しません。現時点では未検証です。

3. ヒステリシス動作  
Fact: `θ_on > θ_off` をどの層で適用するか、entry/exit 両側か、clause 単位か strategy 単位かの記述を確認できていません。  
Interpretation: イントラデイ FX でヒステリシスがチャタリング抑制に有効であること自体は一般論として妥当ですが、この設計に適切に埋め込まれているかは別問題です。設計本文なしでは有効性を設計レベルで肯定できません。  
要確認の参考文献候補: Hysteresis を含む regime persistence / threshold switching の金融時系列応用は実務・学術ともに蓄積がありますが、正確な著者・年・題名は本文確認後に絞るべきです。

4. PrimitiveEvaluator Protocol の抽象レベル  
Fact: `Protocol` 化の対象責務、戻り値、 stateful/stateless 前提、 primitive registry との接点が未提示です。  
Interpretation: primitive 未実装段階で Protocol を置くこと自体は概念設計としては自然ですが、抽象が早すぎて downstream 制約を固定しすぎていないかは本文確認が必要です。現時点では妥当とも過剰とも断定できません。

5. `enforce_consistency` の配置  
Fact: `enforce_consistency` を pure function としてどのフェーズで呼ぶか（mutation 後、crossover 後、decode 前、evaluation 前など）が未提示です。  
Interpretation: pure function 分離は GA operator と整合しやすい設計候補ですが、呼び出し点が曖昧だと「repair が意味論を変える」「archive との整合が崩れる」リスクがあります。本文がないため整合性は未検証です。

6. スコープ境界  
Fact: 後続 TODO である `clause-ga-operators` / `clause-backtest-integration` / `primitives-registry` の境界定義を確認できていません。  
Interpretation: 概念設計レビューでは依存方向と責務分割が重要ですが、その分割図が見えないため妥当性を判断できません。

7. 旧 Genome 削除方針  
Fact: `_legacy` リネームをしない理由、既存テストを skip する条件、移行期間の互換方針が未提示です。  
Interpretation: 旧実装を中途半端に残さない方針自体は筋が通りますが、skip 方針は「何を壊す前提で、何を守るのか」の設計根拠が必要です。本文確認なしでは妥当性を判定できません。

8. session close の扱い  
Fact: `DslStrategy` 引数で `default=None` とする理由、および `None` 時にイントラデイ制約をどこで強制するかが未提示です。  
Interpretation: ここは North Star と絶対制約に直結するため、概念設計で最も慎重に確認すべき点です。`default=None` が「未設定でも日跨ぎしない」意味なのか、「未設定なら制約が抜けうる」のかで評価が逆転します。現時点では未検証です。

## 致命的指摘 (Blockers)

- Fact: レビュー対象である [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1423-clause-genome-structure/conceptual-design.md) を含む参照ドキュメント本文が会話中に提示されておらず、今回の明示制約ではローカルファイル本文を取得できません。  
- Interpretation: C1 Design-first、C4 前提検証、C6 Fact / Interpretation 分離、C8 INCONCLUSIVE を守る限り、設計内容を読まずに APPROVED 系判定を出すことはできません。  
- Fact: 重点レビュー項目 1〜8 はいずれも、本文中の責務定義・依存境界・制約強制点の確認が必要な論点です。  
- Interpretation: 現時点の blocker は「設計の質が低い」とは限らず、「レビュー入力が不足しているため監査可能性が成立していない」ことです。

## 改善提案 (Non-blocking)

- [conceptual-design.md](/Users/ishitoya/repository/zenigame-fx/devnotes/20260422-1423-clause-genome-structure/conceptual-design.md) の全文、または最低でも以下の断片を会話に貼ってください。  
  1. 背景・目的  
  2. 新 Genome / Clause の概念図  
  3. 必須 5 要素の責務配置  
  4. `PrimitiveEvaluator Protocol` の定義案  
  5. `enforce_consistency` の呼び出し位置  
  6. 旧 Genome 廃止方針  
  7. `session close` とイントラデイ制約の整合説明
- 併せて、比較用に [src/dsl/genome.py](/Users/ishitoya/repository/zenigame-fx/src/dsl/genome.py) の現行 flat genome 構造と、SSOT である [clause-architecture.md](/Users/ishitoya/repository/zenigame-fx/docs/alpha_factory/clause-architecture.md) の該当節も抜粋してください。
- その材料があれば、次回は 1〜8 を Fact / Interpretation 分離で実質判定できます。

## 判定

NEEDS_REVISION