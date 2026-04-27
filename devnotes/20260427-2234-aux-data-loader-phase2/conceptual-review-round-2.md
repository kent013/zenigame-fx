**Findings（重大度順）**

[Critical] §2.2 の `effective_from_utc` 根拠がまだ不十分です。  
Fact:
- 提案では `FRED API の realtime_start ベース（未確認）` と明記されています。
- ただし `realtime_start` は通常「リビジョン有効日」であり、「当日その値が市場で利用可能になった時刻」を直接表すとは限りません。
- `VIXCLS=16:20 ET` など series 固有時刻を FRED だけで一意復元できる前提は unverified です。  
Interpretation:
- C2（look-ahead 契約強化）は方向性は正しいですが、データ由来の時刻定義が曖昧なままだと、形式上は強化されても実質的に漏洩余地が残ります。  
修正提案:
- `effective_from_utc` を「取得元が保証する時刻」と「保守的推定時刻（policy）」で区別して保存。
- Phase 2 ではまず `observation_date + conservative lag` を既定にして、series ごとの厳密時刻は別検証で昇格させる。

[Warning] §2.3（strict default True）と §2.7（events partial coverage）の運用整合が未確定です。  
Fact:
- strict を既定 True にしつつ、events は partial coverage としています。  
Interpretation:
- preflight の required set を固定しすぎると、意図せず RUN 全停止になります。  
修正提案:
- preflight required を「今回使う primitive の required_data」に動的連動させる。
- `hard_required` と `soft_required` を分離して fail-closed 対象を限定。

[Warning] 「Phase 2 全部 1 TODO」は実行可能ですが、失敗時切り分けコストが高いです。  
Fact:
- 施策 1-9 はデータ契約・DB・ランナー・運用文書まで跨ります。  
Interpretation:
- 1 TODO 自体は可能でも、受け入れ判定は段階ゲートが必須です。  
修正提案:
- TODO は 1 件のまま、acceptance は `Gate A(契約) → Gate B(wiring) → Gate C(strict化)` の3段階に固定。

---

**確認依頼への回答**

1. Round 1 の `[Critical]3 + [Warning]4` 対応妥当性  
- C1, C3, W1, W2, W3, W4 は妥当です。  
- C2 は「設計意図は妥当、実データ根拠は未充足」で **部分充足** です。

2. Phase 2 全部を 1 TODO 化する判断  
- **妥当**です（ユーザー方針に整合）。ただし incremental commit + 段階 acceptance gate を必須条件にしてください。

3. 新規 Critical / Warning  
- 新規 Critical: `effective_from_utc` のデータ由来定義不足（上記）。  
- 新規 Warning: strict/preflight の required set 設計不足、1 TODO の切り分けリスク。

4. 全体判定  
- **CONDITIONAL APPROVED**（条件付き承認）。  
- 条件は「C2 の時刻根拠を conservative policy で確定」「preflight required の動的化」の2点です。