# レビュー対応記録(REVIEW.md への回答)

- 対象レビュー: REVIEW.md(2026-08-13、対象コミット e38ddf6。処理済みのためファイルは削除 — 内容はgit履歴の82de36e時点を参照)
- 対応日: 2026-08-13
- 凡例: **済**=実装・反映済み / **済(一部)**=中核のみ実装 / **計画**=短期改善計画に登録 / **受容**=理由付きでリスク受容

## P0

| ID | 状態 | 対応内容 |
| --- | --- | --- |
| SEC-01 | **済** | 利用者が該当2トークンを**失効・リセット済み**。`.legacy/` は削除。再発防止としてCIにgitleaks(履歴込み)を導入。※失効済みのため履歴の書き換えは必須ではないが、公開履歴を綺麗にしたい場合は `git filter-repo` を任意で実施 |

## P1

| ID | 状態 | 対応内容 |
| --- | --- | --- |
| SAF-01 | **済** | PBSデータディスクの自動判別を廃止し `pbs_data_disk_device` 明示必須へ。初期化前にOSディスク/マウント中/子・holder/既存署名を全て拒否するガードと、既存署名の意図的初期化用 `-e pbs_data_disk_wipe=true` を追加 |
| SAF-02 | **済** | find_vmに期待値照合(`pve_expected_name`/`pve_expected_node`)を追加し、provision/powerがインベントリ宣言を渡す。VMID誤設定時は別VMに触る前にfail。destroyは対象のVM名/node表示+任意の `-e expect_name=` 照合を追加 |
| REL-01 | **済** | 差分比較の現在値を `config: pending`(保留変更込み)へ変更。稼働中VMへ設定を適用した場合は「再起動まで保留の可能性」を明示表示 |
| SEC-02 | **受容** | 管理LAN内+cloud-init再構築でホスト鍵が毎回変わる運用のため当面受容。将来はguest agent経由のホスト鍵登録を検討(改善計画) |
| SEC-03 | **済** | homarrの `rbac.enabled: false` 化と、適用済みだった広域ClusterRole/ClusterRoleBindingの**クラスタからの削除まで実施**(homarr稼働影響なし) |
| SAF-03 | **済** | deploy.ymlにpreflightを追加。接続先APIサーバーが宣言 `k8s_api_server` と一致しない限り一切書き込まない |
| SEC-04 | **計画** | 管理画面はauthentik forward-auth付きIngress経由が正規経路。VM直アクセスの遮断はNET-01(DOCKER-USER/nftablesの宣言管理)と一体で設計する |
| SEC-05 | **計画** | bootstrapパスワード/トークンのvault必須化は利用者のvault値追加とセットで実施(新規構築時のみ影響) |
| SEC-06 | **計画** | outpost自動管理の要否を確認のうえ、不要ならsocket mount既定無効、必要ならsocket proxy化 |
| SEC-07 | **済(一部)** | k3sを稼働版 `v1.36.2+k3s1` に固定(新規ノードの版ズレ解消)。get.docker.com等のインストーラのdigest固定/公式APT化は改善計画 |
| SEC-08 | **済** | 参加トークンを `agent-token` 優先(存在時)へ変更。server側での `agent-token` 新設は保守作業として手順を記載 |
| REL-02 | **計画** | 宣言削除の追従(prune)は管理ラベル+allowlist方式を設計してから導入(無差別pruneはしない)。当面は削除時に手動 `kubectl delete` +このリポジトリのPRで対応 |
| SEC-09 | **計画** | 内部CA(またはPVE ACME)導入後に `insecureSkipVerify`/`validate_certs: false` を段階的に解消 |
| REL-03 | **計画** | ①DBロール分離(アプリごとのlogin role) ②pg_dump世代管理+restore drill ③K3s datastore/tokenの保全、の順で実施。`k8s_backup_*`(awx-secret-key等)のvault保全は実施済み |
| NET-01 | **計画** | SEC-04と一体。Compose側bind宣言+DOCKER-USERチェーンの宣言管理 |

## P2

| ID | 状態 | 対応内容 |
| --- | --- | --- |
| REL-04 | **済** | 再起動を `/var/run/reboot-required` 存在時(または `-e vm_reboot_force=true`)のみに変更。「差分なしでも毎回再起動」を解消 |
| REL-05 | **済** | Supabase健全性判定を `config --services` × `ps --all --format json` の突合に変更(停止・unhealthyを見逃さない) |
| REL-06 | **済** | `k3s_role` をインベントリで明示し、VM上の実役割(k3s.service/k3s-agent.service)と宣言の不一致でfail |
| REL-07 | **済** | 必須Secret未定義は黙ってskipせずfail(vault編集コマンドを案内)。全アプリにrollout待ち(Deployment/StatefulSet Ready)を追加 |
| REL-08 | **計画** | 宣言縮小(NIC/cloud-init/追加ディスク)のdrift収束は「削除も宣言」の設計を詰めてから |
| CFG-01 | **済** | 利用者がVM990/992を破棄しインベントリを掃除(testグループ・dev-migration削除でgateway不整合も解消)。dev鍵の非管理は設計判断(個人鍵。新規dev VM作成時は `-e pve_ssh_pubkey_file=` を指定) |
| DEP-01 | **済** | 使用する全コレクション5つをバージョン範囲固定で列挙、Python依存も明記 |
| SEC-10 | **済(一部)** | stringData+SSAの2回目 `changed=0` は本番で実測済み(Phase M検証)。PSA/NetworkPolicy/quota、Portainer権限の限定は改善計画 |
| APP-01 | **計画** | 初回のみ有効な環境変数の「作成後不変」assert化 |
| REL-09 | **計画** | 主目的検証の既定fail化(`*_verification_strict` 導入) |

## P3

| ID | 状態 | 対応内容 |
| --- | --- | --- |
| QA-01 | **済(一部)** | ansible-lintをローカル/エディタ標準化(`.ansible-lint`、0 failure・productionプロファイル。VSCode拡張がリアルタイム検査)。GitHub Actions版CIは一度導入後、利用者判断で撤去(6b1810e) — 必要になれば82de36e時点のci.ymlを履歴から復元可能。冪等テスト・failure-pathテストは改善計画 |
| DOC-01 | **済** | requirements案内パス、vault/README全面刷新(現行5ファイルに整合)、未参照の旧 `vault/proxmox.yml` 削除、defaults内の旧docs参照、devcontainerのinterpreterPath/schema globを修正 |
| DEV-01 | **計画** | base imageのdigest固定とExecution Environment定義の共有 |

## 検証(対応後)

- 全playbook syntax-check PASS
- `provision.yml --check`: 本番13台 **changed=0 維持**(SAF-02/REL-01の比較ロジック変更後も収束状態を破壊していないことを確認)
- `deploy.yml --check`: preflight込みで **changed=0 維持**
- SEC-03はクラスタ反映済み(ClusterRole/Binding削除、homarr 1/1稼働)
- yamllint 全ファイルPASS
