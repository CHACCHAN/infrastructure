# VM内セットアップPlaybook(playbooks/vms/)
- このディレクトリはProxmox VM「内部」に対してSSH接続で操作を行います。
  ホスト側の操作(ハードウェア設定・VMの起動停止など)は `playbooks/proxmox/` の管轄です
- **Debian13(cloud image)専用**。対象VMは起動済みである必要があります
- インベントリファイルは使用しません。接続先は `vm_ip` にIPアドレスを直接指定します

## Playbook一覧
| Playbook | 内容 |
| --- | --- |
| [development.yml](development.md) | 開発専用VM(Cockpit/Docker/k8s CLI、任意でRDPデスクトップ) |
| [authentik.yml](authentik.md) | Authentik(SSO/IdP)をDocker Composeで構築 |
| [kubernetes.yml](kubernetes.md) | Kubernetes(k3s)のコントロールプレーン / ワーカーを構築 |
| [technitium-dns.yml](technitium-dns.md) | Technitium DNS ServerをDocker Composeで構築 |
| [cloudflare-ddns-ui.yml](cloudflare-ddns-ui.md) | cloudflare-ddns-ui(公開IPの変化をCloudflareのAレコードに反映)をDocker Composeで構築 |
| [wg-easy.yml](wg-easy.md) | wg-easy(WireGuardのVPNサーバー + Web UI。認証は既定でOIDC)をDocker Composeで構築 |
| [supabase.yml](supabase.md) | Supabase(セルフホスト。Postgres + API + 認証 + Studio)をDocker Composeで構築 |
| [proxmox-backup-server.yml](proxmox-backup-server.md) | Proxmox Backup Server(PBS)をAPTパッケージで構築(Dockerは不使用) |

## 全playbook共通の指定
```sh
ansible-playbook playbooks/vms/<playbook名>.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名>"
```

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `vm_ip` | (必須) | 対象VMのIPアドレス |
| `vm_ssh_user` | (必須) | SSH接続するユーザー名(cloud-initで作成したユーザー) |
| `vm_ssh_prikey` | (必須) | SSH秘密鍵のパス |
| `vm_timezone` | `Asia/Tokyo` | タイムゾーン |
| `vm_locale` | `ja_JP.UTF-8` | ロケール |
| `vm_zram_percent` | `50` | zram(圧縮メモリ上のswap)に割り当てるRAM使用率(%) |
| `vm_reboot_after_setup` | `true` | 構成完了後にVMを再起動するか |

- ログインパスワードはここでは設定しません。**VM構築時のcloud-initで設定したパスワード**を
  使います(変更は `playbooks/proxmox/proxmox_vm_cloudinit.yml` またはVM内の`passwd`)
- 各playbookは最後にVMを再起動します(dockerグループへの追加とカーネル更新の反映のため)

## 共通セットアップ(roles/common・roles/docker・roles/vm_connect)
複数のロールで使う処理は共通ロールに置いて `import_role` で共有しています。
**どれを使うかは各サービスロールが選びます**(例: Dockerは`kubernetes`以外の全ロール。
`kubernetes`はk3s同梱のcontainerdを使うため入れません)。

| 場所 | 内容 | 使うロール |
| --- | --- | --- |
| `vm_connect`(main.yml) | 接続先VMの登録とSSH疎通確認 | 全playbook |
| `common/tasks/assert_debian.yml` | 対象OSがDebianであることの確認 | 全ロール |
| `common/tasks/main.yml` | 共通初期セットアップ一式。下の7ファイルを順番に実行する | 全ロール |
| ├ `update_packages.yml` | apt update && upgrade | 〃 |
| ├ `configure_timezone.yml` / `configure_locale.yml` | タイムゾーン / ロケール | 〃 |
| ├ `configure_swap.yml` | zramによる動的swap | 〃(`kubernetes`は既定で無効化) |
| ├ `configure_admin_group.yml` | SSHユーザーをsudoグループに追加 | 〃 |
| ├ `install_base_packages.yml` | git, curl, nfs-common等 | 〃 |
| └ `install_qemu_guest_agent.yml` | QEMUゲストエージェント | 〃 |
| `docker`(main.yml) | Docker(compose込み)とdockerグループ追加 | `kubernetes` 以外の全ロール |
| `common/tasks/check_disk_space.yml` | イメージ取得前の空き容量チェック(不足なら中止) | `authentik` / `technitium` / `supabase` |
| `common/tasks/configure_ufw_ports.yml` | ufwが有効な場合のみサービスのポートを開放 | `development` 以外の全ロール |
| `docker/tasks/deploy_compose.yml` | compose定義(テンプレート)の配置とコンテナ起動 | `authentik` / `technitium` / `cloudflare_ddns_ui` / `wg_easy` |
| `common/tasks/load_existing_env.yml` | 既存 `.env` の読み込み(パスワード等の引き継ぎ用) | `authentik` / `technitium` / `wg_easy` |
| `common/tasks/reboot_vm.yml` | 構成反映のためのVM再起動 | 全playbook |

- 個別タスクは `import_role` の `tasks_from` で単体でも呼び出せます。
  サービス固有の値(対象ディレクトリ・ポート等)は `vars:`(`svc_` 接頭辞)で渡します
- `deploy_compose.yml` だけは呼び出し元ロールのテンプレートを `role_path` から探すため、
  `import_role` ではなく相対パスの `import_tasks` で呼び出します

- `nfs-common` はどのVMからでもNFS共有をマウントできるよう基本パッケージに含めています
  (Kubernetesのnfs系ボリュームもノード側のこれを使います)

- QEMUゲストエージェントは、ホスト側で `qm set <vmid> --agent enabled=1` が必要です
  (`playbooks/proxmox/` の管轄。未設定でもplaybookは失敗せず案内を表示します)
- `docker.service` を有効化するため、`restart: unless-stopped` のコンテナは
  VM再起動後に自動復帰します
