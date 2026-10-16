# vm_docker

Docker を、`vm` で整えた Debian 13 の VM に入れる。設計は [docs/design/hermes.md](../../docs/design/hermes.md)。

## 使い方

`playbooks/vm/` の playbook から、`vm` のあとに使う([playbooks/vm/README.md](../../playbooks/vm/README.md))。必須の変数は無い。変数の一覧は `ansible-doc -t role vm_docker` と `defaults/main.yml`。

Docker を使うユーザーは、このロールでは決めない。使う側のロール(`vm_hermes` など)が、ユーザーを `docker` グループに入れる。

## 処理の流れ

1. `install.yml`: Debian のパッケージで Docker と `docker compose` を入れ、デーモンを有効にして起動する。
2. `verify.yml`: デーモンに届くことと、`docker compose version` が動くことを確かめる。

## 注意

`docker` グループのユーザーは、その VM の root と同じことができる(ホストのファイルをコンテナにマウントできるため)。グループに入れるのは、VM の中を任せてよいユーザーだけにする。
