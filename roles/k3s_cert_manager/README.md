# k3s_cert_manager

cert-manager を Helm で入れ、Let's Encrypt(Cloudflare の DNS-01)でワイルドカード証明書を自動取得する。証明書は Traefik の既定の証明書(`TLSStore`)にする。設計は [docs/design/k3s.md](../../docs/design/k3s.md)(「クラスタ内アプリの構成」)。

## 使い方

`playbooks/k3s/cert_manager.yml` から使う([playbooks/k3s/README.md](../../playbooks/k3s/README.md))。変数の一覧は `ansible-doc -t role k3s_cert_manager` と `defaults/main.yml`。

前提:

- `vault/cloudflare.yml` に `vault_cloudflare_api_token`(対象ゾーンの DNS 編集だけを許可したトークン)を置く。
- インベントリで `cert_manager_acme_email`(ACME の連絡先)を宣言する。
- ドメインは `lab_domain`(`inventory/group_vars/all/domain.yml`)。

## 処理の流れ

[k3s](../k3s/README.md) ロールに、チャートと Cloudflare のトークンの Secret、発行者(`letsencrypt-staging`・`letsencrypt-production`)、ワイルドカードの `Certificate`、`TLSStore` を渡して適用する。

発行者は、初期値の `letsencrypt-staging` で動作を確認する。`Certificate` が Ready になったら、`cert_manager_issuer: letsencrypt-production` にして再実行する。staging の証明書はブラウザに信頼されない。

`crds.enabled` で CRD をチャートの管理下に置くため、チャートのバージョンを上げると CRD も更新される。
