# k3s 設計

## 決定済み

### ノード

- 3台とも k3s のサーバーで、ワークロードも動かす。名前は `k3s01`〜`k3s03`、VMID は `2101`〜`2103`、IP は `172.20.21.1`〜`.3`(VLAN21)。
- k3s01 の仮想CPUは4コア、起動ディスクは256GiB(pve01 の `ssd01` に置く)。
- OS は Debian 13 minimal。RAM は12GBで固定し、Proxmox のメモリバルーニングは切る。
- swap は使わない(ZRAM も使わない)。Pod の cgroup は `NoSwap` で swap を使えず、ZRAM が効くのは k3s 本体と OS のデーモンだけで、守りたい Pod に効かないため。メモリの逼迫は、`requests`・`limits` の設計とノードのメモリ量で防ぐ。

### VIP と Ingress

| 用途 | IP | 実装 |
| --- | --- | --- |
| Ingress(HTTP/HTTPS) | `172.20.21.5` | MetalLB(L2) |
| Kubernetes API | `172.20.21.6` | kube-vip |

- k3s の `servicelb` は無効にする。Traefik は k3s 内蔵のものを使う。
- Traefik を全ノードに置き(DaemonSet)、`externalTrafficPolicy: Local` にする。VIPを持つノードに必ず Traefik がいて、クライアントの実IPも保たれる(Authentik が、IP ごとにログインの失敗を数えるのに使う)。
- Traefik は、クラスタ内のサービスだけでなく、LAN内のサービス(Proxmox・TrueNAS・PBS の管理UI)へのリバースプロキシも兼ねる。ホスト名のDNSは `172.20.21.5` を指す。例: `pve01.cc-chacchan.com` → Traefik → `172.20.20.1:8006`。
- 管理UIは Cloudflare Tunnel を経由しない。

### ストレージとバックアップ

- Longhorn を使う。通常のPVCは複製数2にする。
- k3s02・k3s03(pve02・pve03 上)は、仮想ディスクを1本だけ持つ。Longhorn のデータは、OS と同じディスクに置く([hardware.md](hardware.md))。
- k3s ノードは、VMとしてのバックアップを取らない。コード(Ansible・Helm・マニフェスト)から再構築する。
- Longhorn のバックアップ先(NFSのNAS)は未構築。**現時点では、k3s上の永続データにバックアップがない。**

### アプリ

- PostgreSQL は k3s で運用する。CloudNativePG(オペレーターの `cloudnative-pg` と、DB 本体を作る `cluster` の2つのチャート)を使う。インスタンスは1つで、ボリュームは Longhorn(複製数2)に置く。
- 次のアプリを、legacy から引き継いで k3s で動かす: Authentik、PostgreSQL、Homarr、OpenWebUI。LiteLLM Proxy を新しく足す。すべて Helm のチャートで入れる。
- 証明書は cert-manager で自動取得する。
- NAS ができるまで、データ保護の暫定策は設けない(オーナーの判断)。
- リモートアクセスの VPN(WireGuard)と DDNS は、上流のルータ(OPNsense)が担う予定。k3s では動かさない。
- 再現性の範囲:
  - 構成(VM、k3s、Helm のリリース、values、Secret)は、コードから再現する。
  - 設定のコード化は、宣言できるものを宣言する。アプリの OIDC クライアントは、Authentik の Blueprint で宣言する。client_id と client_secret は vault で決め、Authentik と各アプリに同じ値を渡す(Authentik を先に完成させる必要がない)。
  - 状態(ユーザー、パスワード、チャット、ボード、DB の中身)は、Ansible では管理しない。バックアップで守る(現在はバックアップなし)。例外は、各アプリの緊急用の管理者だけ。
- Authentik は k3s で運用する。旧構成からは移さず、新規に構築する。OIDC クライアント、認証プロキシ、ログインの失敗の制限、MFA の必須化、Google でのログインは Blueprint で宣言し、ユーザー・グループ・グループの所属・アプリケーションを使えるグループの結びつけ・それ以外のフローは手動で設定する。
- Rancher、AWX、Nextcloud、Portainer は使わない。k3s の Web UI は置かない(一時的なコンテナは、開発VMの Docker で動かす)。

### k3s の構築

