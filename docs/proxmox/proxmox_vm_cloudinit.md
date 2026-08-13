# proxmox_vm_cloudinit.yml
既存VMのcloud-init設定(ログインユーザー・パスワード・SSH公開鍵・IPアドレス)を変更します。

- 指定した項目だけを変更し、未指定の項目には手を触れません
- `proxmox_vm_hardware.yml` と違い、**VMの電源はオンのままでも実行できます**
  (ゲスト内で有効になるのはcloud-initが再実行される次回起動時です)
- 対象VMにcloud-initドライブが接続されていない場合は、設定が反映されないため
  変更前にエラーで終了します

```sh
ansible-playbook playbooks/proxmox/proxmox_vm_cloudinit.yml --ask-vault-pass -vv \
-e "proxmox_ip=<ProxmoxホストのIPアドレス> vm_id=<対象VMのVMID> \
    ssh_user=<ユーザ名> ssh_password=<パスワード> ssh_pubkey='<公開鍵>' \
    ipv4=<IPv4アドレス/CIDR> ipv4_gw=<IPv4アドレス> \
    ipv6=<IPv6アドレス/CIDR> ipv6_gw=<IPv6アドレス>"
```

- SSHユーザは既定で `root`。変更する場合は `-e "proxmox_ssh_user=<ユーザ名>"` を追加します

## 指定できる項目
`vm_id` 以外はすべて任意ですが、**1つ以上の指定が必要**です。

| 変数 | qmのオプション | 内容 |
| --- | --- | --- |
| `ssh_user` | `--ciuser` | cloud-initが作成するログインユーザー名 |
| `ssh_password` | `--cipassword` | そのユーザーのログインパスワード |
| `ssh_pubkey` | `--sshkey` | 登録するSSH公開鍵 |
| `ipv4` / `ipv4_gw` | `--ipconfig0` | 1枚目のNIC(net0)のIPv4アドレス(CIDR形式)とゲートウェイ |
| `ipv6` / `ipv6_gw` | `--ipconfig0` | 1枚目のNIC(net0)のIPv6アドレス(CIDR形式)とゲートウェイ |
| `net1_ipv4` / `net1_ipv4_gw` | `--ipconfig1` | 2枚目のNIC(net1)のIPv4アドレスとゲートウェイ |
| `net1_ipv6` / `net1_ipv6_gw` | `--ipconfig1` | 2枚目のNIC(net1)のIPv6アドレスとゲートウェイ |
| `nameserver` | `--nameserver` | DNSサーバー(複数はスペース区切り) |
| `searchdomain` | `--searchdomain` | 検索ドメイン |

- `nameserver` / `searchdomain` を指定しない場合、ProxmoxはホストのDNS設定をVMへ引き継ぎます。
  ホストのDNSがVMから見えないネットワークでは、VM内で名前解決ができず
  `apt` などが失敗するため明示してください

- `ipv4` / `ipv6` はプレフィックス長込みのCIDR形式で指定します(例: `192.168.10.50/24`、`2001:db8::50/64`)
- `ipv4_gw` / `ipv6_gw` はそれぞれ `ipv4` / `ipv6` と併せて指定してください
  (ゲートウェイのみの指定はエラーになります)
- `ipconfig0` / `ipconfig1` は指定した値でまとめて上書きされます。IPv4とIPv6の両方を
  使っている場合は、変更しない側も併せて指定してください

## NICが2枚あるVM(net1_*)
`net1_*` は2枚目のNIC用で、外部通信とクラスタ内部通信を別のブリッジに分けたい場合に使います。
**NIC自体は [proxmox_vm_hardware.yml](proxmox_vm_hardware.md) の `network` で先に追加**してください
(このplaybookはIPを設定するだけで、NICは足しません)。

```sh
# net1(占有ネットワーク)にIPだけを付ける。ゲートウェイは指定しない
ansible-playbook playbooks/proxmox/proxmox_vm_cloudinit.yml --ask-vault-pass -vv \
-e "proxmox_ip=192.168.10.11 vm_id=101 net1_ipv4=10.10.10.21/24"
```

- **`net1_ipv4_gw` は通常指定しません。** デフォルトゲートウェイが2枚のNICに分かれると、
  通信先によって使うNICが変わり経路が不安定になります。外に出ない占有ネットワークなら
  アドレスだけで足ります(指定した場合は実行時に注意を表示します)
- 3枚目以降(`ipconfig2` 〜)には対応していません。必要な場合はProxmoxホスト上で
  `qm set <vmid> --ipconfig2 ip=...` を直接実行してください

## ssh_password について
`ssh_password` は**VM内のログインパスワード**(cloud-initの `cipassword`)で、
Proxmoxホストへの接続に使う `vault_proxmox_ssh_password` とは別物です。

- 値がログに残らないよう該当タスクの出力を抑止するため(`no_log`)、失敗しても詳細が出ません。
  切り分けが必要なときは `ssh_password` を外して実行してください
- `-e` に直接書くとシェルの履歴に残ります。vaultに入れるか
  `--extra-vars "@<ファイル>"` で渡してください

## 使用例
```sh
# パスワードだけを変更する
ansible-playbook playbooks/proxmox/proxmox_vm_cloudinit.yml --ask-vault-pass -vv \
-e "proxmox_ip=192.168.10.11 vm_id=101 ssh_password=<新しいパスワード>"

# IPアドレスを固定に変更する
ansible-playbook playbooks/proxmox/proxmox_vm_cloudinit.yml --ask-vault-pass -vv \
-e "proxmox_ip=192.168.10.11 vm_id=101 ipv4=192.168.10.50/24 ipv4_gw=192.168.10.1"
```

## 変更の反映について
`qm set` はVM設定に即座に反映されますが、ゲスト内で有効になるのは
cloud-initが再実行される**次回起動時**です。稼働中のVMは
[proxmox_vm_powerctl.yml](proxmox_vm_powerctl.md) などで再起動してください
(playbook実行時にも現在の電源状態に応じた案内を表示します)。

なお、cloud-initはユーザーやSSH鍵の設定を初回起動時のみ行う設定が既定のため、
既に初期化済みのVMではパスワードやユーザーの変更が反映されないことがあります。
その場合はVM内で直接変更するか、クローンし直してください。
