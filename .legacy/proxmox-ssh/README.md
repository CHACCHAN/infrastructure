# 旧Proxmox操作実装のアーカイブ(直接SSH方式)

community.proxmox モジュール化(docs/migration/ 参照)の書き換え前スナップショット(2026-08-13)。

- `proxmox_*/` — 旧ロール一式(qm / pvesh をノード上で直接実行する方式)
- `playbooks/` — 旧 `playbooks/proxmox/*.yml`(proxmox_connect + hosts: proxmox の2プレイ構成)

Phase 3(検証・切替)完了後に削除を判断する。現行コードからは参照されない。