- k3s01 を先に単独で構築する場合([network.md](network.md) の移行)は、最初から次のようにする。
  - 組み込み etcd を有効にして(`cluster-init`)、k3s02・k3s03 を後から参加させられるようにする。
  - API の証明書に `172.20.21.6` を含め(`tls-san`)、接続先は最初から API の VIP にする。
  - Longhorn の複製数は、ノードが1台の間は1にし、2台目が参加したら2に上げる。
- k3s 標準の local-storage(local-path)を無効にし、Longhorn を既定の StorageClass にする。ノード内だけに残る PVC が意図せず作られ、別ノードで復帰できなくなるのを防ぐ。
- k3s は stable チャンネルの 1.36 系(`k3s_version`)を使う。リリースからバイナリを取得してチェックサムを検証し、systemd のユニットは Ansible が置く(インストールスクリプトは使わない)。Longhorn が要求する Kubernetes 1.34 以上を満たす。
- API の VIP を持つ kube-vip は、DaemonSet で動かす(ARP、リーダー選出)。マニフェストは k3s の自動適用ディレクトリ(`/var/lib/rancher/k3s/server/manifests/`)に置く。インターフェースはノードの既定経路のものを使う。

## 推奨(未確定)

- 3台を、別々の Proxmox ノードに置く。

## 決定済み: ノードのネットワーク経路(案A)

k3s ノードのVMは、VLAN21 の1NIC(NIC1側の `vmbr`)だけにつなぐ。NIC2 はホスト専用にする。

### 通信の流れ

```text
LAN クライアント
  → ルータ(VLAN間ルーティング)
  → 172.20.21.5(MetalLB が ARP に応答するノード)
  → Traefik
  → ① クラスタ内サービス: Pod へ(別ノードなら flannel の VXLAN)
  → ② LAN内サービス(Proxmox・TrueNAS・PBS): デフォルトルートからルータへ → 実IP

公開アプリ(Cloudflare Tunnel)
  インターネット → Cloudflare → cloudflared Pod(クラスタから外向きに接続)
  → Traefik の ClusterIP → Pod        (172.20.21.5 を通らない)

kubectl・Ansible
  開発VM(VLAN22) → ルータ → 172.20.21.6:6443(kube-vip のリーダーノード)
```

### NICの扱い

| | 案A: VLAN21 のみ(NIC1) | 案B: VLAN21 + VLAN31(NIC1 + NIC2) |
| --- | --- | --- |
| 設定 | インターフェースが1つで単純 | `node-ip`・flannel のインターフェース・`tls-san`・kube-vip/MetalLB のインターフェースを分けて指定する |
| 帯域 | NIC1(1GbE)を Ingress・Longhorn の複製・リビルドで共有する | ノード間通信を、専用の1GbEへ逃がせる |
| 分離 | k3s の VM は NIC2 に触れない(NIC2 はホスト専用) | k3s の VM が NIC2 側のL2に載る。スイッチがVLAN非対応なので、分離はホストの設定だけ |
| Longhorn のバックアップ(→TrueNAS) | VLAN21 → ルータ → VLAN23 | NIC2 経由で直接 |

案Aは、複雑さと分離の面で有利。pve02・pve03 の NIC2 は USB LAN で、etcd や Longhorn の通信を載せると、リンクが落ちたときにノードがクラスタから外れる。帯域の不足は、実際に計測してから案Bまたは Longhorn の専用ストレージネットワークで補う。

### 確認が要る事項

- ルータ(ER605)が、VIP の切り替え時のGratuitous ARP を受け付け、ARPテーブルを更新するか。実機でフェイルオーバーを試す。
- VLAN をまたぐ通信(Ingress、Traefik から LAN内サービスへのプロキシ、Longhorn のバックアップ)は、ルータを通る。ER605 のルーティング性能とフィルタ設定が、その実効帯域の上限になる。同じ VLAN21 の中のノード間通信(etcd・flannel・Longhorn の複製)は、SWHUB が中継し、ルータを通らない。
- USB LAN のチップ型番([hardware.md](hardware.md))。
- Longhorn のリビルド中の Ingress への影響(同時リビルド数を制限する)。
- ノード停止時に、Longhorn のボリュームを持つ Pod が別ノードで復帰するか、復帰までの時間。Longhorn のノード停止時の Pod 削除ポリシーを設定したうえで、k3s の VM を止めて計測する。

