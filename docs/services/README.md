# サービス構築Playbook(playbooks/services/)
- このディレクトリのplaybookは `playbooks/proxmox/`(Proxmox操作)と
  `playbooks/vms/`(VM内セットアップ)のplaybookを**まとめて実行**します
- 独自の処理は持たず、既存のplaybookを `import_playbook` で順番に呼び出すだけです。
  全サービスで同じになる部分は次の2箇所に共通化しています
  - `roles/provision` : 構築対象の決定(インベントリ/手動指定)・変数の解決・表示と登録
  - `playbooks/services/_provision_vm.yml` : テンプレート構築 → VM作成 → ハードウェア調整 →
    動作設定 → cloud-init → 起動 → SSH接続待ち、の共通フロー(単体では実行しない)
- 各playbookは**2つの実行方法**を持ちます(対象の決め方が違うだけで、処理は共通です)
  - **インベントリ版**(既定): 構築対象を `inventories/lab/<playbook名>.yml` に**1台1ホスト**で書き、
    `--limit` で個別に、指定なしで全台まとめて実行します。
    変数はインベントリの値が既定値で、`-e` で渡した値が常に優先されます(差分方式)
  - **手動指定版**(`-e "manual=true"`): インベントリも `--limit` も使わず、
    **すべて `-e` で指定**して1台だけ構築します
- 変数の検証は呼び出す各playbookが持っているものをそのまま使うため、
  このディレクトリでは重複した検証を行いません

## Playbook一覧
各playbookの詳しい使い方は同じディレクトリの同名ファイルを参照してください。
実行はリポジトリ直下から `ansible-playbook playbooks/services/<playbook名>.yml` で行います。

| Playbook | 内容 |
| --- | --- |
| [development.yml](development.md) | 開発専用VMを構築する(テンプレート構築 → VM作成 → ハードウェア調整 → 動作設定 → cloud-init設定 → 起動 → VM内セットアップ) |
| [authentik.yml](authentik.md) | Authentik(SSO/IdP)のVMを構築する(上と同じ流れ + VM内でDocker ComposeによるAuthentik構築) |
| [kubernetes.yml](kubernetes.md) | Kubernetes(k3s)のクラスタを構築する(上と同じ流れ + VM内でk3s導入とクラスタへの参加) |
| [technitium-dns.yml](technitium-dns.md) | DNSサーバー(Technitium)のVMを構築する(上と同じ流れ + VM内でDocker ComposeによるDNSサーバー構築) |
| [cloudflare-ddns-ui.yml](cloudflare-ddns-ui.md) | DDNS更新(cloudflare-ddns-ui)のVMを構築する(上と同じ流れ + VM内でDocker ComposeによるDDNS更新サービス構築) |
| [wg-easy.yml](wg-easy.md) | VPN(wg-easy)のVMを構築する(上と同じ流れ + VM内でDocker ComposeによるWireGuard構築) |
| [supabase.yml](supabase.md) | Supabase(セルフホスト)のVMを構築する(上と同じ流れ + VM内でDocker ComposeによるSupabase構築) |
| [proxmox-backup-server.yml](proxmox-backup-server.md) | Proxmox Backup Server(PBS)のVMを構築する(上と同じ流れ + VM内でAPTパッケージによるPBS構築。Dockerは不使用) |

いずれも構築の流れは同じで、最後に呼ぶ `playbooks/vms/` のplaybookだけが違います。
`kubernetes.yml` だけは、最後のVM内セットアップを
**コントロールプレーン → ワーカーの順に1台ずつ**実行します
(ワーカーが参加先からトークンを取得するため)。

## インベントリ
インベントリは環境ごとのディレクトリ(既定は `inventories/lab/`)に置き、
**playbookごとにファイルを分けています**(グループ名 = playbook名)。
他のplaybookを追加するときは `inventories/lab/<playbook名>.yml` を同じ形式で作ってください
(`ansible.cfg` でディレクトリ指定しているので、置くだけで読み込まれます)。

```
inventories/
  lab/                     # 既定の環境(ansible.cfg の inventory)
    development.yml        # playbooks/services/development.yml 用(グループ: development)
    authentik.yml          # playbooks/services/authentik.yml 用(グループ: authentik)
    kubernetes.yml         # playbooks/services/kubernetes.yml 用(グループ: kubernetes)
    technitium-dns.yml     # playbooks/services/technitium-dns.yml 用(グループ: technitium_dns)
    cloudflare-ddns-ui.yml # playbooks/services/cloudflare-ddns-ui.yml 用(グループ: cloudflare_ddns_ui)
    wg-easy.yml            # playbooks/services/wg-easy.yml 用(グループ: wg_easy)
    supabase.yml           # playbooks/services/supabase.yml 用(グループ: supabase)
    proxmox-backup-server.yml # playbooks/services/proxmox-backup-server.yml 用(グループ: proxmox_backup_server)
```

- 環境を増やす場合は `inventories/<環境名>/` を作り、`-i inventories/<環境名>` で切り替えます
  (例: `inventories/production/`。ファイル形式は `lab/` と同じ)
- ⚠ **グループ名にハイフンは使えません**(Ansibleが警告を出します)。
  playbook名にハイフンが入る場合だけ、グループ名はアンダースコアにしてください
  (`technitium-dns.yml` → グループ `technitium_dns`)

- ホスト名は**構築するVMのIPアドレス**です。VMごとの値(VMID・VM名・構築先ノード)は
  `hosts:` 配下に、共通の値は `vars:` に書きます
- パスワードは平文で置かないでください(`-e` で渡すか `ansible-vault encrypt_string` を使用)

### ディスクがSSDかHDDかを明記する
各インベントリの `vm_hardware` には、ディスクの **SSDエミュレーション(`ssd`)**・
**IOスレッド(`iothread`)**・**discard(TRIM/UNMAP)** を明記しています。
いずれも既定はオンで、SCSIコントローラは既定で `virtio-scsi-single` になります。

```yaml
      disk_options:          # 既存ディスク(テンプレートからクローンしたOS用)の設定
        - bus: scsi
          index: 0
          ssd: 1             # HDD上のディスクなら 0
          iothread: 1
          discard: "on"      # YAMLでは on が真偽値になるため引用符が必要
```

**載っているストレージがHDDの場合は `ssd: 0` に変えてください**(ゲストのI/O
スケジューラの判断が変わります)。新規に追加するディスクは `disks` の項目に直接書きます
(実例: `proxmox-backup-server.yml` のバックアップ用ディスクは HDD 上のため `ssd: 0`)。
詳細は [proxmox_vm_hardware.md](../proxmox/proxmox_vm_hardware.md) を参照してください。

## 新しいサービスを追加するとき
1. `roles/` にサービスのロールを、`playbooks/vms/` にVM内セットアップのplaybookを作る
   (既存ロールの `main.yml` の構成に合わせ、共通処理は `common` / `docker` ロールを
   `import_role` する)
2. `playbooks/services/` に既存のplaybook(例: `technitium-dns.yml`)をコピーし、次の箇所だけ変える
   - `hosts:` と `pv_group`(インベントリのグループ名。2箇所)
   - `pv_service_summary` / `pv_resize_hint_reason` / `pv_resize_example`(構築内容の表示用)
   - 最後の `import_playbook`(`playbooks/vms/` の対応するplaybook)
   - サービス固有の検証やvaultがあれば「構築対象を確認する」プレイに足す
     (`cloudflare-ddns-ui.yml` / `wg-easy.yml` が実例)
3. `inventories/lab/<playbook名>.yml` を上と同じ形式で作る
