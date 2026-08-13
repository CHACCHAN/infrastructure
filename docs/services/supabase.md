# supabase.yml
[Supabase](https://supabase.com/docs/guides/self-hosting/docker)(セルフホスト)のVMを、
テンプレート構築からVM内部のセットアップまで一気通貫で構築します。
完了時点で、ダッシュボードとAPI、Postgresが使える状態になります。

VM内のセットアップは**Debian 13専用**のため、既定で Debian 13 を構築します。

## 2つの実行方法
対象の決め方だけが違い、それ以降の処理は共通です。

| 実行方法 | 対象 | 台数 |
| --- | --- | --- |
| インベントリ版(既定) | `inventories/lab/supabase.yml` のホスト。`--limit` で選択 | 1台〜全台 |
| 手動指定版(`-e "manual=true"`) | `-e` で指定した1台 | 1台 |

```sh
# インベントリ版(パスワードとAPIキーはVM内で自動生成されます)
ansible-playbook playbooks/services/supabase.yml --ask-vault-pass -vv -e "vm_ssh_password=<パスワード>"

# 公開URLを指定する(リバースプロキシ経由で使う場合)
ansible-playbook playbooks/services/supabase.yml --ask-vault-pass -vv \
-e "vm_ssh_password=<パスワード> supabase_public_url=https://supabase.example.com"

# 手動指定版
ansible-playbook playbooks/services/supabase.yml --ask-vault-pass -vv \
-e 'manual=true vm_node=<ノードIP> proxmox_storage=<ストレージ名> \
    vm_id=<VMID> vm_name=<VM名> vm_ipv4=<IPv4/CIDR> vm_ipv4_gw=<ゲートウェイ> \
    vm_ssh_user=<ユーザ名> vm_ssh_password=<パスワード> \
    vm_ssh_pubkey_file=~/.ssh/<公開鍵> vm_ssh_prikey=~/.ssh/<秘密鍵> \
    vm_hardware={"cpu":{"cores":4,"type":"host"},"memory":{"size":8192},"resize":[{"bus":"scsi","index":0,"size":48}]} \
    vm_options={"agent":1,"onboot":1}'
```

- インベントリの `supabase` グループが空なら、`manual=true` なしでも手動指定版になります
- ⚠ **リソースを多く使います**(11コンテナ / 推奨4コア・8GB・ディスク48GB)。
  `resize` を省くと手順8の空き容量チェックで中止します
- ⚠ **ダッシュボードはBasic認証のみ、Postgresもポートを公開**します。
  LAN内に閉じるか、リバースプロキシ側で保護してください

## 秘密情報の扱い(vaultは使いません)
Supabaseのパスワードとキーは**VM内で公式スクリプトが生成**し、
VM内の `/opt/supabase/supabase/docker/.env` に保存されます。
そのため、このplaybookに渡す秘密情報はありません(vaultファイルも増やしていません)。

```sh
# 生成された値の確認(VM内)
sudo grep -E '^(ANON_KEY|SERVICE_ROLE_KEY|DASHBOARD_PASSWORD|POSTGRES_PASSWORD)=' \
  /opt/supabase/supabase/docker/.env
```

- 再実行しても**作り直されません**(既存の `.env` から引き継ぎます)
- 自分で決めた値を使う場合は `-e "supabase_postgres_password=..."` のように渡せます
  (⚠ 一度DBを作った後に変えると整合しなくなります)
- ⚠ **`.env` と `volumes/db/data` は対**です。バックアップは必ず両方まとめて取ってください

## インベントリ
[inventories/lab/supabase.yml](../../inventories/lab/supabase.yml) に**1台1ホスト**で書きます。
ホスト名はVMのIPアドレスです。

| 優先順位 | 指定方法 |
| --- | --- |
| 高 | `-e "変数名=値"` |
| 中 | インベントリの `hosts:` 配下(VMごと) |
| 低 | インベントリの `vars:`(グループ共通) |

## 実行される順番
1. [proxmox_template_build.yml](../proxmox/proxmox_template_build.md) —
   テンプレート構築。**ノードごとに1台だけが担当**します(VMID衝突を避けるため)
2. [proxmox_vm_build.yml](../proxmox/proxmox_vm_build.md) — VMをクローン
3. [proxmox_vm_hardware.yml](../proxmox/proxmox_vm_hardware.md) —
   ハードウェア調整(`vm_hardware` 指定時のみ)
4. [proxmox_vm_options.yml](../proxmox/proxmox_vm_options.md) —
   動作設定(`vm_options` 指定時のみ)
5. [proxmox_vm_cloudinit.yml](../proxmox/proxmox_vm_cloudinit.md) — cloud-init設定
6. [proxmox_vm_powerctl.yml](../proxmox/proxmox_vm_powerctl.md) — VMの起動
7. SSHでログインできるまで待機(cloud-initの完了待ち)
8. [playbooks/vms/supabase.yml](../vms/supabase.md) —
   VM内部のセットアップ、VM再起動、実行元の端末からの接続確認

手順1〜6はProxmoxノードへ、手順7〜8はVM自身へ接続します。
**手順8は初回で10分以上かかることがあります**(イメージの取得とDBの初期化のため)。

## VMごとに指定する変数
インベントリの `hosts:` 配下、または `-e` で指定します。

| 変数 | 内容 |
| --- | --- |
| `vm_id` | 新規VMのVMID |
| `vm_name` | VM名 |
| `vm_node` | 構築先ProxmoxノードのIPアドレス |
| `vm_ipv4` | VMの固定IP(CIDR)。省略時は**ホスト名 + `vm_ipv4_prefix`** から組み立てます |

`proxmox_ip` ではなく `vm_node` なのは、`-e proxmox_ip=...` を使うと呼び出し先が
そのIPを別の構築対象として登録してしまうためです。

## 共通で指定する変数
インベントリの `vars:`、または `-e` で指定します。

| 変数 | 内容 |
| --- | --- |
| `proxmox_storage` | テンプレートとVMのディスクを置くストレージ名 |
| `vm_ipv4_prefix` / `vm_ipv4_gw` | プレフィックス長(既定 `24`)/ ゲートウェイ |
| `vm_ssh_user` | cloud-initで作成するログインユーザー |
| `vm_ssh_pubkey_file` | VMに登録するSSH公開鍵のファイルパス(`vm_ssh_pubkey` で内容の直接指定も可) |
| `vm_ssh_prikey` | 秘密鍵のパス。VM内セットアップのSSH接続に使います |
| `vm_hardware` / `vm_options` | ハードウェア / 動作設定(後述) |

## ハードウェア・動作設定の既定値
インベントリの `vm_hardware` / `vm_options` で指定しています。書式は
[proxmox_vm_hardware.md](../proxmox/proxmox_vm_hardware.md) /
[proxmox_vm_options.md](../proxmox/proxmox_vm_options.md) を参照してください。

| 項目 | 既定値 | 指定 |
| --- | --- | --- |
| CPU / RAM | 4コア(`x86-64-v2-AES`)/ 8GB | `cpu: {cores: 4, type: x86-64-v2-AES}` `memory: {size: 8192}` |
| BIOS / マシン / 画面 | SeaBIOS / Q35 / 標準VGA | `options: {bios: seabios, machine: q35, vga: std}` |
| ディスク | 48GiB | `resize: [{bus: scsi, index: 0, size: 48}]` |
| QEMUエージェント / 自動起動 | 有効 | `agent: 1` `onboot: 1` |

- 公式の最小構成は2コア / 4GBです。DBとStorageの実データが増えるとディスクを消費します
- ディスクは **`resize`(既存ディスクの拡張)で指定します**。`disks` に書くと新しい空ディスクに
  置き換わります
- `-e` で `vm_hardware` を渡すとインベントリの値は**置き換え**になるため、
  変更しない項目も併せて指定してください(JSONにはスペースを含めないこと)

## Supabase本体の設定
`supabase_` で始まる変数はそのまま手順8へ渡ります。
**`.env` に入る値はすべて変数で指定できます**(全項目の対応表は
[docs/vms/supabase.md](../vms/supabase.md#指定できる項目))。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `supabase_public_url` | `http://<VMのIP>:8000` | ブラウザ・アプリから見たURL(**リバースプロキシ経由なら必須**) |
| `supabase_site_url` | `http://localhost:3000` | 認証後の戻り先(アプリのURL) |
| `supabase_ref` | (固定のコミット) | 取得する公式構成のリビジョン。イメージのタグはこの中で固定 |
| `supabase_compose_files` | `[docker-compose.yml]` | ログ収集やHTTPS化の定義を重ねる |
| `supabase_kong_http_port` / `_https_port` | `8000` / `8443` | API + ダッシュボード |
| `supabase_postgres_port` | `5432` | Postgres(Supavisorのセッションモード) |
| `supabase_pooler_proxy_port_transaction` | `6543` | Supavisor(トランザクションモード) |
| `supabase_enable_email_autoconfirm` | `false` | メールを送れない環境では `true` に |
| `supabase_extra_env` | `{}` | 上記以外の環境変数 |

## 再実行・復旧
- **同じ `vm_id` での再実行はできません。** 作り直す場合は
  `playbooks/proxmox/proxmox_vm_delete.yml` で削除するか、別の `vm_id` にしてください
- 設定を変えるだけなら `playbooks/vms/supabase.yml` を直接実行してください
  (`.env` が変わったときだけコンテナを作り直します)
- ⚠ **VMを作り直すとDBのデータも失われます。** 先に
  `/opt/supabase/supabase/docker/.env` と `volumes/db/data` をバックアップしてください

## 注意
- `--ask-vault-pass` は必須です(`vault/proxmox.yml` を読むため)
- 手動指定版では `--limit` を使わないでください(`hosts: localhost` のプレイが
  対象外になり、構築対象が登録されません)
- VM内の設定は `vm_` 接頭辞で指定します。`ssh_user` や `ipv4` をそのまま `-e` で渡すと
  **テンプレート側にも**焼き込まれてしまうためです
- 公開する場合は [cloudflare-ddns-ui.yml](cloudflare-ddns-ui.md) でDNSを更新し、
  HTTPS化(`docker-compose.caddy.yml` など)を併せて検討してください