## クラスタ内アプリの管理

クラスタ内アプリ(`k3s` / `k3s_<app>`)を、Helm で管理する方法。

### 決定済み

- アプリは Helm の実リリース(`helm upgrade --install` に相当。`kubernetes.core.helm`)で管理する。MetalLB・Traefik の公開設定・Longhorn など、クラスタに入れるものはすべてこの経路にする。
- チャートのバージョンは、ロールの `defaults/main.yml` にだけ書く([conventions.md](../conventions.md))。
- 秘密情報は vault に置き、playbook がロールへ渡す。
- kubeconfig を使わない。プロジェクトの外に機密情報を置かないため。接続先は API の VIP(`https://172.20.21.6:6443`)。
- 接続は、専用の ServiceAccount のトークンで行う。権限は `cluster-admin`(MetalLB や Longhorn が CRD・ClusterRole・namespace を作るため。使うのはオーナー1人)。
- トークンは、最初の1回だけ、k3s01 上の管理用 kubeconfig(`/etc/rancher/k3s/k3s.yaml`)を SSH 越しに使って ServiceAccount と長期トークンの Secret を作り、`vault/k3s.yml` に格納する。この単発の作業は `playbooks/utils/` に置く。
- `--check --diff` には helm-diff プラグインを使う(Helm 4 では v3.14.0 以上)。開発コンテナに導入する(`.devcontainer/devcontainer.json`)。
- 共通処理は `k3s` ロールに1つだけ置く(チャート・リリース名・namespace・values を受け取って適用する)。このロールの変数は、`vm_k3s` の `k3s_*` と衝突しないよう `helm_*` にする。各 `k3s_<app>` は、`defaults/main.yml` にチャート・バージョンを、`vars/main.yml` に values の基本値を書く。インベントリでは `<app>_values` で、基本値へ再帰的に合成して上書きする(リソースや `TZ` など)。
- values に入れた秘密値は、Helm のリリース情報(namespace 内の Secret)に残る。秘密値を扱うタスクには `no_log` を付ける。

### 未決

- トークンの更新(ローテーション)の手順。
- CRD の扱い。Helm は、チャートの `crds/` ディレクトリにある CRD を upgrade で更新しない。MetalLB・cert-manager(`crds.enabled`)・CloudNativePG・Longhorn は、CRD をテンプレートで持つため upgrade で更新される(チャートのバージョンを上げる前に、新しい CRD の変更点を確認する)。ほかのチャートを足すときは、どちらの方式か確認する。

## クラスタ内アプリの構成

### 決定済み

- 導入の順序: トークン → MetalLB → cert-manager → Longhorn → CloudNativePG(オペレーター、PostgreSQL)→ Authentik → Homarr・OpenWebUI・LiteLLM。Longhorn の管理 UI は、Authentik を入れるまで開けない(認証プロキシのミドルウェアが無いため)。
- namespace はアプリごとに分ける(`cert-manager`、`longhorn-system`、`cnpg-system`、`postgresql`、`authentik` など)。
- 証明書:
  - Let's Encrypt と Cloudflare の DNS-01 を使う。ドメインは `lab_domain`(`cc-chacchan.com`、`inventory/group_vars/all/domain.yml`)。ホスト名がインターネットに出ないよう、ワイルドカード1枚(`*.cc-chacchan.com`)にする。
  - 証明書は `kube-system` に置き、Traefik の既定の証明書(`TLSStore` の `default`)にする。各アプリの Ingress は、証明書を個別に持たない。
  - 先に staging の発行者で動作を確認し、本番の発行者に切り替える(`cert_manager_issuer`)。
  - 自己チェックの DNS は、公開リゾルバ(`1.1.1.1`・`1.0.0.1`)を直接指す。ノードに渡す DNS サーバーが未決で、プライベートIPを返す応答の扱いも未決のため。
  - Cloudflare の API トークンは、対象ゾーンの DNS 編集だけを許可する。`vault/cloudflare.yml` に置く。ACME の連絡先メールアドレスはインベントリに宣言する(`cert_manager_acme_email`)。
