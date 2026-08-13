# プロジェクト全体レビュー・改善提案書

- レビュー日: 2026-08-13 (UTC)
- 対象コミット: `e38ddf6` (`main` / `origin/main`)
- 対象範囲: 現行の `inventory/`、`playbooks/`、`roles/`、`vault/`、開発環境・文書、および追跡済みの `.legacy/`
- 方針: 読み取り専用レビュー。実環境の Proxmox / VM / Kubernetes には接続・変更していない

## 総評

「PVE APIによるVM構築」「SSHによるVM内構成」「Kubernetesへの適用」を3ドメインに分けた構造は明快です。変数の配置、ロール名、適用順も追いやすく、入力検証、`no_log`、ファイル権限、チェックサム検証、直列実行など、安全性を意識した実装が多く見られます。

一方で、現状は**公開リポジトリに平文のProxmox APIトークンシークレットが残っている**ため、まずコード改善ではなくインシデント対応が必要です。また、PBSのディスク初期化、PVEの対象同定、HomarrのRBAC、SSHホスト鍵、暗黙のKubernetes接続先など、誤操作・侵害時の影響が大きい箇所があります。「収束済みなら `changed=0`」「Gitが単一の真実」という目標に対しても、pending設定、無条件再起動、Kubernetesリソースの削除非追従、バックアップ不足が残っています。

優先度は次の意味で使用します。

| 優先度 | 意味 |
| --- | --- |
| P0 | 既に露出している可能性があるため直ちに対応 |
| P1 | 次回の本番相当実行より前に対応 |
| P2 | 短期の改善計画へ入れる |
| P3 | 保守性・開発体験の継続改善 |

## P0: 緊急対応

### SEC-01: 公開Git履歴に平文のProxmox APIトークンシークレットがある

**根拠**

