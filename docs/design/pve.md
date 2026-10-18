# Proxmox 設計

ホストの設定(`pve`)、VMの作成(`pve_vm`)、テンプレート(`pve_template`)の設計。ネットワークは [network.md](network.md)、ノードの構成は [hardware.md](hardware.md)。

## 決定済み

### ホストと API

- Proxmox VE 9 系。ノードは pve01〜pve03(`172.16.10.1`〜`.3`)で、クラスタを組んでいる。
- API は、操作する VM(テンプレート)を置くノード自身へ接続する(`https://<ノードのIP>:8006`)。API のトークンはクラスタで共通のため、どのノードでも通る。1台が止まっても、ほかのノードの VM は操作できる。
- API のトークンは `vault/proxmox.yml`(`vault_proxmox_token_id`・`vault_proxmox_token_secret`)に置く。
- 証明書は自己署名。

### ネットワーク

- NIC の割り当て・VLAN サブインターフェース・VLAN ごとの `vmbr`・corosync の2リンクは [network.md](network.md) に従う。
- HA は使わない。
- ブリッジの名前は、物理 NIC の番号と VLAN 番号から `vmbr<NIC番号><VLAN番号>` にする(例: `nic1` の VLAN12 は `vmbr112`)。NIC の配線はノードごとに違うため([hardware.md](hardware.md))、同じ役割のブリッジでもノードによって名前が違う。
  - ホストの管理IP(VLAN10)は、LAN 側のブリッジ(pve01 は `vmbr010`、pve02・pve03 は `vmbr110`)に置く。
  - VM のブリッジは、配置先のノードの LAN 側の NIC 番号(インベントリの `lan_nic`)から導出する。
  - ノード間で VM を移すと、ブリッジの名前が合わない。移すときは、移した先のノードで NIC の設定を直す(`vmbr010` は、pve01 では LAN、pve02・pve03 ではクラスタ用のネットワークを指す)。

### ストレージ

- VM 用の SSD(`ssd01`〜)は、通常の LVM(thick)にする。VM のディスクは作成時に容量をすべて確保するため、領域が足りなくなって VM のディスクが壊れることはない。`local-lvm` は、Proxmox の標準の LVM-thin のまま使う([hardware.md](hardware.md))。
- SYS 以外の SSD(各ノードの ssd01〜)は、すべてVM用のストレージにする。
- SSD ごとに別のストレージ(`ssd01`〜)にする。k3s の VM と、そのノードのテンプレートは `ssd01` に置く。開発VM は pve01 の `ssd02` に置く。

### VM の層

VM は層に分けて作る。Ansible が持つのは、器(テンプレート)と、値を渡す仕組みだけ。値はインベントリに宣言する。

| 層 | 内容 | 担当 |
| --- | --- | --- |
| 第1層 | Proxmox の VM のデバイス設定(CPU・メモリ・ディスク・NIC・BIOS など) | `pve_vm` |
| 第2層 | OS と cloud-init(OS のイメージ、ユーザー、SSH 公開鍵、IP) | `pve_template`(OS の器)、`pve_vm`(cloud-init へ値を渡す) |
| 第3層以降 | VM の中(パッケージ、サービスなど) | `vm`、`vm_<サービス>` |

- テンプレートは OS の器だけを持ち、個体の値は持たない。個体の値は、クローンするときに渡す。
- 値は、変数の層([conventions.md](../conventions.md))で決まる。ホストは `vlan`・`id`・`node` と、既定値との差分だけを書く。
- VM の CPU の種類の既定は `x86-64-v3`(AVX2 まで)。全ノードが対応していて、移した先のノードでも同じ命令セットで動く。

### VM テンプレート

- Debian 13 の cloud-init イメージのうち、仮想化向けの `genericcloud` を使う。IP・ユーザー・SSH 公開鍵は cloud-init で渡す。
- テンプレートは残す。`provision.yml` が、未作成の VM があるノードにテンプレートが無いときだけ作る。作り直すときは、Proxmox の画面でテンプレートと取り込み用のイメージを削除してから、`provision.yml` を実行する。
- テンプレートの VMID は `9<OSの番号><ノードの番号>`(例: pve01 の Debian 13 は `90001`)、名前は `<OS>-template-<ノード名>`(例: `debian13-template-pve01`)。
- qemu-guest-agent は、`vm` ロールが SSH で入れる。入れ終えるまで、VM の `agent` は有効にしない(エージェントのないゲストでは、停止や再起動が待ち時間で失敗するため)。入れたあとに、インベントリで `pve_vm_agent` を有効にする。

### SSH 鍵

