# pve_vm

VM を、テンプレートから作り、宣言どおりにする。API だけを使い、VM へ SSH しない。設計は [docs/design/pve.md](../../docs/design/pve.md)。担当は第1層(Proxmox の VM のデバイス設定)と、第2層のうち cloud-init へ値を渡す部分。

## 使い方

`playbooks/pve/provision.yml` から使う([playbooks/pve/README.md](../../playbooks/pve/README.md))。先に [pve_template](../pve_template/README.md) でテンプレートを作っておく。

- 必須の変数は `pve_vm_storage`(ディスクを置くストレージ)と `pve_vm_ssh_pubkeys`(cloud-init で登録する公開鍵のリスト)。
- ホストは `vlan`・`id`・`node` と、既定値との差分だけを書く。VMID・IP・ゲートウェイは導出される([inventory/README.md](../../inventory/README.md))。例: `inventory/group_vars/k3s.yml`。
- 停止と削除はしない。`pve_vm_start: false` にすると、起動もしない。

## 変数

変数名は `pve_vm_` に、`community.proxmox.proxmox_kvm` のオプション名を続けた形(NIC だけ `pve_vm_nets`)。使える項目の一覧は `ansible-doc -t role pve_vm` か `defaults/main.yml`。

- `null` は「指定しない」。API へ送らず、現在値とも比べない。
- 宣言した値と現在値が違う項目だけを更新する。
- `pve_vm_` で始まる未知の変数(打ち間違い)と、対応しない項目(ストレージを確保するデバイスなど)は、エラーで止まる。
- 辞書にまとめず、項目ごとの変数にしている。グループやホストで1項目書いただけで、辞書全体が置き換わるのを避けるため。

## NIC

- `pve_vm_nets` の要素は、`bridge`(必須)、`model`、`macaddr`、`tag`、`firewall`、`link_down`、`mtu`、`queues`、`rate`。
- 宣言したキーだけを比べる。宣言にないキーと MAC は、現在値を保つ。
- 起動中の VM で、ブリッジ・VLAN タグ・モデル・MAC・キュー数・MTU・ファイアウォール・リンク切断 が変わる場合は、通信が切れるおそれがあるため止まる。モデルは、宣言したときだけ比べる(新しい NIC は `virtio`)。承知のうえなら `pve_vm_allow_nic_change: true` を渡す。

## 再起動が必要な変更

CPU の種類、メモリ(ホットプラグなし)、マシン型などは、起動中の VM には再起動まで反映されない。保留中の変更は、cloud-init の設定のあと、電源の操作の前にメッセージで知らせる。VM を再起動するまで、実行のたびに知らせ続ける。

## 項目を足す・直すとき

次の3つに、同じ項目を書く。

| ファイル | 内容 |
| --- | --- |
| `defaults/main.yml` | 変数と既定値、説明のコメント |
| `vars/main.yml` | 現在値との比べ方(型、現在値に項目がないときの Proxmox の既定値) |
| `meta/argument_specs.yml` | 型・選択肢・説明 |

比較の処理は `filter_plugins/pve_vm.py`。NIC・起動ディスクの拡張・cloud-init の公開鍵と IP・電源は、専用のタスクで扱う。

## 処理の流れ

`validate`(変数の確認)→ `find`(VMID で検索し、名前とノードが宣言と一致することを確認)→ `clone`(未作成ならクローン)→ `configure`(デバイス設定・NIC)→ `disk`(起動ディスクの拡張)→ `cloudinit`(公開鍵・IP)→ `pending`(再起動が必要な変更の通知)→ `power`(起動)。
