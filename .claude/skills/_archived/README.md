# Archived Skills

zenigame（日本株 Alpha Factory）から流用した skill 群のうち、zenigame-fx 環境で**現状動作しない** ものをここに退避している。Claude Code は `_archived/` プレフィックスのディレクトリを skill 候補から除外する想定（要検証）。

## 退避された skill 一覧（7 件）

| skill | 退避理由 | 復活条件 |
|-------|---------|---------|
| `zenigame-enqueue-task` | Dramatiq + RabbitMQ ワーカー依存 | zenigame-fx に Dramatiq/RabbitMQ ベースのキュー基盤を整備した時 |
| `zenigame-manage-alert` | systemd + Discord 通知依存 | zenigame-fx に Discord 通知 + systemd サービス整備した時 |
| `zenigame-manage-timer` | systemd timer 依存 | systemd サービス整備した時 |
| `zenigame-restart-worker` | systemd worker 依存 | systemd ワーカー整備した時 |
| `zenigame-troubleshoot-worker` | systemd worker 依存 | 同上 |
| `zenigame-primitive-ic-eval` | J-Quants API + 日本株プリミティブ registry 依存 | zenigame-fx 用の primitive registry を整備し、IC 評価を再設計した時 |
| `zenigame-primitive-ic-sync` | J-Quants + プリミティブ registry 依存 | 同上 |

## 復活手順

復活させる場合:
1. `_archived/{skill}` を `.claude/skills/{skill}` に `git mv` で戻す
2. zenigame-fx 環境向けに skill 内容を adapt（パス・依存パッケージ・使命・禁止事項）
3. 新しい依存インフラがあることを動作確認

## 注意

- これらの skill は **そのままでは zenigame-fx 環境で動かない**（依存インフラがない）
- 設計パターンの参考としてのみ参照してよい
- 本番運用で呼び出してはならない
