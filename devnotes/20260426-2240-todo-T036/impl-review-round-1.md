**レビュー結果**
- [Critical] 事実: `force_recalculate=True` で再実行すると、`_write_mode_to_targets` が `fsp_runtime_mode` と `fsp_sampling_mode` だけを上書きし、`fsp_factor_set` や `fsp_rolling_corr_60d` 等の既存値をクリアしません (`src/alpha_factory/fsp_updater.py:333-423`)。解釈: 以前の RUN で残った観測値が「skipped_*」モードに貼り付いたまま残り、H1 指標や運用監視レポートが矛盾したデータを読むリスクがあります。再計算インターフェースの契約 (観測値を最新状態に正規化する) に反するため致命的です。対応案: スキップ系モードを書き込む際に FSP 列をまとめて None に戻す処理と、その回帰テストを追加してください。
- [Warning] 事実: `_atomic_write_parquet` はテンポラリ名として `archive_path.with_suffix(".fsp_tmp.parquet")` を固定利用しています (`src/alpha_factory/fsp_updater.py:183-205`)。解釈: 複数プロセスが同一 archive を同時に更新した場合、同じ一時ファイルを共有して互いの書き込みを上書き・破壊する恐れがあり、求められている「atomic write」保証が崩れます。`tempfile.NamedTemporaryFile` 等で一意なテンポラリを確保することを検討してください。

全体判定: CHANGES_REQUESTED