# playbooks/vm

VM の中を SSH で設定する。VM の作成は [playbooks/pve](../pve/README.md)。設計は [docs/design/k3s.md](../../docs/design/k3s.md)。

**実機の VM を変更する。** 実行は、実行を頼まれたときだけ行う([AGENTS.md](../../AGENTS.md) の安全規則)。

## playbook

| playbook | 内容 | 実行例 |
| --- | --- | --- |
| `k3s.yml` | グループ `k3s` の VM に、OS の共通設定([vm](../../roles/vm/README.md))と k3s の構築([vm_k3s](../../roles/vm_k3s/README.md))をする | `ansible-playbook playbooks/vm/k3s.yml [-l k3s01] 2>&1 \| cat` |

## 前提

- `playbooks/pve/provision.yml` で VM が作られ、起動している。
- 開発マシンから VM へ、SSH(22)で届く(VLAN をまたぐ経路がルータで通っている)。
- `vault/ssh.yml` に秘密鍵があり、対の公開鍵が `inventory/group_vars/all/ssh.yml` にある([vault/README.md](../../vault/README.md))。

## SSH 鍵の扱い

秘密鍵は、開発マシンの `~/.ssh` ではなく vault から取り出す。実行の間だけ `/dev/shm` に 0600 で書き出し、終わると消す。消せなかった場合は、次の実行の初めに消す。

## 確かめる

```sh
ansible-playbook --syntax-check playbooks/vm/k3s.yml
```

実行後の確認(ノードの Ready、API の VIP の応答)は、`vm_k3s` の `verify` が行う。

## 注意

- `playbooks/vm/` の playbook を同時に複数実行しない(実行の初めに、ほかの実行の秘密鍵まで消すため)。
- `vm_k3s` は、k3s のノードが1台のときだけ動く。ノードの追加(参加の手順、クラスタのトークンの置き場)は、設計してから実装する。
