# vm

VM の OS(Debian 13)の共通設定(第3層の土台)。サービスごとの設定は `vm_<サービス>` が担う。設計は [docs/design/pve.md](../../docs/design/pve.md)。

## 使い方

`playbooks/vm/` の playbook から使う([playbooks/vm/README.md](../../playbooks/vm/README.md))。VM に SSH でき、`sudo` できることが前提。変数の一覧は `ansible-doc -t role vm` と `defaults/main.yml`。

## SSH 鍵

`ssh_key_open.yml` と `ssh_key_close.yml` は、VM へ SSH する playbook が、vault の秘密鍵を実行の間だけ `/dev/shm` に置いて消すために使う(`include_role` の `tasks_from`)。

## 処理の流れ

1. `ready.yml`: cloud-init の完了を待つ。
2. `install.yml`: 共通のパッケージ(`vm_packages`)と qemu-guest-agent を入れ、`fstrim.timer` を有効にする。
3. `zram.yml`: `vm_zram_percent` が 1 以上のとき、ZRAM の swap(zram-tools)を設定し、swap が有効になったことを確かめる。

## ZRAM

既定では使わない(`vm_zram_percent: 0`)。使うグループだけ、`inventory/group_vars/<グループ>.yml` で割合を宣言する。k3s ノードでは使わない([docs/design/k3s.md](../../docs/design/k3s.md))。`0` に戻しても、設定済みの ZRAM は消さない。割合を変えると zramswap を再起動し、使用中の swap をいったんメモリへ戻す(メモリが逼迫している VM では、負荷の低いときに行う)。

## qemu-guest-agent を有効にする手順

このロールは、パッケージを入れるだけで、VM の `agent` は有効にしない。入れ終えたあと、次の順で進める。

1. インベントリで `pve_vm_agent: 1` を宣言する。入れ済みのホストだけに書く(新しく作る VM は、入れる前に有効にしない)。
2. `playbooks/pve/provision.yml` を実行する。デバイスの追加は、VM の再起動まで反映されない旨が通知される。
3. VM を再起動する。

## 注意

`ssh_key_open.yml` は、前回の残りとして `/dev/shm/ansible-ssh-*` をすべて消す。SSH で動く playbook を同時に2つ流さない。
