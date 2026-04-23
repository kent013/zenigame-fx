## 本分析の前提
- Stage gate I/Fと戻り値（StageResult.payload.cross_pair{skipped/result/error}）は既存仕様どおり（shadowはStage Cのpassedに影響しない）。
- Archiveはmonotonic enrich（A→B→C）＋第4段の`mark_graduated`でgraduatedフラグを立てる。Aは全個体で必ずcollect、B/Cは短絡時に未collectで矛盾しない。
- Cross-pairは`StageCRunCrossPairEvaluator.evaluate(...)`でPhase2はmean＋minのAND判定（ratio provider未注入）。`passed`はcross-pair実装側で完結。
- Archiveのii_lite_passは`payload["cross_pair"]`のskipped/Noneを基準に判定（Noneなら未評価扱い）。

## Verdict: APPROVED

## Facts
- Tier1×6＋Graduationの2層構造を`SwimLane`階層（Tier1Lane/GraduationLane）と`LaneManager`で一元管理。
- `run_generation(lane_id)`はA→B→Cの順に短絡評価し、各通過時にarchiveへ4段伝搬（A/B/C collect＋必要時に`mark_graduated`）。
- Cross-pairはTier1のStage Cでshadow実行。データ未注入時はskipped（保守的にgraduation False）。
- Graduation判定は「Stage C passed AND cross-pair passed」。即時`seed_graduates.append`＋`archive.mark_graduated`を採用。
- GraduationLaneの評価は本TODO外。`run_generation("graduation")`は`NotImplementedError`を明示。
- Archiveのinstrument値はTier1=実インスト、Graduation=固定sentinel `"multi"`の方針。
- 失敗モード表に、meta未設定、lane不在、内部例外、cross-pair例外、skipped時の保守的判定、重複collect警告などを網羅。
- テスト計画はdataclass/初期化/短絡/通過/卒業/adapter/順序/状態/NotImplementedを含む包括セット。
- DI（config群・evaluator・archive・bt config factory）でモック容易性と拡張性を確保。

## Interpretations
- 目的・スコープは適切に限定（1世代の評価オーケストレーションと卒業まで）。GA生成は明確にOUTで境界が明瞭。
- 設計判断は一貫：SSOT（GraduationLane.pair_bars）でcross-pairデータを供給、shadowは卒業判定のみ参照しStage C本体のpassedは汚さない。
- 失敗モードは主要経路をカバー。即時`mark_graduated`は整合性に有利だが、重複昇格・再実行時の冪等性ガードがあるとより安全。
- 4段伝搬（config→GaConfig→genome.meta→consumer/archive）のうち、本稿ではarchive 4段は明瞭だが、上流（config/GaConfig→genome.meta）の転記・スナップショット要件が明文化不足。再現性や「値の転記漏れ」防止の観点で追記が望ましい。
- `"multi"` sentinelは合理的だが、下流集計・可視化・フィルタの互換性契約を明示しておくべき。
- テストは概念意図に整合。加えて冪等性・sentinel互換・state別カウント不変などの境界テストが入ると運用耐性が上がる。
- 使命・絶対制約の適合性：本設計自体は構造レイヤで準拠。実運用での遵守は`backtest_config_factory`（イントラデイ、ロング/ショート許容、スワップ・スプレッド反映）に依存するため、前提検証（C4）をマネージャ初期化時に明示チェックするのが安全。
- 先人知見との整合：ペア横断の合格基準とGraduationでのmean−λ·std再評価は、過剰最適化の抑制・普遍性検証に合致（Lopez de Prado, 2018; Bailey et al., 2014; Deflated Sharpe Ratio: Bailey & Lopez de Prado, 年要確認）。

参考（要確認含む）
- Marcos López de Prado (2018), Advances in Financial Machine Learning.
- David H. Bailey, Jonathan M. Borwein, Marcos López de Prado, Qiji Jim Zhu (2014), The Probability of Backtest Overfitting.
- David H. Bailey, Marcos López de Prado (2012?, 要確認), The Deflated Sharpe Ratio.

## 修正点
1. §4.7と§4.8の整合性: 「Graduation laneでも同等collect」記述を本TODOの方針（`run_generation("graduation")`は未実装）に統一。Graduationでは本TODO中はarchive collectしない旨を明記。
2. 4段伝搬（値の転記）を明文化: `config/alpha_factory/default.yaml → SwimLaneConfig/GaConfig → BacktestConfig（スワップ/スプレッド/取引時間帯）→ StageEvaluator入出力 → archive.metrics.payload(meta_snapshot, bt_costs, timeframes, instrument|pairs)`の転記表を追補し、漏れ防止を仕様に格上げ。
3. `"multi"` sentinelの互換契約: Archiveの`instrument="multi"`採用時は`payload["pairs"]`（評価対象ペア一覧）と`weights/λ`を必須保存。下流集計が`instrument`をキーに厳密比較する場合の扱いをdocsに追記。
4. 冪等性ガード: `mark_graduated`の多重呼び出し/再実行対策として、LaneManager側で「当該(lane_id, generation, individual_name)が既卒業ならskip」を実装（またはarchive側のidempotent API契約を明記）。`seed_graduates`も`individual_name`キーで重複追加を避けるオプションを設計に記載。
5. `stage_cfg`の由来を明示: コンストラクタ受領の`stage_gate_config`から各ステージの閾値/設定を取り出す規約（例:`self._stage_cfg.for_stage("A")` or 共有`StageGateConfig`）を仕様化し、擬似コード中の`stage_cfg`表記を整合。
6. Cross-pair skippedの契約を明確化: `_build_cross_pair_args`が`(None, None)`を返す場合、Stage Cは`payload.cross_pair={"skipped": True, "result": None, ...}`を必ず埋める前提を明記（テストNo.9で検証）。
7. 絶対制約の実装前提チェック: `backtest_config_factory`が(a) イントラデイ取引時間帯、(b) ロング/ショート許容、(c) スワップ・スプレッドを含むことをLaneManager初期化時に`assert`/`ValueError`で検証。テスト項目に「コスト未設定で初期化失敗」を追加。
8. Promotionの時点と副作用を明文化: 即時append＋即時`mark_graduated`の利点/副作用を§4.6に箇条書きで追記し、将来「一括promote」に切替える際のフラグ（例:`deferred_promotion: bool`）拡張ポイントを記載。
9. 状態遷移のNoOp仕様を明記: `state!="active"`ではgeneration_count非増分・summaryに`{"state": lane.state, "n_evaluated": 0}`を必ず含める契約を`run_generation`返却仕様に追記（テストNo.15で確認）。
10. 追加テスト提案（軽微）: 
   - 卒業の冪等性（同名個体の二重`mark_graduated`を抑止）。
   - Graduation向けsentinel出力（`instrument="multi"`時に`payload["pairs"]`必須）をmonkeypatchで検証（将来の実装見越し）。

以上は記述追補と軽微なガード設計で収まり、骨子・I/Fは堅牢です。構造・責務分離・失敗時の保守性は良好で、North Star/絶対制約にも整合します。実装時はC4（前提明示）とC8（INCONCLUSIVE許容）をテスト命名と失敗時サマリーに反映することを推奨します。