- `.legacy/proxmox-guest-ansible/group_vars/vault.yml:1`
- `.legacy/proxmox-personal-ansible/group_vars/vault.yml:1`
- 対応する接続先・ユーザー・トークンID: `.legacy/proxmox-guest-ansible/group_vars/all.yml:1-3`、`.legacy/proxmox-personal-ansible/group_vars/all.yml:1-3`
- `.gitignore:1` はルート直下の `group_vars/vault.yml` にしか一致せず、上記2ファイルは追跡済み
- 2つの値は異なる非プレースホルダー値で、Ansible Vaultヘッダーを持たない
- 初回コミット `d3a48fd` から履歴に存在する
- `origin` は `CHACCHAN/infrastructure` で、レビュー時点の[GitHubリポジトリ](https://github.com/CHACCHAN/infrastructure)は `Public`
- `docs/migration/phase1-design.md:221` にも平文秘密と履歴残存が既知事項として記録されている

**影響**

値が現在も有効なら、権限範囲内のProxmox API操作を第三者が実行できます。現在無効でも、漏えいした資格情報として扱う必要があります。ファイルを削除・暗号化するだけでは、Git履歴、既存clone、fork、キャッシュに残った値は無効になりません。

**直ちに行うこと（この順序）**

1. 該当する2トークンをProxmox側で**失効**する。必要な場合のみ、最小権限・別IDで再発行する。
2. トークンの権限、最終利用時刻、PVE API / 認証ログを、初回公開時点から確認する。不審操作があれば影響範囲を調査する。
3. BFG Repo-Cleanerまたは`git filter-repo`で全履歴から値とファイルを除去し、force-push後にclone利用者・fork所有者へ再cloneを依頼する。ホスティング側キャッシュの扱いも確認する。
4. `.legacy/`を公開履歴へ残す必要がなければ削除する。残す場合でも秘密値は必ずダミーへ置換し、広いパターン（例: `**/vault.yml`）で誤追跡を防ぐ。
5. pre-commitとCIにgitleaks等を導入し、作業ツリーだけでなくGit履歴も検査する。

> この文書にはシークレット値を転記していません。履歴除去よりも、サーバー側での失効を先に行ってください。

## P1: 次回実行前に対処すべき事項

### SAF-01: PBSのデータディスク自動判別が使用中ディスクを破壊し得る

**根拠:** `roles/vm_pbs/tasks/prepare_data_disk.yml:47-54` は「パーティションがない」だけで候補にし、同ファイル `71-101` でGPTを作成します。`roles/vm_pbs/tasks/validate.yml:42-51` は明示デバイスが `/dev/...` 形式かしか検証せず、OSディスクとの一致も拒否しません。

**影響:** whole-disk filesystem、LVM PV、RAIDメンバーなどはパーティションなしでも使用中です。また、誤ってOSディスクを明示すると、そのディスクへGPTを書き得ます。バックアップサーバーの役割上、最も避けるべきデータ損失経路です。

**改善案:** 自動選択をやめて `/dev/disk/by-id/...` の明示を原則とし、初期化専用の確認フラグを要求してください。少なくとも `lsblk`、`blkid`、`wipefs` で署名、FSTYPE、mountpoint、children、holdersを調べ、OSディスクとその親子、LVM/RAID、既存署名のあるデバイスを拒否します。初期化直前に対象ID・サイズ・シリアルを再表示してassertするテストも必要です。

### SAF-02: PVEの対象をVMIDだけで信用している

**根拠:** `roles/pve/tasks/find_vm.yml:3-15` はVMID検索後、名前・node・VM種別・template状態を宣言と照合しません。provisionは `roles/pve_vm/tasks/configure.yml:81-89` で危険なNIC更新も許可します。power/destroyも `playbooks/pve/power.yml:34-45`、`playbooks/pve/destroy.yml:25-70` で同じVMIDを操作します。

**影響:** inventoryのVMIDを別VMへ誤設定した場合、別VMの名前、CPU、NIC、cloud-init、電源を変更できます。destroyの二重入力も、同じ誤VMIDを2回入力すれば通ります。

**改善案:** 更新前に `vmid + name + node + type=qemu + template期待値` を照合し、不一致なら停止します。既存VMの意図的な取り込みだけを `pve_allow_adopt=true` のような明示フラグで許可し、destroyはVM名も確認入力に含めてください。

### REL-01: 稼働中PVE VMのpending設定を収束済みと扱えない

**根拠:** `roles/pve_vm/tasks/configure.yml:5-9` と `roles/pve_vm/tasks/cloudinit.yml:17-21` は `proxmox_vm_info(config=current)` を使います。インストール済み `community.proxmox 2.0.0` の説明では、`current` は実行中構成、`pending` は保留変更込みです。更新後の `roles/pve_vm/tasks/power.yml:11-20` は既にstartedなら再起動しません。

**影響:** CPU、machine、NIC、cloud-init等の変更がpendingになった場合、playbookは成功しても実行中構成は旧値のままです。次回も同じ差分を検出し、`README.md:110` の「全タスクが冪等」と一致しません。

**改善案:** 比較にはpendingを含む構成を使い、再起動が必要な変更を分類します。自動再起動、保守時間まで保留、または明示的に失敗、のどれかを変数で選べるようにし、実行結果にpending内容を表示してください。

### SEC-02: SSHホスト鍵検証が全VMで無効

**根拠:** `playbooks/vm/authentik.yml:17-18`、`ddns.yml:19-20`、`dev.yml:17-18`、`k3s.yml:21-22,40-47`、`pbs.yml:17-18`、`supabase.yml:19-20`、`technitium.yml:17-18`、`wg-easy.yml:19-20` が `StrictHostKeyChecking=no` と `/dev/null` を指定しています。さらに `.devcontainer/devcontainer.json:41-45` で全体の `ANSIBLE_HOST_KEY_CHECKING=False` を設定しています。

**影響:** 管理LAN上のMITMが新規VMになりすますと、AnsibleがCloudflare/OIDC/Supabase/K3s等の秘密を含むモジュール引数を偽ホストへ送る可能性があります。

**改善案:** 再構築時だけ旧known_hostsエントリを除去し、PVE/QEMU guest agent、信頼できるコンソール、またはSSH Host CAから取得した鍵を登録してから接続します。例外を設ける場合も初回起動・対象IP・1回に限定し、その後必ず検証を有効化してください。

### SEC-03: Homarrがクラスタ内の全Secretを読み取れる

**根拠:** `roles/k8s_homarr/defaults/main.yml:90-93` のコメントは「必要になるまで無効」としながら `rbac.enabled: true` です。固定チャート8.26.0を安全に `helm template` した結果、Homarr ServiceAccountへ、クラスタ全体の`secrets`を含むリソースに対する `get/list/watch/use` を持つClusterRole/Bindingが生成されることを確認しました。

**影響:** Homarr Podまたはアカウントが侵害されると、Cloudflare、DB、OIDC、証明書関連など他アプリの資格情報まで取得され得ます。

**改善案:** Kubernetes連携が不要なら `rbac.enabled: false` にします。必要なら上流の広いClusterRoleを使わず、対象namespace・対象リソースだけのRole/ClusterRoleを作り、Secret権限を除外してください。ServiceAccount tokenは自動マウントを避け、必要時のみ短命なprojected tokenを使います。

### SAF-03: Kubernetesの接続先が暗黙のcurrent-context

**根拠:** `playbooks/k8s/deploy.yml:5-14` と `roles/k8s/tasks/apply.yml:18-27` はkubeconfig、context、API hostを指定しません。`.devcontainer/devcontainer.json:33-39` は利用者の `~/.kube` 全体をマウントします。

**影響:** current-contextを取り違えると、別クラスタへhome-lab用マニフェストと復号済みSecretを適用できます。`force=true` では既存フィールド所有権も奪います。

**改善案:** 専用のkubeconfigとcontextを必須入力にし、Secretを扱う前にAPI URL、cluster名、namespace UID、期待する識別用ConfigMap等をpreflightで照合します。環境名と確認値を二重指定させ、`force` は対象アプリと理由も必須にしてください。

### SEC-04: 認証なしのDDNS管理画面が全インターフェースへ公開される

**根拠:** `roles/vm_ddns/defaults/main.yml:14-18` は管理画面に認証がなくレコード削除も可能と説明しつつ、bind既定値を `0.0.0.0` にしています。現行inventoryは上書きせず、`roles/vm_ddns/templates/docker-compose.yml.j2:20-25` がhost portを公開します。Kubernetes側のforward-authを通らず、VMのIPへ直接到達できます。

**影響:** VMへ到達できるLAN利用者や侵害済み端末からDNS設定を操作できます。

**改善案:** 既定を `127.0.0.1` にし、SSH tunnel、VPN、または認証・TLS付きreverse proxy経由に限定します。特定LAN IPへのbindは「非公開」ではないため、`roles/vm_ddns/tasks/validate.yml:120-129` の判定もloopback基準へ直してください。

### SEC-05: Authentik初回管理者を先取りされる時間窓がある

**根拠:** `roles/vm_authentik/defaults/main.yml:35-36` ではbootstrap password/tokenが既定で未指定です。`roles/vm_authentik/templates/docker-compose.yml.j2:46-48` は管理画面を全IFへ公開し、`playbooks/vm/authentik.yml:49-54` は未認証のinitial-setup URLを案内します。

**影響:** 新規構築直後、管理者より先にURLへ到達した者が初期管理者を設定できる可能性があります。認証基盤自体の乗っ取りにつながります。

**改善案:** Vault内のbootstrap password/tokenを必須にし、自動初期化を完了させてから公開します。または初期設定完了までlocalhost/管理IPだけにbindし、HTTPではなくTLS経由に限定してください。

### SEC-06: Authentik workerがhost root相当のDocker socketを常時持つ

**根拠:** `roles/vm_authentik/templates/docker-compose.yml.j2:53-72` はworkerをrootで実行し、hostの `/var/run/docker.sock` をread-write mountします。

**影響:** Authentik worker内でコード実行を許した場合、Docker APIからprivileged containerを作るなどしてVM hostのroot権限へ到達できます。認証基盤の侵害がVM全体の侵害へ直結します。

**改善案:** outpost自動管理などDocker連携を使わない構成ではsocket mountを既定無効にします。必要な場合もDocker socket proxyで許可APIを限定し、専用hostへの分離、監査、image更新を組み合わせてください。

### SEC-07: mutableな未検証コードをrootで実行する経路が複数ある

**根拠**

- Docker: `roles/vm_docker/tasks/main.yml:12-26` が `get.docker.com` をchecksumなしで実行
- K3s: `roles/vm_k3s/tasks/install_k3s.yml:9-29` が `get.k3s.io` をchecksumなしで実行
- Helm: `roles/vm_dev/tasks/install_helm.yml:13-27` がGitHubの`main`ブランチ上のscriptを実行
- Cockpit Docker Manager: `roles/vm_dev/tasks/configure_cockpit_dockermanager.yml:1-15` が第三者APT repoを `trusted: true` で登録
- Cockpit Navigator: `roles/vm_dev/tasks/install_cockpit_navigator.yml:9-51` がその時点の最新debを署名/checksumなしで導入

加えて `roles/vm_k3s/defaults/main.yml:8-10` はversion未指定のstable channelで、新規nodeだけが実行時点の最新版になり、既存nodeは `roles/vm_k3s/tasks/check_installed.yml:14-19` により旧版を維持します。

**影響:** 配布元、アカウント、DNS/TLS、リポジトリの侵害がVM上のroot実行へ直結します。同じGitコミットから異なる成果物や、意図しないK3s version skewも生成されます。

**改善案:** 署名済み公式APT repositoryを優先し、versionとSHA256/digestを固定します。署名のない第三者パッケージは取得物を内部ミラーで検証するか、既定無効のopt-inにします。K3s/Helmも固定release artifactをchecksum検証して導入してください。

### SEC-08: K3s workerへserver tokenを配布している

**根拠:** `roles/vm_k3s/tasks/fetch_token.yml:9-17,30-33` は `/var/lib/rancher/k3s/server/node-token` を取得し、`roles/vm_k3s/templates/config.yaml.j2:5-10` でagentの設定へ保存します。

**影響:** K3sのserver tokenはserver/agent参加に使え、bootstrap data保護にも関係する強い秘密です。workerのroot侵害がコントロールプレーン相当の資格情報漏えいへ拡大します。

**改善案:** server側でdistinctな`agent-token`を設定し、workerには `/var/lib/rancher/k3s/server/agent-token` のみを配ります。可能なら短命bootstrap tokenを使い、server tokenはdatastoreと一緒にcontrol-plane側だけでバックアップしてください。参考: [K3s token documentation](https://docs.k3s.io/cli/token)

### REL-02: Kubernetes宣言から削除したリソースがクラスタに残る

**根拠:** `roles/k8s/tasks/apply.yml:18-27` は `state: present` のSSAだけです。`inventory/group_vars/all/k8s.yml:6-19` のアプリ登録や外部routeから項目を削除しても、対応するabsent/prune処理はありません。Helm releaseも作成していません。

**影響:** 廃止したIngress、Service、EndpointSlice、RBAC、Deployment等が残り、公開経路や権限が意図せず存続します。「Gitが単一の真実」になりません。

**改善案:** 管理ラベルとallowlistに基づく制御されたprune、明示的な`absent`登録簿、または実Helm releaseのどれかを採用します。削除dry-run、対象一覧確認、rollbackを必須にし、namespace全体を無差別pruneしないでください。

### SEC-09: PVE/TrueNASバックエンドのTLS認証を無効化している

**根拠:** `inventory/group_vars/all/k8s.yml:29-36` が `insecure_skip_verify: true` を宣言し、`roles/k8s_external/templates/external.yaml.j2:13-16` がTraefik `insecureSkipVerify`へ出力します。PVE API側も `playbooks/pve/*.yml` のmodule defaultsで `validate_certs: false` です。

**影響:** ブラウザからTraefikまでTLSでも、その先の管理画面/API接続はLAN内MITMを認証できません。管理ログインやAPI tokenの窃取につながります。

**改善案:** 内部CAまたは信頼できる証明書を発行し、AnsibleコントローラとTraefikへCA bundleを配布します。正しいSNIを指定し、証明書検証無効は移行期間限定にしてください。

### REL-03: 主要データの分離・バックアップ・復元手順が不足している

**根拠:** `roles/k8s_postgresql/defaults/main.yml:31-50` は5アプリのDBだけを作り、全アプリが`postgres` superuserを共有します（例: `roles/k8s_guacamole/templates/guacamole.yaml.j2:195-204`）。`52-60` のNFS PVC `Retain` は削除抑止であってバックアップではありません。リポジトリ内にpg_dump/WAL/PITR、オフサイトコピー、復元テストはありません。K3sもinventory上1 serverで、`roles/vm_k3s/defaults/main.yml:52-54` の既定はSQLiteです。

**影響:** 1アプリのDB資格情報漏えいが全DBへ波及します。NFS/TrueNAS、単一control-plane、共有PostgreSQLの障害時に、Gitだけでは状態を復元できません。

**改善案:** アプリごとにlogin role・password・ownerを分け、PUBLIC権限を見直します。PostgreSQLは世代管理付きdumpとWAL/PITRまたはストレージsnapshotを別障害ドメインへ送り、定期restore drillを行います。K3s datastoreとserver tokenも対で保全し、可用性が必要なら3 serverのembedded etcdを検討してください。外部で既にバックアップしている場合も、このリポジトリに責任範囲、RPO/RTO、復元確認日を記録します。

### NET-01: Docker公開ポートに対しUFWが実効的な境界になっていない

**根拠:** `roles/vm/tasks/configure_ufw_ports.yml:1-6` 自身がDocker portはUFW INPUTを通らないと記載しています。処理は `26-37` で送信元制限なしのallow追加だけです。Supabaseは `roles/vm_supabase/tasks/main.yml:47-56` でKongだけでなくPostgreSQL/poolerも公開対象にします。

**影響:** 管理画面やDB portが、想定以上のインターフェース・ネットワークから到達可能になります。

**改善案:** Compose側でbind addressを宣言し、DB/poolerはlocalhostまたは専用管理NICへ限定します。必要なら`DOCKER-USER`/nftablesをAnsibleで明示管理し、許可元CIDRとinterfaceを宣言してください。外部ホストからの到達/遮断テストも追加します。

## P2: 短期改善

### REL-04: 全VM Playbookが差分なしでも再起動する

`roles/vm/tasks/reboot_vm.yml:5-10` は変更有無を見ず、既定trueなら再起動します。8本のVM Playbookがpost taskから呼び、K3sは `playbooks/vm/k3s.yml:53-67` で単一control-planeから順に毎回再起動します。これは無停止性と`changed=0`の主張に反し、単一レプリカworkloadを中断します。

`/var/run/reboot-required`、kernel/package変更、明示的なnotifyのいずれかだけで再起動し、強制再起動は別フラグにしてください。K3s workerはdrain/uncordonとPDB確認を行い、control-plane再起動は保守操作として分離します。

### REL-05: Supabaseのコンテナ健全性判定に抜けがある

`roles/vm_supabase/tasks/verify_service.yml:6-27` の `docker compose ps` は `--all` なしのため停止済みserviceを一覧から落とします。またHealthが`starting`でないことしか見ず、`unhealthy`を成功扱いします。

`docker compose config --services` と `docker compose ps --all --format json` を突き合わせ、全serviceが存在し、State=`running`、Healthが未定義または`healthy`であることを検証してください。

### REL-06: K3sの役割がinventory順だけで決まる

`playbooks/vm/k3s.yml:14-24` は先頭hostをserver、残りをagentと毎回計算します。`roles/vm_k3s/tasks/check_installed.yml:4-19` は既存versionだけを見て役割不一致を検出しません。並べ替えで既存serverをagent設定へ上書きし得ます。

`kubernetes_node_role`をhost varで明示し、既存systemd unit・data directoryから実役割を検出して不一致時は停止します。役割変更は通常収束から切り離したmigration手順にしてください。

### REL-07: 必須Secret欠落やrollout失敗でもKubernetes deployが成功し得る

例として `roles/k8s_cloudflared/tasks/main.yml:5-22` はtoken変数が未定義ならSecretを黙ってskipし、`23-32` でDeploymentを適用します。共通の `roles/k8s/tasks/apply.yml:18-29` にwaitはなく、多くのロールがDeployment/StatefulSet/CertificateのReadyを確認しません。

各アプリの必須Secret名・必須keyを最初にassertし、全preflight完了後に書き込みを始めます。適用後はrollout、PVC、Certificate、DNS/HTTP等の最小smoke testを待ってください。

### REL-08: PVE宣言を減らした場合や追加ディスク変更のdriftが残る

- `roles/pve_vm/tasks/configure.yml:27-51,81-89`: 宣言対象のNICしか扱わず、削除した`netN`が残る
- `roles/pve_vm/tasks/cloudinit.yml:10-15,44-48`: `cluster_ip`削除後も`ipconfig1`を消さない
- `roles/pve_vm/tasks/disks.yml:44-54`: 追加ディスクの既存size/storage変更に`state=present`を使い、resize/moveを収束しない
- `roles/pve_template/tasks/check_existing.yml:8-14` と `vars/os/*.yml`: `latest/current`イメージでも既存templateを更新せず、キャッシュ済みイメージのdigest再検証・rotation方針もない

余剰NIC/cloud-initを検出して削除または安全停止し、追加ディスクは現状取得後に`resized`/`moved`を明示します。テンプレートはimmutableなrelease/digestを記録し、更新を通常provisionと分けた管理操作にしてください。

### CFG-01: inventoryに一時資源・接続不能になり得る宣言が残る

- `inventory/hosts.yml:44-53` の停止済み`dev-migration`はdev既定の`pve_vm_power: started`を継承し、全体provisionで起動する
- `inventory/hosts.yml:113-116` の`migration-test`は `172.16.19.90/24` に対し、`inventory/group_vars/all/pve.yml:7-8` の `172.16.11.1` gatewayを継承する
- `inventory/group_vars/dev.yml:8-12` と `roles/pve_vm/tasks/cloudinit.yml:7-9,27-29` の組合せでは、dev VM新規作成時に公開鍵が入らずSSH不能になり得る

役目を終えたVM 990/992とinventoryを計画どおり整理してください。残す間は明示的に`stopped`とし、IP/gatewayの同一subnet検証、VM新規作成時の公開鍵必須検証を追加します。

### DEP-01: 依存関係が不足し、versionも固定されていない

`collections/requirements.yml:5-10` は `community.proxmox >=2.0.0`、`kubernetes.core >=6.5.0`、versionなしの`community.docker`だけです。実装は`community.general.*`と`ansible.posix.mount`も使用します。クリーンなAWX Execution Environmentではmodule解決に失敗し得ます。

使用する全collection（`community.proxmox`、`kubernetes.core`、`community.docker`、`community.general`、`ansible.posix`）とPython依存（proxmoxer、kubernetes等）を完全列挙し、検証済みの正確なversionへ固定してください。対応Ansible core、PVE、K3s/Kubernetes versionも互換表にします。

### SEC-10: SecretのSSA、namespace分離、管理UI権限を見直す余地がある

- Secret template（例: `roles/k8s_postgresql/templates/secrets.yaml.j2:7-10`）は`stringData`をSSAへ渡す。Kubernetesは`stringData`とSSAの相性に注意を示している
- `roles/k8s_namespaces/templates/namespaces.yaml.j2:1-9` は名前だけで、PSA label、NetworkPolicy、ResourceQuota、LimitRangeがない
- Portainer chart 239.5.0のrenderではServiceAccountがbuilt-in `cluster-admin`へbindされ、`roles/k8s_portainer/templates/ingress.yaml.j2:10-42` で追加認証/IP制限なしに公開される

Secretは決定的にbase64化した`data`またはSecret専用の非SSA更新経路を検証し、2回目`changed=0`と古いkey削除をテストします。namespaceはdefault-deny NetworkPolicy、PSA、quotaを基本にし、例外を文書化します。Portainerのcluster-adminが必要なら、VPN/IP allowlist、MFA/SSO、監査ログを必須のリスク受容条件にしてください。参考: [Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)

### APP-01: 初回だけ有効な設定と実状態がdriftする

Technitium (`roles/vm_technitium/tasks/configure_env.yml:1-4`) とwg-easy (`roles/vm_wg_easy/tasks/configure_env.yml:1-4`) の一部環境変数は初回起動時だけ有効ですが、再実行では.envだけ更新できます。Supabaseも既存DBのPostgreSQL passwordを.envだけ変えると接続不能になり得ます (`roles/vm_supabase/tasks/configure_env.yml:113-130`)。

bootstrap変数を「作成後不変」として差異時に停止するか、管理API/SQLを使う明示的rotation workflowを用意します。.envの宣言値だけでなくサービスの実状態を照合してください。

### REL-09: サービスの主目的未達をwarningだけで成功扱いする

wg-easyはWireGuard health失敗をrescueして完了扱いします (`roles/vm_wg_easy/tasks/verify_service.yml:99-140`)。DDNSもレコード更新未確認をdebugだけで終えます (`roles/vm_ddns/tasks/verify_service.yml:62-110`)。Nextcloudはruntimeに未固定のOIDC pluginを取得し、設定失敗でも`exit 0`です (`roles/k8s_nextcloud/defaults/main.yml:186-228`)。

主目的の検証は既定でfailし、明示的な`*_verification_strict=false`時だけwarningへ降格します。runtime downloadはversion/digest固定のimage buildへ移し、必要機能のhealth conditionを追加してください。

## P3: 保守性・開発体験

### QA-01: 自動テスト・品質ゲートがない

`.github/workflows/`、Molecule、tests、`.ansible-lint`、`.yamllint`、pre-commit設定はありません。環境にも`ansible-lint`、`yamllint`、gitleaksは導入されていません。

最低限、次をPR必須チェックにしてください。

1. gitleaks等による作業ツリー・Git履歴の秘密検査
2. yamllint、ansible-lint、全playbookのsyntax-check
3. inventory schema（必須値、VMID/IP重複、IP/gateway整合）
4. 全Helm chartのrender、kubeconform、RBAC/privileged/NetworkPolicy等のpolicy検査
5. template/golden testとSecret非表示テスト
6. disposable環境での2回実行（2回目`changed=0`・不要rebootなし）
7. PVEのpending、誤VMID、NIC削減、使用済みPBSディスク、停止/unhealthy container、prune、restoreのfailure-path test

公開CIでproduction Vaultパスワードを使わずに済むよう、CI専用fixture Vaultまたは秘密値を必要としない構文検査用変数を用意してください。

### DOC-01: 文書と開発環境に旧構成の参照が残る

- `collections/requirements.yml:2`: 存在しない `ansible/collections/requirements.yml` を案内
- `vault/README.md:8-12`: 廃止済み `playbooks/proxmox/`、`playbooks/services/` を案内し、現行`k8s_secrets.yml`も表にない
- `roles/vm_supabase/defaults/main.yml:4`、`roles/vm_wg_easy/defaults/main.yml:4` 等: 存在しない `docs/vms/...` を参照
- `docs/migration/k8s-helm-to-kustomize-2026-08-07.md:132-133`: `.migration-backup/` はignore済みと書くが `.gitignore` にない
- `.devcontainer/devcontainer.json:75`: `ansible.python.interpreterPath` は現在存在しない `/usr/local/bin/python`
- `.devcontainer/devcontainer.json:78-85`: 廃止済みディレクトリ向けのYAML schema glob
- `TASK.md` と一部roleコメントは移行前のパス・状態を現在形で記述

現行運用手順、履歴資料、廃止済み資料を明示的に分け、READMEから現行手順だけへ誘導してください。`.legacy/`削除後も必要な設計判断はADRへ要約し、古い実行コマンドを誤って使えないようにします。

### DEV-01: Dev Containerの再現性を強化する

`.devcontainer/devcontainer.json:5,17,22-23` にはmutableなimage/feature/tool指定（`trixie`、`latest`）があります。lock fileはfeature digestを一部持ちますが、Ansible collection、Python package、Helm/kubectl等を含む実行環境全体のlockにはなっていません。

base imageをdigest固定し、Execution Environment定義（`execution-environment.yml` + requirements）をCI/AWX/開発で共有することを推奨します。lock更新は依存更新PRとして行い、syntax/render/idempotence検証後に取り込みます。

## 良い点

- 3ドメインの責務、命名、変数階層が一貫し、リポジトリを読む入口が分かりやすい。
- 現行の`vault/*.yml` 7ファイルはすべてAnsible Vaultヘッダーを持つ。Secret適用や.env生成は概ね`no_log`で、`0600`/`0640`も適切に設定されている。
- destroyはVMID再入力と停止状態を要求し、root diskは縮小せず拡張だけに制限している。
- NIC更新時に既存MACを維持し、危険な`update_unsafe`を差分時だけ使う意図は良い。
- Cloud image、PBS keyring、kubectl等、チェックサム検証を行っている取得経路がある。
- K3sの直列構築、Ready確認、2NIC/flannel選択、TLS SAN、swap無効化は丁寧に設計されている。
- custom Kubernetes workloadは概ね固定tag、resource request/limit、probe、capability drop、seccompを持つ。cloudflaredには複数replica、topology spread、PDBもある。
- assertと日本語のfail messageが多く、失敗時の切り分けを意識している。

## 実施した静的検証

| 検証 | 結果 |
| --- | --- |
| `ansible-playbook --syntax-check`（現行13 playbook、既存Vault password fileを明示） | 全件PASS |
| `ansible-inventory --graph` | PASS、15ホストを解決 |
| inventory必須値 | 全15ホストに`vmid`、`node`、`ansible_host`あり |
| inventory重複 | VMID・管理IPとも重複なし |
| `.devcontainer/*.json` のJSON parse | PASS |
| 現行`vault/*.yml`のヘッダー | 7/7が`$ANSIBLE_VAULT;1.1;AES256` |
| Homarr 8.26.0のHelm render | PASS、Secretを含む広いClusterRoleを確認 |
| Git作業ツリー（レビュー開始時） | clean |

実クラスタへ変更を与えないため、playbook本実行、`--check`でのPVE/Kubernetes API接続、SSH接続、サービス疎通、復元試験は行っていません。したがって、実行環境固有の権限、ネットワーク、ストレージ、ライブ状態との一致は別途検証が必要です。

## 推奨ロードマップ

### 直ちに

1. SEC-01の2トークン失効、ログ監査、履歴除去、関係者連絡。
2. 次の自動実行を一時停止し、PBSディスク初期化対象とHomarr RBACの現状を確認。

### 次回の本番相当実行まで

1. PBS初期化guard、PVE対象同定、Kubernetes接続先preflightを追加。
2. Homarr RBACを無効化/最小化し、DDNS/Authentik管理面を限定公開へ変更。
3. SSH/PVE/backend TLSの本人確認を有効化。
4. K3s agent token分離、無条件再起動停止、バックアップ責任範囲を確定。

### その後1〜2スプリント

1. Kubernetes prune/uninstall、rollout wait、DB role分離、restore drillを実装。
2. 全依存とartifactを固定し、未検証root installerを廃止。
3. CI、secret scan、lint、render/schema/policy、idempotence/failure-path testを導入。
4. `.legacy/`、一時VM、旧template、古い文書を整理し、現行運用を一本化。
