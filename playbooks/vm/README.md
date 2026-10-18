# playbooks/vm

VM の中を SSH で設定する。VM の作成は [playbooks/pve](../pve/README.md)。設計は [docs/design/k3s.md](../../docs/design/k3s.md) と [docs/design/hermes.md](../../docs/design/hermes.md)。

**実機の VM を変更する。** 実行は、実行を頼まれたときだけ行う([AGENTS.md](../../AGENTS.md) の安全規則)。

## playbook

| playbook | 内容 | 実行例 |
| --- | --- | --- |
| `k3s.yml` | グループ `k3s` の VM に、OS の共通設定([vm](../../roles/vm/README.md))と k3s の構築([vm_k3s](../../roles/vm_k3s/README.md))をする | `ansible-playbook playbooks/vm/k3s.yml [-l k3s01] 2>&1 \| cat` |
| `hermes.yml` | グループ `hermes` の VM に、OS の共通設定、Docker([vm_docker](../../roles/vm_docker/README.md))、未設定の Hermes Agent([vm_hermes](../../roles/vm_hermes/README.md))を入れる | `ansible-playbook playbooks/vm/hermes.yml [-l <ホスト名>] 2>&1 \| cat` |

## 前提

- `playbooks/pve/provision.yml` で VM が作られ、起動している。
- 開発マシンから VM へ、SSH(22)で届く(VLAN をまたぐ経路がルータで通っている)。
- `vault/ssh.yml` に秘密鍵があり、対の公開鍵が `inventory/group_vars/all/ssh.yml` にある([vault/README.md](../../vault/README.md))。

## SSH 鍵の扱い

秘密鍵は、開発マシンの `~/.ssh` ではなく vault から取り出す。実行の間だけ `/dev/shm` に 0600 で書き出し、終わると消す。消せなかった場合は、次の実行の初めに消す。

## 確かめる

```sh
ansible-playbook --syntax-check playbooks/vm/k3s.yml
ansible-playbook --syntax-check playbooks/vm/hermes.yml
```

実行後の確認は、各ロールの `verify` が行う(`vm_k3s`: ノードの Ready、API の VIP の応答。`vm_hermes`: 入れた `hermes` コマンドと、そのユーザーで Docker のデーモンに届くこと)。

## 注意

- `playbooks/vm/` の playbook を同時に複数実行しない(実行の初めに、ほかの実行の秘密鍵まで消すため)。
- `hermes.yml` の対象は、グループ `hermes` のホスト(`inventory/hosts/13_hermes.yml`)。
- `k3s.yml` は、1台ずつ(グループの先頭から)実行する。先に `playbooks/utils/k3s_cluster_token.yml` で、クラスタのトークンを `vault/k3s.yml` に入れておく([vm_k3s](../../roles/vm_k3s/README.md))。