- ラボ専用の ed25519 の鍵ペアを1つ使う。開発マシンの `~/.ssh` には依存しない。
- 秘密鍵は `vault/ssh.yml`(`vault_ssh_private_key`)、公開鍵は `inventory/group_vars/all/ssh.yml`(`pve_vm_ssh_pubkeys`)に置く。公開鍵はリストなので、個人の鍵を足せる。
- `playbooks/vm/` は、実行の間だけ秘密鍵を `/dev/shm` に書き出し、終わると消す。
- VM に入るユーザーは、cloud イメージが作る `debian`(グループ変数 `ansible_user`)。

### 開発VM

- 開発VM(VLAN11 の ID 1、VMID `1101`)は、Ansible で、起動前までの存在(VM の定義とインストール用 ISO の接続)を管理する。
- OS は Ubuntu Desktop 26.04 LTS。ISO から手動で入れる。cloud-init は使わず、OS の中身は Ansible で管理しない。

## 推奨(未確定)

- テンプレートは、ノードごとに作る。ストレージがノードローカルで、別ノードへクローンできないため。
- 旧構成の、インベントリ外のVMを `-e` で扱う「直接実行」、AWX の Survey 向けの仕組み、cloud-init のパスワードの書き込みは引き継がない。インベントリを唯一の宣言元にする。
- 電源の停止と削除は、確認用の変数を必須にする。
- ISO から入れるVM(開発VM)は、第2層を持たない。クローンではなく、空のVMを作ってISOを接続する。電源は操作しない。
- VM の設定は「全項目を持つ基底(`roles/pve_vm/defaults/main.yml`)+ 差分の上書き」にする(暫定。実際に使って見直す)。
  - 基底は、`community.proxmox.proxmox_kvm` が受け取る VM の設定項目をすべて並べる。使わない項目は `null`(API へ送らず、現在値とも比べない)。何を指定できるかは、この一覧と `ansible-doc -t role pve_vm` で分かる。
  - 変数は項目ごとの平らな名前 `pve_vm_<オプション名>`(NIC だけ `pve_vm_nets`)。辞書にまとめると、グループやホストで1項目書いただけで辞書全体が置き換わるため。
  - 現在値との比較は、項目の型で決める(`roles/pve_vm/vars/main.yml`)。NIC・起動ディスクの拡張・cloud-init の公開鍵と IP・電源は専用のタスク。
  - `pve_vm_` で始まる未知の変数と、対応しない項目(ストレージを確保するデバイスなど)は、エラーにする。
  - 項目を増やすと、API トークンに必要な権限(`VM.Config.CPU`・`Memory`・`Network`・`Disk`・`Options` など)も増える。
- VM の既定値は、マシン型 `q35`、BIOS `seabios`、メモリのバルーニングなし、ノード起動時に自動起動にする。VGA は、テンプレートの設定(シリアルコンソール)を引き継ぐ。ISO から入れるVM は、個別に上書きする。
- ロールの分担:
  - `pve`: ホスト自体(リポジトリ、ネットワーク、ストレージ、クラスタ)。SSH で設定する。
  - `pve_vm`: VM の作成・更新・削除。API で操作する。
  - `pve_template`: OS テンプレートの作成。
- ネットワークの変更は、1ノードずつ、コンソールで入れる状態を確認してから適用する。適用前に `--check --diff` で差分を見る。
- VMのディスクは `discard` を有効にし、VM内で `fstrim` を定期実行する。削除した領域を SSD へ知らせ(TRIM)、`local-lvm`(LVM-thin)に置いた VM では、使用率が実態から離れないようにするため。
- API の証明書の検証は、変数(`pve_validate_certs`)で切り替える。既定は有効にする。このクラスタは自己署名のため、`inventory/group_vars/all/pve.yml` で無効にし、証明書を整えたら外す。

## 未決

- k3s・テンプレート(`ssd01`)と開発VM(pve01 の `ssd02`)以外の SSD に置くもの(pve01 の `ssd03`、pve02 の `ssd02`・`ssd03`、pve03 の `ssd02`)。
- Proxmox の APT リポジトリ(no-subscription を使うか)。
- API トークンの権限の範囲(権限の分離、ロールの割り当て)。
- VM に渡す DNS サーバー([network.md](network.md) の名前解決の設計に依存する)。
- 既存の開発VMを Ansible の管理下に入れる方法(現在の設定をそのまま定義に写し、再実行で変更が出ないようにする)。
- 開発VM は Ansible の実行元でもある。開発VM を作り直すときの、実行元の手当て。
- ホストのNTP・タイムゾーン・通知(メール)の設定。