- Longhorn: 複製数は、ノードが1台の間は1(CSI・マネージャーの Pod も1)。ノード停止時の Pod 削除ポリシーと、同時リビルド数の制限(1)を設定する。管理 UI は認証を持たないため、Authentik の認証プロキシを通して公開する(`longhorn`)。
- PostgreSQL: メジャーバージョン17、pgvector を含む CloudNativePG の `standard` イメージ。1インスタンス。アプリごとに DB とロールを宣言で作り、パスワードは `vault/postgresql.yml` に置く。スーパーユーザーのアクセスは無効にする。
- 公開ホスト名は `<名前>.<lab_domain>` で、インベントリ(`inventory/group_vars/k3s.yml`)に宣言する(`auth`・`homarr`・`ai`・`litellm`・`longhorn`)。TLS は Traefik で終端し、Ingress は Traefik の既定の証明書を使う。
- アプリの秘密情報は `vault/<アプリ名>.yml` に置く(DB のパスワードは `vault/postgresql.yml`)。
- ログインは、すべてのアプリで Authentik の SSO(OIDC)にする(Homarr・OpenWebUI・LiteLLM)。Ansible が管理するのは、OIDC の接続(Authentik の OIDC クライアントと、各アプリの接続先)まで。グループの作成、グループの所属、アプリケーションを使えるグループの結びつけ、Authentik の管理者権限は、Authentik の画面で設定する(状態)。例外は、認証プロキシで守る画面を使えるグループだけ(後述)。権限はグループに付け、ユーザーには直接付けない。アプリは、Authentik が渡すグループ(`groups`)を見て権限を決める。
- Ansible が持つアカウントは、緊急用のユーザーだけにする。緊急用のパスワードは機械的に作った値をそのまま使う(人が決めるパスワードより強いため)。普段使うユーザーと、グループの所属は状態で、Authentik の画面で決める。MFA を登録していないユーザーには、ログインの途中で登録させる。
- Authentik には、Google でもログインできる(Authentik の外部のログイン元)。入れるのは、Authentik に作ってあるユーザーと、メールアドレスが一致する Google アカウントだけで、ユーザーを自動では作らない。Google でのログインでは Authentik の MFA を求めず、Google の2段階認証に任せる。パスワードでのログインも残す。OAuth クライアントの client_id と client_secret は `vault/authentik.yml` に置く。
- ログインの試行回数の制限は Authentik で行う。IP ごとに、ログインの失敗が成功を5回上回ると、その IP からのログインを拒否する(同じ IP からの成功は、失敗を1回ずつ打ち消す。最初の記録から1時間で解ける。緊急用の `akadmin` も同じ IP からは入れない)。アプリ側のパスワードのログイン(緊急用)には、この制限は効かない。
- グループからアプリの権限への対応づけは、アプリの画面で行う。Homarr は、Authentik と同じ名前のグループを Homarr の画面で作り、権限を付ける。OpenWebUI は、管理画面の OAuth の設定で行う(`ENABLE_OAUTH_PERSISTENT_CONFIG` で、画面からの変更を許す。画面で保存した OAuth の設定は DB に残り、環境変数より優先される)。例外は LiteLLM で、グループ `admins` を管理者にする対応づけだけを Ansible で設定する(`litellm_admin_group`)。LiteLLM の管理画面を使えるユーザーは、Authentik でアプリケーションにグループを結びつけて、管理者だけに絞る。
- 緊急用のユーザー: 各アプリに、Authentik が使えないときのための、パスワードでログインする管理者を1つずつ残す(Authentik の `akadmin`、Homarr・LiteLLM の `admin`、OpenWebUI の `admin@<lab_domain>`・表示名 `Admin`)。名前は、各アプリの公式の既定に合わせる(Homarr には既定がないため `admin`)。パスワードは機械的に作った 24〜32 文字の英数字で、vault にだけ置き、`ansible-vault view` で確認する。ログイン画面からパスワードの入力欄は隠さない。LiteLLM のマスターキーは API の鍵で、この規則の対象外。
- 認証プロキシ(Authentik の forward auth)は、自前のログインを持たない画面にだけ掛ける(現在は Longhorn の管理 UI)。Homarr・OpenWebUI・LiteLLM には掛けない。自前の OIDC のログインがあり、掛けると、Authentik が使えないときに緊急用のユーザーへ届かなくなり、API キーでの利用(LiteLLM の `/v1` など)も止まるため。
  - 守る画面は、Authentik のアプリケーション(プロキシプロバイダー、アプリケーションごとの forward auth)として Blueprint で宣言する(`authentik_proxy_apps`)。問い合わせには、Authentik 内蔵のアウトポストが答える。
  - Traefik のミドルウェア(`authentik` namespace の `forward-auth`)を、守る画面の Ingress に掛ける。ミドルウェアが無いとき、Traefik はその画面を通さない。
  - 使えるのは、グループ `admins` のメンバーだけ。これだけは、Authentik の画面ではなく Blueprint で宣言する(`authentik_proxy_access_group`)。守る画面は自分で権限を分けられず、入れた全員がすべての操作をできるため、結びつけを忘れても開かないようにする。グループ自体と所属は、Authentik の画面で作る。
