# vm_hermes

未設定の [Hermes Agent](https://hermes-agent.nousresearch.com/) を、`vm` と `vm_docker` で整えた Debian 13 の VM に入れる。設計は [docs/design/hermes.md](../../docs/design/hermes.md)。

## 使い方

`playbooks/vm/hermes.yml` から使う([playbooks/vm/README.md](../../playbooks/vm/README.md))。必須の変数は無い。変数の一覧は `ansible-doc -t role vm_hermes` と `defaults/main.yml`。

このロールが用意するのは、Hermes が入った状態まで。モデル、チャネル、常駐、管理画面は設定しない。導入のあと、Hermes のユーザーでログインして設定する。

```sh
ssh hermes@<VM の IP>
hermes setup
```

`hermes` で入れるのは、`hermes_ssh_pubkeys`(`inventory/group_vars/hermes.yml`)に載せた公開鍵だけ。sudo を持つ `debian` の鍵(`pve_vm_ssh_pubkeys`)とは別のリストにし、`hermes` に入れる人やエージェントが `debian` に入れないようにする。

## 構成されるもの

- Hermes を動かすユーザー(`hermes_user`)。sudo は持たない。`docker` グループに入る(`hermes_groups`)。
- ユーザーの常駐(linger)。ログアウトしたあとも、ユーザー単位の systemd が動き続ける。
- Hermes Agent の本体。公式のインストーラが、ユーザーのホーム(`~/.hermes/`、コマンドは `~/.local/bin/hermes`)に入れる。

## 処理の流れ

1. `packages.yml`: インストーラが前提にするパッケージを入れる。
2. `user.yml`: ユーザーを作り、SSH の公開鍵を登録し、linger を有効にする。
3. `install.yml`: Hermes がまだ入っていなければ、インストーラを取得して Hermes のユーザーで実行する。
4. `verify.yml`: この実行で入れたときは `hermes --version` が動くことを、毎回、Hermes のユーザーで Docker のデーモンに届くことを確かめる(コンテナの起動までは試さない)。

## 注意

- 導入は、インストーラの完了の印(`~/.hermes/hermes-agent/.hermes-bootstrap-complete`)が無いときだけ行う。入る版は、その時点の最新。導入済みの Hermes の版と設定には触らない。
- ユーザーのホームの中は、Hermes のもの。このロールは、導入と公開鍵の登録のほかには触らない。
- Hermes の本体(インストーラや新しい版)が OS のパッケージを要求したら、`hermes_packages` に足して playbook を流す(sudo を持たないため。VM を作り直しても入るようにする)。ブラウザなどの道具が使うパッケージは足さない。道具は、Hermes がコンテナで動かす。
- インストーラは、実行のたびに公式の URL から取得する。チェックサムは照合しない(版を固定しないため)。
- インストーラの実行には時間がかかる(Python・Node.js と依存一式を取得する)。
