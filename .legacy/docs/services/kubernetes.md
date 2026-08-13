# kubernetes.yml
[k3s](https://k3s.io/)のVMを、テンプレート構築からクラスタへの参加まで**コマンド1回**で
構築します。完了時点で `kubectl get nodes` が通り、ワーカーが参加済みの状態になります。

VM内のセットアップは**Debian 13専用**のため、既定で Debian 13 を構築します。

## 2つの実行方法
対象の決め方だけが違い、それ以降の処理は共通です。

| 実行方法 | 対象 | 台数 |
| --- | --- | --- |
| インベントリ版(既定) | `inventories/lab/kubernetes.yml` のホスト。`--limit` で選択 | 1台〜全台 |
| 手動指定版(`-e "manual=true"`) | `-e` で指定した1台 | 1台 |

```sh
# インベントリ版: クラスタ一式(コントロールプレーン + ワーカー)をまとめて構築
ansible-playbook playbooks/services/kubernetes.yml --ask-vault-pass -vv -e "vm_ssh_password=<パスワード>"

# ワーカーを1台だけ追加する(コントロールプレーンは構築済み)
ansible-playbook playbooks/services/kubernetes.yml --ask-vault-pass -vv \
--limit 192.168.10.72 -e "vm_ssh_password=<パスワード>"

# 手動指定版(コントロールプレーン)
ansible-playbook playbooks/services/kubernetes.yml --ask-vault-pass -vv \
-e 'manual=true vm_node=<ノードIP> proxmox_storage=<ストレージ名> \
    vm_id=<VMID> vm_name=<VM名> vm_ipv4=<IPv4/CIDR> vm_ipv4_gw=<ゲートウェイ> \
    vm_ssh_user=<ユーザ名> vm_ssh_password=<パスワード> \
    vm_ssh_pubkey_file=~/.ssh/<公開鍵> vm_ssh_prikey=~/.ssh/<秘密鍵> \
    kubernetes_node_role=server vm_cluster_ipv4=<占有ネットワークのIPv4/CIDR> \
    vm_hardware={"cpu":{"cores":4,"type":"host"},"memory":{"size":4096},"network":[{"index":0,"model":"virtio","bridge":"vmbr2"},{"index":1,"model":"virtio","bridge":"vmbr3"}],"resize":[{"bus":"scsi","index":0,"size":32}]} \
    vm_options={"agent":1,"onboot":1}'

# 手動指定版(ワーカー)。参加先のIPを足すだけで、トークンは自動取得します
ansible-playbook playbooks/services/kubernetes.yml --ask-vault-pass -vv \
-e 'manual=true ... kubernetes_node_role=agent kubernetes_server_ip=<コントロールプレーンのIP>'
```

- インベントリの `kubernetes` グループが空なら、`manual=true` なしでも手動指定版になります
- ⚠ **手動指定版では `vm_hardware` の既定値がありません。** `resize` を省くとディスクが
  テンプレート素の約3GBのままになり、コンテナイメージが入りません(実行開始時に警告します)

## 構築される順番(重要)
**手順8(VM内のセットアップ)だけは、コントロールプレーン → ワーカーの順に1台ずつ**
実行されます。ワーカーは参加先のコントロールプレーンから参加用トークンを
取得するため、先に相手が出来上がっている必要があるからです
(手順1〜7のProxmox側の操作は全台同時に進みます)。

- インベントリの並び順は関係ありません。`kubernetes_node_role` を見て並べ替えます
- 途中の1台が失敗しても、残りはそのまま進みます。ただし**コントロールプレーンが
  失敗した場合はワーカーもトークンを取得できずに失敗**します
- 既存クラスタにワーカーを足す場合(`--limit` でワーカーだけを指定した場合)は、
  参加先のコントロールプレーンが**起動していてSSHでログインできる**必要があります

## インベントリ
[inventories/lab/kubernetes.yml](../../inventories/lab/kubernetes.yml) に**1台1ホスト**で書きます。
ホスト名はVMのIPアドレスです。

| 優先順位 | 指定方法 |
| --- | --- |
| 高 | `-e "変数名=値"` |
| 中 | インベントリの `hosts:` 配下(VMごと) |
| 低 | インベントリの `vars:`(グループ共通) |

```yaml
kubernetes:
  hosts:
    192.168.10.70:              # コントロールプレーン
      vm_id: 1020
      vm_name: k3s-cp01
      vm_node: 192.168.10.11
      kubernetes_node_role: server
    192.168.10.71:              # ワーカー
      vm_id: 1021
      vm_name: k3s-worker01
      vm_node: 192.168.10.11
      kubernetes_node_role: agent
  vars:
    kubernetes_server_ip: 192.168.10.70   # ワーカーの参加先
```

- `kubernetes_node_role` は**VMごとに**指定します(`server` / `agent`)
- `kubernetes_server_ip` は**グループ共通で構いません**。コントロールプレーン自身にも
  渡りますが、自分を指す値は「クラスタの1台目」として扱われます
- **Kubernetes上のノード名は `vm_name`** です(cloud-initがVM名をホスト名に設定するため)

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
8. [playbooks/vms/kubernetes.yml](../vms/kubernetes.md) —
   k3sの導入とクラスタへの参加、VM再起動、ノードがReadyであることの確認

手順1〜6はProxmoxノードへ、手順7〜8はVM自身へ接続します。
ワーカーの構築時は、**参加先のコントロールプレーンにもSSH接続**します
(トークンの取得とReady確認のため)。

完了後、コントロールプレーンにログインすれば `kubectl` がそのまま使えます。

```sh
ssh -i ~/.ssh/<秘密鍵> <vm_ssh_user>@192.168.10.70 'kubectl get nodes -o wide'
```

## VMごとに指定する変数
インベントリの `hosts:` 配下、または `-e` で指定します。

| 変数 | 内容 |
| --- | --- |
| `vm_id` | 新規VMのVMID |
| `vm_name` | VM名。**そのままKubernetesのノード名になります** |
| `vm_node` | 構築先ProxmoxノードのIPアドレス |
| `vm_ipv4` | nic0(外部通信用)の固定IP(CIDR)。省略時は**ホスト名 + `vm_ipv4_prefix`** から組み立てます |
| `vm_cluster_ipv4` | nic1(クラスタ占有ネットワーク)の固定IP(CIDR)。省略するとクラスタ通信もnic0を使います(後述) |
| `kubernetes_node_role` | `server`(コントロールプレーン)/ `agent`(ワーカー) |

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
| CPU / RAM | 4コア(`host`)/ 4GB | `cpu: {cores: 4, type: host}` `memory: {size: 4096}` |
| BIOS / マシン / 画面 | SeaBIOS / Q35 / 標準VGA | `options: {bios: seabios, machine: q35, vga: std}` |
| NIC | nic0 = `vmbr2` / nic1 = `vmbr3` | `network: [{index: 0, model: virtio, bridge: vmbr2}, {index: 1, model: virtio, bridge: vmbr3}]` |
| ディスク | 32GiB | `resize: [{bus: scsi, index: 0, size: 32}]` |
| QEMUエージェント / 自動起動 | 有効 | `agent: 1` `onboot: 1` |

- ノードごとに変える場合は `hosts:` の各VMの下に `vm_hardware` を書けば上書きできます
- ディスクは **`resize`(既存ディスクの拡張)で指定します**。`disks` に書くと新しい空ディスクに
  置き換わります。また既に指定サイズ以上なら拡張は行われません
- `-e` で `vm_hardware` を渡すとインベントリの値は**置き換え**になるため、
  変更しない項目も併せて指定してください(JSONにはスペースを含めないこと)

## ネットワーク構成(NIC 2枚)
既定では**NICを2枚**持たせ、外部通信とクラスタ内部通信を分けます。

| NIC | ブリッジ | IPアドレス | 用途 |
| --- | --- | --- | --- |
| nic0 | `vmbr2` | ホスト名のIP(または `vm_ipv4`) | 外部通信。SSH・手元からの `kubectl`・イメージの取得 |
| nic1 | `vmbr3` | `vm_cluster_ipv4` | クラスタ間の占有ネットワーク。ノード間通信のみ |

`vm_cluster_ipv4` を書くと、以下がまとめて自動設定されます。

1. cloud-initの `ipconfig1` にそのアドレスが入る(nic1にIPが付く)
2. k3sの `node-ip` がそのIPになる(kubelet・etcd・ノード間アクセスが占有ネットワークへ)
3. k3sの `flannel-iface` が**そのIPを持つNICに自動で揃う**(Pod間通信も占有ネットワークへ)
4. ワーカーの参加先(`server:`)が、**同じ実行に含まれるコントロールプレーンの
   占有ネットワーク側IP**になる

```yaml
kubernetes:
  hosts:
    172.16.12.11:
      vm_cluster_ipv4: 10.10.10.11/24   # nic1に付くIP
      kubernetes_node_role: server
    192.168.10.71:
      vm_cluster_ipv4: 10.10.10.21/24
      kubernetes_node_role: agent
  vars:
    kubernetes_server_ip: 172.16.12.11  # SSH接続先。外部通信用のIPのまま
```

- **`kubernetes_server_ip` は外部通信用のIPのままにしてください。** 占有ネットワークは
  Ansibleの実行元から見えないのが普通で、トークン取得とReady確認のSSHに使うためです。
  APIサーバーへの接続先だけが自動で占有ネットワーク側に切り替わります
- ゲートウェイ(`vm_cluster_ipv4_gw`)は**指定しないでください**。デフォルトゲートウェイが
  2枚のNICに分かれると通信経路が不安定になります
- コントロールプレーンの `tls-san` には外部通信用のIPが**自動で追加**されるため、
  手元からの `kubectl` はそのまま使えます
- 既存クラスタにワーカーだけを足す場合(`--limit` でワーカーのみ)は、参加先が実行対象に
  含まれないため `-e "kubernetes_server_node_ip=<コントロールプレーンの占有ネットワークIP>"`
  を付けてください
- **1枚構成に戻す場合**は `vm_cluster_ipv4` を消し、`vm_hardware` の `network` から
  `index: 1` を外します。クラスタ通信はnic0に戻ります
- `vm_cluster_ipv4` を書いたのに `vm_hardware` にnic1が無い場合は、実行開始時にエラーで
  停止します(テンプレートはnic0の1枚しか持たないため)

## k3sの設定
`kubernetes_` で始まる変数はそのまま手順8へ渡ります。インベントリにも `-e` にも書けます。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `kubernetes_node_role` | **(必須)** | `server` / `agent` |
| `kubernetes_server_ip` | (未設定) | ワーカーの参加先(SSH接続先)。**agentでは必須** |
| `kubernetes_server_node_ip` | (自動判定) | 参加先の占有ネットワーク側IP。既存クラスタに足す場合のみ指定 |
| `kubernetes_node_ip` | `vm_cluster_ipv4` | ノード間通信に使うIP。通常は自動設定に任せます |
| `kubernetes_version` | (最新安定版) | 例: `v1.34.1+k3s1` |
| `kubernetes_disable` | `[]` | 標準コンポーネントの無効化。例: `["traefik"]` |
| `kubernetes_cluster_init` | `false` | 1台目で埋め込みetcdを使う(HA構成にするなら必須) |
| `kubernetes_disable_swap` | `true` | swapを無効化する |

全項目と運用(バージョンアップ・ノードの外し方・HA構成)は
[docs/vms/kubernetes.md](../vms/kubernetes.md) を参照してください。

## `-e` で渡す変数
| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `manual` | インベントリが空なら `true` | 手動指定版として動作します |
| `vm_ssh_password` | (なし) | VMのログインパスワード(Proxmoxのコンソール用。SSHは鍵認証) |
| `proxmox_ssh_user` | `root` | Proxmoxホストへ接続するSSHユーザー |
| `vm_reboot_after_setup` | `true` | VM内セットアップ後に再起動するか |

`proxmox_ssh_user` と `vm_reboot_after_setup` は、対象ホストの変数が参照できない
タイミングで使われるため、インベントリに書いても反映されません。

## 任意の変数
| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `os_type` / `os_version` | `debian` / `13` | VM内のセットアップがDebian 13専用のため固定 |
| `target_storage` | `proxmox_storage` と同じ | VMのディスクを置くストレージ名 |
| `vm_hardware_delete` / `vm_options_delete` | (なし) | 削除するプロパティ |
| `vm_ipv6` / `vm_ipv6_gw` | (なし) | IPv6アドレス(CIDR)とゲートウェイ |
| `vm_cluster_ipv4_gw` | (なし) | 占有ネットワークのゲートウェイ。**通常は指定しません**(経路が不安定になります) |
| `vm_nameserver` / `vm_searchdomain` | (なし) | DNSサーバーと検索ドメイン |
| `vm_ip` | ホスト名 | SSHの接続先(ホスト名と違うIPで繋ぐ場合) |
| `vm_ssh_wait_timeout` | `600` | SSHログインできるまでの待機上限(秒) |
| `kubernetes_server_ssh_user` / `_prikey` | `vm_ssh_user` / `vm_ssh_prikey` | 参加先へSSH接続するユーザー・鍵(ノードごとに鍵を分けている場合) |

## 再実行・復旧
- **同じ `vm_id` での再実行はできません。** 作り直す場合は
  `playbooks/proxmox/proxmox_vm_delete.yml` で削除するか、別の `vm_id` にしてください
- 構築済みVMのk3sだけを更新する場合は `playbooks/vms/kubernetes.yml` を
  直接実行してください(クラスタのデータはそのまま残ります)
- ノードをクラスタから外す手順は
  [docs/vms/kubernetes.md](../vms/kubernetes.md#ノードを外す作り直す) にあります

## 注意
- 手順8は1台ずつ処理されるため、台数が増えるとその分時間がかかります
  (1台あたりOS更新・k3s導入・再起動で数分)
- `--ask-vault-pass` は必須です(`vault/proxmox.yml` を読むため)
- 手動指定版では `--limit` を使わないでください(`hosts: localhost` のプレイが
  対象外になり、構築対象が登録されません)
- VM内の設定は `vm_` 接頭辞で指定します。`ssh_user` や `ipv4` をそのまま `-e` で渡すと
  **テンプレート側にも**焼き込まれてしまうためです
- 他のOSを指定した場合、手順7までは動作しますが手順8でOS判定により停止します