- アプリの Pod が受ける通信は、NetworkPolicy で絞る。通すのは、同じ namespace、Traefik、名前を挙げた namespace だけ(PostgreSQL は、オペレーターと DB を使うアプリ。LiteLLM は OpenWebUI)。対象は `authentik`・`homarr`・`open-webui`・`litellm`・`postgresql` の namespace と、Longhorn の管理 UI の Pod(Longhorn 本体の API は、Longhorn のチャートが置く NetworkPolicy が、Longhorn の Pod だけに絞っている)。外向きの通信は絞らない(LLM の API、Google、Let's Encrypt などへ出るため)。クラスタの基盤(`kube-system`、MetalLB、cert-manager、CloudNativePG のオペレーター、Longhorn の本体)には掛けない。
- クラスタ内から公開ホスト名を引くと、Traefik の Service を返す(CoreDNS の `coredns-custom`)。Pod から Authentik への OIDC の通信が、外の DNS([network.md](network.md) の名前解決)に頼らないようにする。
- Homarr と OpenWebUI はボリュームを持たず、データを PostgreSQL に置く。LLM への接続は OpenWebUI の管理画面で登録する。SSO でのアカウント作成(`ENABLE_OAUTH_SIGNUP`)とメールでの統合(`OAUTH_MERGE_ACCOUNTS_BY_EMAIL`)を有効にする。Authentik では、ユーザーが自分でメールアドレスを変えられないようにする。
- Homarr の緊急用の管理者は、宣言できないため単発ツール(`playbooks/utils/homarr_admin.yml`)で作る。
- LiteLLM は、チャートの PostgreSQL を使わず、共有の PostgreSQL に接続する。モデルとプロバイダーの認証情報は、管理画面で登録する(`store_model_in_db` を有効にする。OAuth を使うプロバイダーは宣言できないため)。登録した内容と仮想キーは DB に保存される状態で、バックアップの対象になる。認証情報は `LITELLM_SALT_KEY`(`vault/litellm.yml`)で暗号化される。Hermes Agent が使うモデルの名前は `hermes_llm` にする。

### 未決(クラスタ内アプリ)

- Cloudflare Tunnel を通るログインでの、クライアントの IP の扱い。`cloudflared` の Pod から Traefik へ届く通信は、すべて同じ IP に見える。そのままでは、誰かの失敗で Tunnel 経由の全員がログインを拒否される。`auth` を Tunnel に載せる前に決める(Traefik が `cloudflared` からの転送ヘッダーを信頼するなど)。上流のルータが自宅LANを NAT する場合も同じ([network.md](network.md))。
- 公開ホスト名の DNS の切り替え。`*.cc-chacchan.com` は legacy(`172.16.12.11`)を向き、`auth`・`homarr`・`ai` は Cloudflare Tunnel 用の個別レコードがある。旧構成は移行中も止めない([network.md](network.md))ため、切り替えの時期と方法(アプリ単位か、サブドメインを分けるか)を決める。

## 未決

- k3s01 の仮想ディスク(k3s02・k3s03 と同じく1本にするか、Longhorn 用に別のディスクを足すか)。
- k3s02・k3s03 の仮想CPUのコア数と仮想ディスクのサイズ(pve02・pve03 は 4C/8T で、OS と Longhorn が同居する 1TB の SSD)。
- 3台の k3s を置く Proxmox ノード([hardware.md](hardware.md) の配置案を参照)。
- Longhorn の容量の最終値。
