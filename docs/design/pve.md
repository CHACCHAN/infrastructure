# Proxmox 設計

ホストの設定(`pve`)、VMの作成(`pve_vm`)、テンプレート(`pve_template`)の設計。ネットワークは [network.md](network.md)、ノードの構成は [hardware.md](hardware.md)。

## 決定済み

### ホストと API

- Proxmox VE 9 系。1台目は pve01(`172.20.20.1`、VLAN20 の ID 1)。API は `https://172.20.20.1:8006`。
- API のトークンは `vault/proxmox.yml`(`vault_proxmox_token_id`・`vault_proxmox_token_secret`)に置く。
- 証明書は自己署名。

### ネットワーク

- NIC の割り当て・VLAN サブインターフェース・VLAN ごとの `vmbr`・USB LAN の扱い・corosync の2リンクは [network.md](network.md) に従う。
- HA は使わない。

### ストレージ

- LVM-thin を使う。シンプールの使用率を監視する([hardware.md](hardware.md))。
- SYS 以外の SSD(pve01 の ssd01〜03、pve04 の ssd01)は、すべてVM用のストレージにする。
- pve02・pve03 は、SYS の1本の local-lvm に、Proxmox の OS と VM(k3s)を載せる。
- pve01 は、SSD ごとに別のストレージ(`ssd01`、`ssd02`)にする。k3s01 の仮想ディスクは `ssd01`、開発VM は `ssd02` に置く。

### VM の層

VM は層に分けて作る。Ansible が持つのは、器(テンプレート)と、値を渡す仕組みだけ。値はインベントリに宣言する。

| 層 | 内容 | 担当 |
| --- | --- | --- |
| 第1層 | Proxmox の VM のデバイス設定(CPU・メモリ・ディスク・NIC・BIOS など) | `pve_vm` |
| 第2層 | OS と cloud-init(OS のイメージ、ユーザー、SSH 公開鍵、IP) | `pve_template`(OS の器)、`pve_vm`(cloud-init へ値を渡す) |
| 第3層以降 | VM の中(パッケージ、サービスなど) | `vm`、`vm_<サービス>` |

- テンプレートは OS の器だけを持ち、個体の値は持たない。個体の値は、クローンするときに渡す。
- 値は、変数の層([conventions.md](../conventions.md))で決まる。ホストは `vlan`・`id`・`node` と、既定値との差分だけを書く。

### VM テンプレート

- Debian 13 の cloud-init イメージのうち、仮想化向けの `genericcloud` を使う。IP・ユーザー・SSH 公開鍵は cloud-init で渡す。
- テンプレートの VMID は `9<OSの番号><ノードの番号>`(例: pve01 の Debian 13 は `90001`)、名前は `<OS>-template-<ノード名>`(例: `debian13-template-pve01`)。
- qemu-guest-agent は、`vm` ロールが SSH で入れる。入れ終えるまで、VM の `agent` は有効にしない(エージェントのないゲストでは、停止や再起動が待ち時間で失敗するため)。入れたあとに、インベントリで `pve_vm_agent` を有効にする。

### 開発VM

- 開発VM(VLAN22 の ID 1、VMID `2201`)は、Ansible で、起動前までの存在(VM の定義とインストール用 ISO の接続)を管理する。
- OS は Ubuntu Desktop 26.04 LTS。ISO から手動で入れる。cloud-init は使わず、OS の中身は Ansible で管理しない。

## 推奨(未確定)

- テンプレートは、ノードごとに1つ作る。ストレージがノードローカルで、別ノードへクローンできないため。
- 旧構成の、インベントリ外のVMを `-e` で扱う「直接実行」、AWX の Survey 向けの仕組み、cloud-init のパスワードの書き込みは引き継がない。インベントリを唯一の宣言元にする。
- 電源の停止と削除は、確認用の変数を必須にする。
- ISO から入れるVM(開発VM)は、第2層を持たない。クローンではなく、空のVMを作ってISOを接続する。電源は操作しない。
- VM の設定は「全項目を持つ基底(`roles/pve_vm/defaults/main.yml`)+ 差分の上書き」にする(暫定。実際に使って見直す)。
  - 基底は、`community.proxmox.proxmox_kvm` が受け取る VM の設定項目をすべて並べる。使わない項目は `null`(API へ送らず、現在値とも比べない)。何を指定できるかは、この一覧と `ansible-doc -t role pve_vm` で分かる。
  - 変数は項目ごとの平らな名前 `pve_vm_<オプション名>`(NIC だけ `pve_vm_nets`)。辞書にまとめると、グループやホストで1項目書いただけで辞書全体が置き換わるため。
  - 現在値との比較は、項目の型で決める(`roles/pve_vm/vars/main.yml`)。NIC・起動ディスクの拡張・cloud-init の公開鍵と IP・電源は専用のタスク。
  - `pve_vm_` で始まる未知の変数と、対応しない項目(ストレージを確保するデバイスなど)は、エラーにする。
  - 項目を増やすと、API トークンに必要な権限(`VM.Config.CPU`・`Memory`・`Network`・`Disk`・`Options` など)も増える。
- VM の既定値は、CPU を `x86-64-v2-AES`(AVX2 のない pve02・pve03 でも同じ設定で動かすため)、マシン型 `q35`、BIOS `seabios`、メモリのバルーニングなし、ノード起動時に自動起動にする。VGA は、テンプレートの設定(シリアルコンソール)を引き継ぐ。ISO から入れるVM は、個別に上書きする。
- ロールの分担:
  - `pve`: ホスト自体(リポジトリ、ネットワーク、ストレージ、クラスタ)。SSH で設定する。
  - `pve_vm`: VM の作成・更新・削除。API で操作する。
  - `pve_template`: OS テンプレートの作成。
- ブリッジの名前は、NIC1 側を `vmbr0<VLAN番号>`、NIC2 側を `vmbr2<VLAN番号>` にする(例: `vmbr021`)。VMを別のノードで動かしても設定が通るよう、全ノードで同じ名前にする。ホストの管理IPは `vmbr020` に置く。
- ネットワークの変更は、1ノードずつ、コンソールで入れる状態を確認してから適用する。適用前に `--check --diff` で差分を見る。
- クラスタの形成は、2台目のノードを入れるときに行う。それまでは単体ノードとして設定する。
- VMのディスクは `discard` を有効にし、VM内で `fstrim` を定期実行する。削除した領域をシンプールへ返し、使用率が実態から離れないようにするため。
- API の証明書の検証は、変数(`pve_validate_certs`)で切り替える。既定は有効にする。このクラスタは自己署名のため、`inventory/group_vars/all/pve.yml` で無効にし、証明書を整えたら外す。

## 未決

- pve04 のストレージの構成と、`ssd03` が増えたあとの pve01 での置き場所。
- Proxmox の APT リポジトリ(no-subscription を使うか)。
- API トークンの権限の範囲(権限の分離、ロールの割り当て)。
- VM に渡す DNS サーバー([network.md](network.md) の名前解決の設計に依存する)。
- クラスタ形成後の API の接続先(どのノードへ接続するか)。
- 既存の開発VM(2201)を Ansible の管理下に入れる方法(現在の設定をそのまま定義に写し、再実行で変更が出ないようにする)。
- 開発VM は Ansible の実行元でもある。開発VM を作り直すときの、実行元の手当て。
- ホストのNTP・タイムゾーン・通知(メール)の設定。
