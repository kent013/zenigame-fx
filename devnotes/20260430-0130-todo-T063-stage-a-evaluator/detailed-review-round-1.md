前提（C4）  
- Verified: レビュー対象は提示本文のみ（T063 詳細設計ドラフト）。  
- Unverified: `synthesis.md` 本文、T061 実装実体、既存コード接続点（本ラウンドでは未照合）。

[VERDICT]  
**REQUEST_CHANGES（Critical 2件）**

[Critical]  
1. **state の単一情報源が崩れている（観点5）**  
`StageAGenerationInput.state` を持ちながら、`evaluate_generation(state, inputs, ...)` で別引数 `state` を受け、実装上は後者だけを使用しています。  
この二重化は不整合を許し、pure/immutable API 契約を曖昧化します。  
対応: `state` は 1 経路に統一（`inputs.state` のみにするか、逆に入力 dataclass から削除）。暫定でも `if inputs.state != state: raise StageAInputError` を必須化。

2. **乖離更新がサンプルサイズ無視で C7/C8 に抵触し得る（観点4,10）**  
`update_divergence_state(prev_state, corr)` は `corr` だけで毎回 step 更新しますが、`n`（相関の標本数）や信頼性ガードがありません。  
低標本・ノイズ相関で `divergence_offset_steps` が機械的に増減し、`q_force` が誤駆動するリスクが高いです。  
対応: API に `corr_sample_size`（最低でも n）を追加し、`n<30` は INCONCLUSIVE として step 不変、`n<10` は更新禁止を明文化。

[Warning]  
1. **`bucket_validator` が未配線**  
`evaluate_generation` 引数にあるが `evaluate_fn` へ渡しておらず未使用です。契約誤認を生みます（使わないなら削除、使うなら DI シグネチャに含める）。  
2. **Helper の入力ガード不足**  
`compute_q_force_with_divergence(base_q_force, ...)` で `base_q_force` 範囲検証なし、`select_top_q_force_indices(..., q_force)` で `q_force` 範囲検証なし。将来の直接呼び出しで静かに異常値を通す可能性があります。  
3. **同点 tie-break が仕様化されていない**  
`sorted(..., reverse=True)` の同点順が入力順依存です。再現性要件が強い領域なので、`(-score, index)` など明示 tie-break を仕様化推奨。  
4. **「学術引用」節のラベル不一致（観点11）**  
実体は主に内部 synthesis/既存コード参照で、学術文献引用はほぼありません。節名を「根拠/先行実装」に修正した方が正確です。

[Suggestion]  
1. `evaluate_generation` の契約を簡素化: `inputs` に state を内包し単一化、戻り値は `(result, next_state)` 形式に固定。  
2. テスト追加:  
- `state` 二重指定不整合の reject テスト  
- tie-break 決定性テスト  
- `corr n` 不足時に state 据え置きテスト  
3. default-deny は docstring だけでなく、Phase2 まで待たずに「補集合 fail を明示的に生成しない」不変条件テストを T063 側にも 1 本置くと安全。