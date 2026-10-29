# playbooks/k3s

k3s のクラスタ内アプリを、Helm で宣言どおりにする。kubeconfig を使わず、vault のトークンで Kubernetes API の VIP に接続する。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「クラスタ内アプリの管理」)。

**`--check` なしの実行は、実機のクラスタを変更する。** 実行は、実行を頼まれたときだけ行う([AGENTS.md](../../AGENTS.md) の安全規則)。`--check --diff`(helm-diff)は読み取り専用。

## playbook

| playbook | 内容 | 実行例 |
| --- | --- | --- |
| `metallb.yml` | MetalLB(L2)を入れ、Ingress の VIP を LoadBalancer に割り当てる。内蔵の Traefik の配置と、Cloudflare Tunnel 専用の入口も設定する(変えると Traefik が入れ替わり、Ingress が一時的に途切れる) | `ansible-playbook playbooks/k3s/metallb.yml [--check --diff] 2>&1 \| cat` |
| `cert_manager.yml` | cert-manager を入れ、Let's Encrypt(Cloudflare の DNS-01)のワイルドカード証明書を Traefik の既定の証明書にする | `ansible-playbook playbooks/k3s/cert_manager.yml [--check --diff] 2>&1 \| cat` |
| `longhorn.yml` | Longhorn を入れ、既定の StorageClass にする。管理 UI を、Authentik の認証プロキシを通して公開する | `ansible-playbook playbooks/k3s/longhorn.yml [--check --diff] 2>&1 \| cat` |
| `cnpg.yml` | CloudNativePG のオペレーターを入れる。各アプリ専用の PostgreSQL は、そのアプリの playbook が作る([roles/k3s_postgresql](../../roles/k3s_postgresql/README.md)) | `ansible-playbook playbooks/k3s/cnpg.yml [--check --diff] 2>&1 \| cat` |
| `authentik.yml` | Authentik を入れ、アプリの OIDC クライアントと認証プロキシを Blueprint で宣言する | `ansible-playbook playbooks/k3s/authentik.yml [--check --diff] 2>&1 \| cat` |
| `gravitee_am.yml` | Gravitee Access Management と専用の PostgreSQL を入れる([roles/k3s_gravitee_am](../../roles/k3s_gravitee_am/README.md)) | `ansible-playbook playbooks/k3s/gravitee_am.yml [--check --diff] 2>&1 \| cat` |
| `gravitee.yml` | Gravitee API Management と専用の PostgreSQL を入れる([roles/k3s_gravitee](../../roles/k3s_gravitee/README.md)) | `ansible-playbook playbooks/k3s/gravitee.yml [--check --diff] 2>&1 \| cat` |
| `openwebui.yml` | OpenWebUI を入れる | `ansible-playbook playbooks/k3s/openwebui.yml [--check --diff] 2>&1 \| cat` |
| `nextcloud.yml` | Nextcloud Hub と専用の PostgreSQL を入れる([roles/k3s_nextcloud](../../roles/k3s_nextcloud/README.md)) | `ansible-playbook playbooks/k3s/nextcloud.yml [--check --diff] 2>&1 \| cat` |
| `litellm.yml` | LiteLLM Proxy を入れる | `ansible-playbook playbooks/k3s/litellm.yml [--check --diff] 2>&1 \| cat` |
| `cliproxy.yml` | CLIProxyAPI を置き、管理画面を Authentik の認証プロキシを通して公開する | `ansible-playbook playbooks/k3s/cliproxy.yml [--check --diff] 2>&1 \| cat` |
| `lan_proxy.yml` | クラスタの外にある LAN 内のサービス(Proxmox の管理 UI など)を、Traefik でリバースプロキシする | `ansible-playbook playbooks/k3s/lan_proxy.yml [--check --diff] 2>&1 \| cat` |
| `cloudflared.yml` | cloudflared(Cloudflare Tunnel のコネクタ)を入れる | `ansible-playbook playbooks/k3s/cloudflared.yml [--check --diff] 2>&1 \| cat` |

## 実行の順序

`metallb.yml` → `cert_manager.yml` → `longhorn.yml` → `cnpg.yml` → `authentik.yml` の順に実行する。そのあとの `openwebui.yml`・`litellm.yml`・`cliproxy.yml`・`nextcloud.yml` は、順不同。Gravitee は `authentik.yml` で AM 用の OIDC クライアントと認証プロキシを用意してから、`gravitee_am.yml` → [AM の画面での手動設定](../../roles/k3s_gravitee_am/README.md) → `gravitee.yml` の順に実行する。それ以外の OIDC アプリは client_secret が vault で決まっているため、`authentik.yml` より先に入れてもよい(ログインできるのは Authentik の起動後)。`cloudflared.yml` は、Tunnel を Cloudflare の画面で作ってから実行する([roles/k3s_cloudflared](../../roles/k3s_cloudflared/README.md))。公開するホスト名(`cloudflared_hosts`)を変えたときは、そのアプリの playbook を実行し、Cloudflare の画面の経路も合わせる。Gravitee は `gravitee.<lab_domain>` だけを登録する。`lan_proxy.yml` は、`metallb.yml` と `cert_manager.yml` のあとなら、いつ実行してもよい。アプリを足して `k3s_ingress_hosts`(クラスタ内から公開ホスト名を Traefik へ向ける CoreDNS の設定)を変えたときは、`playbooks/vm/k3s.yml` も流す。Longhorn の管理 UI、CLIProxyAPI の管理画面と APIM のコンソールは、`authentik.yml` を実行するまで開けない(認証プロキシのミドルウェアが無いため)。Longhorn は、ノード側の前提(`vm_k3s` の `storage`)が先に要るので、`playbooks/vm/k3s.yml` を流してから実行する。

## 前提

- k3s が動いている([playbooks/vm](../vm/README.md))。
- `vault/k3s.yml` にトークンと認証局の証明書がある。無ければ、先に [playbooks/utils](../utils/README.md) の `k3s_token.yml` を実行する。
- アプリごとの前提は、各ロールの README に書く。
- 開発マシンから API の VIP(`172.16.<vlan>.<k3s_api_vip_id>`、6443)に届く。

## アプリを足す

`new-role` スキルに従い、`k3s_<app>` ロールを作る。ロールは [k3s](../../roles/k3s/README.md) を `include_role` で呼ぶだけにし、チャートとバージョンを `defaults/main.yml` に、values の基本値を `vars/main.yml` に書く。playbook は `metallb.yml` と同じ形にする。
