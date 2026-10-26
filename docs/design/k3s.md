# k3s 設計

## 決定済み

### ノード

- 3台とも k3s のサーバーで、ワークロードも動かす。k3s01 は pve01、k3s02 は pve02、k3s03 は pve03 に置く。etcd の台数を奇数に保つため、サーバーは3台にする。名前は `k3s01`〜`k3s03`、VMID は `1201`〜`1203`、IP は `172.16.12.1`〜`.3`(VLAN12)。
- 3台とも、仮想CPUは4コア、仮想ディスクは430GiBの1本で、置いたノードの `ssd01` に置く。Longhorn のデータも、このディスクに置く。430GiB は、いちばん小さい pve01 の `ssd01`(447GiB)に、テンプレート(3GiB)と、作り直すときの新しいテンプレートを並べて置ける大きさ([hardware.md](hardware.md))。
- OS は Debian 13 minimal。RAM は12GBで固定し、Proxmox のメモリバルーニングは切る。
- swap は使わない(ZRAM も使わない)。Pod の cgroup は `NoSwap` で swap を使えず、ZRAM が効くのは k3s 本体と OS のデーモンだけで、守りたい Pod に効かないため。メモリの逼迫は、`requests`・`limits` の設計とノードのメモリ量で防ぐ。

### VIP と Ingress

| 用途 | IP | 実装 |
| --- | --- | --- |
| Ingress(HTTP/HTTPS) | `172.16.12.5` | MetalLB(L2) |
| Kubernetes API | `172.16.12.6` | kube-vip |

- k3s の `servicelb` は無効にする。Traefik は k3s 内蔵のものを使う。
- Traefik を全ノードに置き(DaemonSet)、`externalTrafficPolicy: Local` にする。VIPを持つノードに必ず Traefik がいて、クライアントの実IPも保たれる(Authentik が、IP ごとにログインの失敗を数えるのに使う)。
- Traefik は、クラスタ内のサービスだけでなく、LAN内のサービス(Proxmox・TrueNAS・PBS の管理UI)へのリバースプロキシも兼ねる。ホスト名のDNSは `172.16.12.5` を指す。例: `pve01.cc-chacchan.com` → Traefik → `172.16.10.1:8006`。
- 管理UIは Cloudflare Tunnel を経由しない。

### ストレージとバックアップ

- Longhorn を使う。通常のPVCは複製数2にする。
- Longhorn の容量は、各 k3s ノードの既存の仮想ディスク(OS と共用の1本)を拡張して増やす。専用のディスクは追加しない。
- Longhorn で使える容量は、約440GiB(3台×430GiB から、Longhorn の既定の予約30%と OS の分を引き、複製数2で割った値)。ディスクは後から広げられるが、縮められない。
- k3s ノードは、VMとしてのバックアップを取らない。コード(Ansible・Helm・マニフェスト)から再構築する。
- Longhorn のバックアップ先(NFSのNAS)は未構築。**現時点では、k3s上の永続データにバックアップがない。**

### アプリ

- PostgreSQL は k3s で運用する。CloudNativePG(オペレーターの `cloudnative-pg` と、DB 本体を作る `cluster` の2つのチャート)を使う。PostgreSQL を使うアプリ(Authentik・OpenWebUI・LiteLLM)ごとに専用のクラスタを置き、アプリ同士で共有しない(1つのアプリの DB の障害・更新・削除を、ほかのアプリに及ぼさないため)。インスタンスは1つで、ボリュームは Longhorn(複製数2)に置く。
- 次のアプリを、旧構成から引き継いで k3s で動かす: Authentik、PostgreSQL、OpenWebUI。LiteLLM Proxy・CLIProxyAPI・Nextcloud Hub を新しく足す。CLIProxyAPI 以外は、Helm のチャートで入れる。
- 証明書は cert-manager で自動取得する。
- NAS ができるまで、データ保護の暫定策は設けない(オーナーの判断)。
- リモートアクセスの VPN(WireGuard)と DDNS は、ルータ(OPNsense)が担う予定。k3s では動かさない。
- 再現性の範囲:
  - 構成(VM、k3s、Helm のリリース、values、Secret)は、コードから再現する。
  - 設定のコード化は、宣言できるものを宣言する。アプリの OIDC クライアントは、Authentik の Blueprint で宣言する。client_id と client_secret は vault で決め、Authentik と各アプリに同じ値を渡す(Authentik を先に完成させる必要がない)。
  - 状態(ユーザー、パスワード、チャット、ボード、DB の中身)は、Ansible では管理しない。バックアップで守る(現在はバックアップなし)。例外は、各アプリの緊急用の管理者だけ。
  - アプリの中で足す拡張(Nextcloud のアプリ、CLIProxyAPI のプラグイン)も状態にする。Ansible が再現するのは、素のアプリ(インストール直後の状態)と、ほかの決定のために要る設定まで。
- Authentik は k3s で運用する。旧構成からは移さず、新規に構築する。OIDC クライアント、認証プロキシ、ログインの失敗の制限、MFA の必須化、Google でのログインは Blueprint で宣言し、ユーザー・グループ・グループの所属・アプリケーションを使えるグループの結びつけ・それ以外のフローは手動で設定する。
- Rancher、AWX、Portainer は使わない。k3s の Web UI は置かない(一時的なコンテナは、開発VMの Docker で動かす)。

### k3s の構築

- k3s01 を先に単独で構築する([network.md](network.md) の移行)ため、最初から次のようにする。
  - 組み込み etcd を有効にして(`cluster-init`)、k3s02・k3s03 を後から参加させられるようにする。
  - API の証明書に `172.16.12.6` を含め(`tls-san`)、接続先は最初から API の VIP にする。
  - Longhorn の複製数は、ノードが1台の間は1、2台以上なら2にする(インベントリの `k3s` グループのホスト数から導出する)。
- サーバーの参加: グループ `k3s` の先頭のホスト(k3s01)がクラスタを作り(`cluster-init`)、ほかのホストは API の VIP(`https://172.16.12.6:6443`)へ参加する。
  - クラスタのトークン(サーバーの参加に使う共有の秘密)は、ansible-vault(`vault/k3s.yml` の `vault_k3s_cluster_token`)に置き、全サーバーが同じ値を使う(`token-file`)。作り直しても同じトークンで再現できる。単発の playbook(`playbooks/utils/k3s_cluster_token.yml`)が、動いているクラスタのトークンを写す(クラスタが無ければ、秘密だけを新しく作る)。
  - 参加するホストは、トークンに含まれる認証局のハッシュで、参加先が本物のクラスタかを確かめる(VLAN12 で API の VIP を名乗られても、トークンを渡さない)。クラスタを作るホストは、秘密の部分だけを使う(認証局が作り直されても使えるため)。
  - 先頭のホストを作り直したとき、動いているクラスタとは別のクラスタを作らない(データが無く、API の VIP が応答していれば止める)。
  - k3s の設定の変更は、1台ずつ反映する(再起動が重なって etcd の過半数を失わないため)。
- k3s 標準の local-storage(local-path)を無効にし、Longhorn を既定の StorageClass にする。ノード内だけに残る PVC が意図せず作られ、別ノードで復帰できなくなるのを防ぐ。
- k3s は stable チャンネルの 1.36 系(`k3s_version`)を使う。リリースからバイナリを取得してチェックサムを検証し、systemd のユニットは Ansible が置く(インストールスクリプトは使わない)。Longhorn が要求する Kubernetes 1.34 以上を満たす。
- API の VIP を持つ kube-vip は、DaemonSet で動かす(ARP、リーダー選出)。マニフェストは k3s の自動適用ディレクトリ(`/var/lib/rancher/k3s/server/manifests/`)に置く。インターフェースはノードの既定経路のものを使う。

## 決定済み: ノードのネットワーク経路(案A)

k3s ノードのVMは、VLAN12 の1NIC(NIC1側の `vmbr`)だけにつなぐ。NIC2 はホスト専用にする。

### 通信の流れ

```text
LAN クライアント
  → ルータ(VLAN間ルーティング)
  → 172.16.12.5(MetalLB が ARP に応答するノード)
  → Traefik
  → ① クラスタ内サービス: Pod へ(別ノードなら flannel の VXLAN)
  → ② LAN内サービス(Proxmox・TrueNAS・PBS): デフォルトルートからルータへ → 実IP

公開アプリ(Cloudflare Tunnel)
  インターネット → Cloudflare → cloudflared Pod(クラスタから外向きに接続)
  → Traefik の Tunnel 専用の入口 → Pod        (172.16.12.5 を通らない)

kubectl・Ansible
  開発VM(VLAN11) → ルータ → 172.16.12.6:6443(kube-vip のリーダーノード)
```

### NICの扱い

| | 案A: VLAN12 のみ(NIC1) | 案B: VLAN12 + ストレージ用 VLAN(NIC1 + NIC2) |
| --- | --- | --- |
| 設定 | インターフェースが1つで単純 | `node-ip`・flannel のインターフェース・`tls-san`・kube-vip/MetalLB のインターフェースを分けて指定する |
| 帯域 | NIC1(1GbE)を Ingress・Longhorn の複製・リビルドで共有する | ノード間通信を、専用の1GbEへ逃がせる |
| 分離 | k3s の VM は NIC2 に触れない(NIC2 はホスト専用) | k3s の VM が NIC2 側のL2に載る。スイッチがVLAN非対応なので、分離はホストの設定だけ |
| Longhorn のバックアップ(→TrueNAS) | VLAN12 → ルータ → 基幹システムの VLAN | NIC2 経由で直接 |

案Aは、複雑さと分離の面で有利。帯域の不足は、実際に計測してから案Bまたは Longhorn の専用ストレージネットワークで補う。

### 確認が要る事項

- ルータ(OPNsense)が、VIP の切り替え時のGratuitous ARP を受け付け、ARPテーブルを更新するか。実機でフェイルオーバーを試す。
- VLAN をまたぐ通信(Ingress、Traefik から LAN内サービスへのプロキシ、Longhorn のバックアップ)は、ルータを通る。OPNsense のルーティング性能とフィルタ設定が、その実効帯域の上限になる。同じ VLAN12 の中のノード間通信(etcd・flannel・Longhorn の複製)は、SWHUB が中継し、ルータを通らない。
- Longhorn のリビルド中の Ingress への影響(同時リビルド数を制限する)。
- ノード停止時に、Longhorn のボリュームを持つ Pod が別ノードで復帰するか、復帰までの時間。Longhorn のノード停止時の Pod 削除ポリシーを設定したうえで、k3s の VM を止めて計測する。

## クラスタ内アプリの管理

クラスタ内アプリ(`k3s` / `k3s_<app>`)を、Helm で管理する方法。

### 決定済み

- アプリは Helm の実リリース(`helm upgrade --install` に相当。`kubernetes.core.helm`)で管理する。MetalLB・Traefik の公開設定・Longhorn など、クラスタに入れるものはすべてこの経路にする。例外は、LAN内サービスへのリバースプロキシ(`k3s_lan_proxy`)と CLIProxyAPI(`k3s_cliproxy`)で、チャートが無いため、同じ `k3s` ロールからマニフェストだけを適用する。
- チャートのバージョンは、ロールの `defaults/main.yml` にだけ書く([conventions.md](../conventions.md))。
- 秘密情報は vault に置き、playbook がロールへ渡す。
- kubeconfig を使わない。プロジェクトの外に機密情報を置かないため。接続先は API の VIP(`https://172.16.12.6:6443`)。
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

- 導入の順序: トークン → MetalLB → cert-manager → Longhorn → CloudNativePG のオペレーター → Authentik → OpenWebUI・LiteLLM・CLIProxyAPI → cloudflared。Longhorn の管理 UI は、Authentik を入れるまで開けない(認証プロキシのミドルウェアが無いため)。
- namespace はアプリごとに分ける(`cert-manager`、`longhorn-system`、`cnpg-system`、`authentik` など)。アプリ専用の DB(PostgreSQL)は、アプリと別の `<アプリの namespace>-db` に置く(アプリの namespace は Traefik からも受けるため、DB には届かないよう分ける)。
- 証明書:
  - Let's Encrypt と Cloudflare の DNS-01 を使う。ドメインは `lab_domain`(`cc-chacchan.com`、`inventory/group_vars/all/domain.yml`)。ホスト名がインターネットに出ないよう、ワイルドカード1枚(`*.cc-chacchan.com`)にする。
  - 証明書は `kube-system` に置き、Traefik の既定の証明書(`TLSStore` の `default`)にする。各アプリの Ingress は、証明書を個別に持たない。
  - 先に staging の発行者で動作を確認し、本番の発行者に切り替える(`cert_manager_issuer`)。
  - 自己チェックの DNS は、公開リゾルバ(`1.1.1.1`・`1.0.0.1`)を直接指す。ノードに渡す DNS サーバーが未決で、プライベートIPを返す応答の扱いも未決のため。
  - Cloudflare の API トークンは、対象ゾーンの DNS の編集とゾーンの読み取り(cert-manager がゾーンの ID を引くため)だけを許可する。`vault/cloudflare.yml` に置く。ACME の連絡先メールアドレスはインベントリに宣言する(`cert_manager_acme_email`)。
- Longhorn: 複製数は、ノードが1台の間は1、2台以上なら2(CSI・マネージャーの Pod の数は、ノードの数)。ノード停止時の Pod 削除ポリシーと、同時リビルド数の制限(1)を設定する。管理 UI は認証を持たないため、Authentik の認証プロキシを通して公開する(`longhorn`)。
- PostgreSQL: メジャーバージョン17、pgvector を含む CloudNativePG の `standard` イメージ。アプリごとの専用のクラスタ(1インスタンス、ボリューム 5Gi)は、アプリのロールが作る(`k3s_postgresql`)。DB とその所有者のロールを宣言で作り、パスワードはアプリの vault(`vault/<アプリ名>.yml`)に置く。スーパーユーザーのアクセスは無効にする。インスタンスが1つの間は PodDisruptionBudget を置かない(ノードの退避を止めないため)。CLIProxyAPI は PostgreSQL を使わない(後述)。
- 公開ホスト名は `<名前>.<lab_domain>` で、インベントリ(`inventory/group_vars/k3s.yml`)に宣言する(`auth`・`ai`・`litellm`・`longhorn`・`hermes`・`opnsense`・`cliproxy`・`nextcloud`)。TLS は Traefik で終端し、Ingress は Traefik の既定の証明書を使う。
- アプリの秘密情報は `vault/<アプリ名>.yml` に置く(DB のパスワードも含む)。
- ログインは、すべてのアプリで Authentik の SSO(OIDC)にする(OpenWebUI・LiteLLM・Nextcloud Hub)。Ansible が管理するのは、OIDC の接続(Authentik の OIDC クライアントと、各アプリの接続先)まで。本体が OIDC を持たないアプリは、OPNsense と同じく Authentik の OIDC クライアントだけを置き、アプリ側の接続はアプリの画面で設定する。グループの作成、グループの所属、アプリケーションを使えるグループの結びつけ、Authentik の管理者権限は、Authentik の画面で設定する(状態)。例外は、認証プロキシで守る画面を使えるグループだけ(後述)。権限はグループに付け、ユーザーには直接付けない。アプリは、Authentik が渡すグループ(`groups`)を見て権限を決める。
- Ansible が持つアカウントは、緊急用のユーザーだけにする。緊急用のパスワードは機械的に作った値をそのまま使う(人が決めるパスワードより強いため)。普段使うユーザーと、グループの所属は状態で、Authentik の画面で決める。MFA を登録していないユーザーには、ログインの途中で登録させる。
- Authentik には、Google でもログインできる(Authentik の外部のログイン元)。入れるのは、Authentik に作ってあるユーザーと、メールアドレスが一致する Google アカウントだけで、ユーザーを自動では作らない。Google でのログインでは Authentik の MFA を求めず、Google の2段階認証に任せる。パスワードでのログインも残す。OAuth クライアントの client_id と client_secret は `vault/authentik.yml` に置く。
- ログインの試行回数の制限は、LAN からのログインは Authentik で行う(外からのログインは Cloudflare)。IP ごとに、ログインの失敗が成功を10回上回ると、その IP からのログインを拒否する(同じ IP からの成功は、失敗を1回ずつ打ち消す。最初の記録から1時間で解ける。緊急用の `akadmin` も同じ IP からは入れない)。アプリ側のパスワードのログイン(緊急用)には、この制限は効かない。
- グループからアプリの権限への対応づけは、アプリの画面で行う。OpenWebUI は、管理画面の OAuth の設定で行う(`ENABLE_OAUTH_PERSISTENT_CONFIG` で、画面からの変更を許す。画面で保存した OAuth の設定は DB に残り、環境変数より優先される)。例外は LiteLLM で、グループ `admins` を管理者にする対応づけだけを Ansible で設定する(`litellm_admin_group`)。LiteLLM の管理画面を使えるユーザーは、Authentik でアプリケーションにグループを結びつけて、管理者だけに絞る。
- 緊急用のユーザー: 各アプリに、Authentik が使えないときのための、パスワードでログインする管理者を1つずつ残す(Authentik の `akadmin`、LiteLLM・Nextcloud Hub の `admin`、OpenWebUI の `admin@<lab_domain>`・表示名 `Admin`)。名前は、各アプリの公式の既定に合わせる(Nextcloud Hub は、イメージに既定がなく、チャートの既定の `admin`)。パスワードは機械的に作った 24〜32 文字の英数字で、vault にだけ置き、`ansible-vault view` で確認する。ログイン画面からパスワードの入力欄は隠さない。LiteLLM のマスターキーは API の鍵で、この規則の対象外。
- 認証プロキシ(Authentik の forward auth)は、自前のログインを持たない画面にだけ掛ける(現在は Longhorn の管理 UI)。例外として、ログインが共有の鍵1つだけの画面にも掛ける(現在は CLIProxyAPI の管理画面)。ユーザーを分けられず、MFA も無いため。OpenWebUI・LiteLLM には掛けない。自前の OIDC のログインがあり、掛けると、Authentik が使えないときに緊急用のユーザーへ届かなくなり、API キーでの利用(LiteLLM の `/v1` など)も止まるため。
  - 守る画面は、Authentik のアプリケーション(プロキシプロバイダー、アプリケーションごとの forward auth)として Blueprint で宣言する(`authentik_proxy_apps`)。問い合わせには、Authentik 内蔵のアウトポストが答える。アウトポストの設定(ブラウザを送る Authentik の URL など)も Blueprint で宣言する。
  - Traefik のミドルウェア(`authentik` namespace の `forward-auth`)を、守る画面の Ingress に掛ける。ミドルウェアが無いとき、Traefik はその画面を通さない。
  - 使えるのは、グループ `admins` のメンバーだけ。これだけは、Authentik の画面ではなく Blueprint で宣言する(`authentik_proxy_access_group`)。守る画面は自分で権限を分けられず、入れた全員がすべての操作をできるため、結びつけを忘れても開かないようにする。グループ自体と所属は、Authentik の画面で作る。
- アプリの Pod が受ける通信は、NetworkPolicy で絞る。通すのは、同じ namespace、Traefik、名前を挙げた namespace だけ(各アプリの PostgreSQL は、オペレーターとそのアプリ。LiteLLM は OpenWebUI。CLIProxyAPI は LiteLLM)。対象は `authentik`・`open-webui`・`litellm`・`cliproxy`・`nextcloud`・`cloudflared` と各アプリの DB(`<アプリの namespace>-db`)の namespace と、Longhorn の管理 UI の Pod(Longhorn 本体の API は、Longhorn のチャートが置く NetworkPolicy が、Longhorn の Pod だけに絞っている)。外向きの通信は絞らない(LLM の API、Google、Let's Encrypt などへ出るため)。クラスタの基盤(`kube-system`、MetalLB、cert-manager、CloudNativePG のオペレーター、Longhorn の本体)には掛けない。
  - NetworkPolicy を置く namespace と、追加で通す namespace は、インベントリ(`inventory/group_vars/k3s.yml`)の表 `helm_network_policies` に1か所で宣言する。各アプリのロールは、自分の namespace が表に無ければ止まる(宣言を忘れて NetworkPolicy が消えないため)。
  - 送信元の IP による受け入れの制限(Traefik の許可リストなど)は、クラスタ内では設定しない。どこから届くかは、上流のルータ(OPNsense)で一律に管理する。
- 外部への公開は Cloudflare Tunnel で行う。公開するのは Authentik・OpenWebUI・Nextcloud Hub。LiteLLM・CLIProxyAPI(プロバイダーの認証情報を持ち、API が課金や利用枠につながる)と Longhorn の管理 UI は公開せず、LAN と VPN から使う(CLIProxyAPI は管理画面だけ。API はクラスタ内からだけ)。
  - 公開するホスト名は、インベントリ(`inventory/group_vars/k3s.yml`)の `cloudflared_hosts` に宣言する。ここに無いアプリは、LAN と VPN からだけ使う。
  - `cloudflared` を k3s で動かし、Traefik の Tunnel 専用の入口(クラスタ内だけで開く)につなぐ。公開するアプリだけを、この入口に載せる。LAN 用の入口(`172.16.12.5`)とは別にし、外から届く経路を入口で絞れるようにする。
  - Tunnel・経路表(ホスト名から向け先への対応)・DNS は、Cloudflare の画面で管理する(状態)。Ansible が持つのは、`cloudflared` のコネクタ(トークンは `vault/cloudflared.yml`)と、Traefik の Tunnel 専用の入口に載せるアプリ(`cloudflared_hosts`)。
  - 経路表の向け先は、すべてのホスト名で Traefik の Tunnel 専用の入口(`https://traefik-tunnel.kube-system.svc.cluster.local:443`)にする。外部に出るアプリは `cloudflared_hosts` で決まり、画面にホスト名を足しただけでは届かない。
  - `cloudflared` の Pod は、外向きの通信も NetworkPolicy で絞る(通すのは、クラスタ内の DNS、Tunnel 専用の入口、インターネットだけ)。経路表がコードの外にあるため、画面の誤りや Cloudflare のアカウントの乗っ取りで、LAN 用の入口・LAN の機器・クラスタ内の別のサービスを向け先にされても届かないようにする。「外向きの通信は絞らない」の例外。
  - 緊急用のユーザーのパスワードのログインは、外からは使えないようにする(Authentik が使えないときは、LAN か VPN から使う)。OpenWebUI・Nextcloud Hub は、Tunnel 専用の入口でだけ、パスワードのログインのパスを通さない。
  - Tunnel 専用の入口では、届いた転送ヘッダー(`X-Forwarded-*`)を信頼しない。Cloudflare は、クライアントが付けた `X-Forwarded-For` を消さずに後ろへ追記し、Authentik は先頭を使うため、信頼すると、外部から IP を偽って、ログインの失敗の制限をすり抜けることも、LAN の IP を名乗って LAN のログインを締め出すこともできる。入口に第三者のプラグインを入れて IP を直すことはしない。
  - そのため、Tunnel を通る通信は、アプリからはすべて `cloudflared` の Pod の IP に見える。Authentik のログインの失敗の制限は、Pod のネットワークからのログインには掛けない(掛けると、誰かの失敗で外部の全員が拒否される)。この例外は `cloudflared` だけでなく、すべての Pod に効く(クラスタ内の Pod は、公開ホスト名で Authentik へ届く)。外からのログインの試行回数は、Cloudflare で絞る(WAF のレート制限。Cloudflare の画面で設定する)。Authentik の記録には、外からのログインのクライアントの IP は残らない。
  - 入口を指定しない経路は、LAN 用の入口にだけ載る(Tunnel 専用の入口には、明示した経路だけを載せる)。認証プロキシで守る画面は、外部に公開しない(Tunnel 専用の入口の経路には、ミドルウェアが掛からない)。
- LAN内サービスへのリバースプロキシ(`k3s_lan_proxy`、namespace は `lan-proxy`): Proxmox の管理 UI を `<ノード名>.<lab_domain>` で公開する。対象は、インベントリの `pve` グループから導出する。
  - 宛先の証明書は検証しない(Proxmox の証明書が自己署名のため)。
  - 認証プロキシは掛けない(自前のログインを持つため)。Cloudflare Tunnel には載せない。
  - TrueNAS と PBS は、接続したときに足す([network.md](network.md) の移行)。
  - Proxmox 以外の宛先は、インベントリの `lan_proxy_extra_services` に宣言する。現在は Hermes Agent の受付の管理画面(`hermes.<lab_domain>`。[hermes.md](hermes.md))と、ルータ(OPNsense)の管理画面(`opnsense.<lab_domain>` → `172.16.5.254:443`。宛先の証明書は検証しない)。
  - OPNsense の管理画面のログインは、OPNsense 側の OIDC で、Authentik に OIDC クライアント `opnsense` を置く(シークレットは `vault/opnsense.yml`)。OPNsense の OIDC の設定の Application code は `authentik` にする(コールバックのパス `/api/openidconnect/auth/callback/<Application code>` を、Authentik で完全一致で許可するため)。OPNsense 側の設定は、OPNsense の画面で行う(状態)。
  - Proxmox の管理画面のログインは、Proxmox の OpenID のレルムで、Authentik に OIDC クライアント `proxmox` を置く(シークレットは `vault/proxmox_oidc.yml`)。Proxmox は開いている画面の URL をリダイレクト URI にするため、Authentik は `pve` グループの各ノードの公開ホスト名(`https://<ノード名>.<lab_domain>`)だけを許可する。IP で開いた画面からは SSO を使えない。レルムの設定は、Proxmox の画面で行う(状態)。
- 公開ホスト名の DNS は、`*.<lab_domain>` を Ingress の VIP(`172.16.12.5`)へ向ける(Cloudflare の画面で管理する)。
- クラスタ内から公開ホスト名を引くと、Traefik の Service を返す(CoreDNS の `coredns-custom`)。Pod から Authentik への OIDC の通信が、外の DNS([network.md](network.md) の名前解決)に頼らないようにする。
- OpenWebUI はボリュームを持たず、データを PostgreSQL に置く。LLM への接続は OpenWebUI の管理画面で登録する。SSO でのアカウント作成(`ENABLE_OAUTH_SIGNUP`)とメールでの統合(`OAUTH_MERGE_ACCOUNTS_BY_EMAIL`)を有効にする。Authentik では、ユーザーが自分でメールアドレスを変えられないようにする。
- LiteLLM は、チャートの PostgreSQL を使わず、専用の PostgreSQL(`k3s_postgresql`)に接続する。モデルとプロバイダーの認証情報は、管理画面で登録する(`store_model_in_db` を有効にする。OAuth を使うプロバイダーは宣言できないため)。登録した内容と仮想キーは DB に保存される状態で、バックアップの対象になる。認証情報は `LITELLM_SALT_KEY`(`vault/litellm.yml`)で暗号化される。Hermes Agent が使うモデルの名前は `hermes_llm` にする。
- CLIProxyAPI(CLI の OAuth の認証情報を、OpenAI 互換などの API として出すプロキシ)は、`cliproxy.<lab_domain>` で LAN に公開する。
  - 外から使えるのは管理画面だけ。API は、クラスタ内の Service からだけ使う(LiteLLM だけが使う。LAN のクライアントは LiteLLM を経由する)。
  - 管理画面は OIDC を持たず、ログインは共有の管理キー(`vault/cliproxy.yml`)だけ。認証プロキシは、公開ホスト名のすべてのパスに掛ける。認証プロキシを通ったあとも、管理キーを求められる。
  - Authentik が使えないときは、k3s01 の上の `k3s kubectl port-forward` と SSH のポート転送で管理画面を使う(緊急用のユーザーの代わり)。
  - 設定とプロバイダーの認証情報は、Longhorn のボリューム(1Gi、Pod は1つ)にファイルで置く。設定の初期値(API キーなど)は、設定ファイルが無いときだけ Ansible が渡し、以降は管理画面で変えた内容がファイルに残る(状態)。
  - LiteLLM は、クラスタ内の Service へ直接つなぐ。
  - プラグインは有効にする(設定の初期値)。入れるのは、管理画面から公式ストアのもの(第三者の作者のものを含む)だけで、公式以外のストア(`plugins.store-sources`)は足さない。プラグインは CLIProxyAPI のプロセスの中で動き、認証情報に触れられるため、入れるものは人が選ぶ。
  - 入れたプラグインも、同じボリュームに置く。コンテナの中に置くと、Pod を作り直すたびに消えるため。
  - 管理画面のファイルは、CLIProxyAPI が GitHub の最新のリリースから取得する(バージョンを固定する規則の例外)。CLIProxyAPI に、取得するバージョンを指定する方法がないため。
- Nextcloud Hub を、ポータル(マニュアル・チャット・ファイル・予定の共有)として置き、LAN と Cloudflare Tunnel に公開する。公開ホスト名は `nextcloud.<lab_domain>`。
  - 使う機能は、Talk(チャットだけ)・ファイル・Collectives(マニュアル)・カレンダーと連絡先・Deck・External sites。
  - Talk は、通話を誰も始められないようにする。Talk を入れたあと、Talk の管理画面で通話の権限を設定する(状態)。通話用のサーバー(TURN・High-performance backend)は置かない。そのため、チャットの「入力中」の表示は出ない。
  - アプリは、既定で入っているものも含め、アプリストアを使える画面で追加・更新・有効化・無効化する(CLIProxyAPI のプラグインと同じく状態)。アプリとその版はボリュームの `custom_apps` と DB に保持し、バックアップで守る。Ansible が再現するのは、素の Nextcloud(インストール直後)と、ほかの決定のために要る設定だけ。
  - チャートは、コミュニティの `nextcloud/helm` で、公式の Docker イメージ(Apache 版)を使う。チャートに同梱の Bitnami のチャート(PostgreSQL・MariaDB・Redis)は使わない(Bitnami の無料のイメージは更新されないため)。DB は、ほかのアプリと同じく専用の PostgreSQL(`k3s_postgresql`)にする。
  - キャッシュは APCu だけにし、ファイルのロックは DB で行う(Redis は置かない)。使う人が少なく、部品を増やさないため。遅さが出たら、公式のイメージの Redis を足す。
  - バックグラウンドの処理(cron)は、チャートのサイドカー(同じ Pod の中のコンテナ)で動かす。別の CronJob にすると、別のノードで動いたときに Longhorn のボリューム(RWO)を付けられないため。
  - データは Longhorn のボリューム1つ(Pod は1つ)に置く。初期の容量は 50Gi で、使用量が7割を超えたら広げる(Longhorn のボリュームは付けたまま広げられるが、縮められない)。ユーザーごとの容量の上限は、既定で 10GB にする(`default_quota`)。Ansible は最初のインストールでだけこの初期値を設定し、その後の Nextcloud の画面での変更は保つ(状態)。
  - メモリを多く使うため、`heavy_workloads` のノードに寄せる([hardware.md](hardware.md))。
  - 設定は、Nextcloud の初期の値(インストール直後の値)のままにする。変えるのは、ほかの決定のために要るものだけ(以下)。
  - ログインは、`user_oidc` で Authentik の SSO にする。Nextcloud 本体は OIDC を持たないため、OPNsense と同じく、Ansible は Authentik の OIDC クライアント `nextcloud`(シークレットは `vault/nextcloud.yml`)だけを置く。`user_oidc` の導入と接続先の設定は、Nextcloud の画面で行う(状態。入力する値は [ロールの README](../../roles/k3s_nextcloud/README.md) に書く)。グループは、Authentik が渡すグループ(`groups`)を写し、グループのプロビジョニングを有効にする。管理者は Nextcloud の画面で付け、`admin` グループは写す対象に含めない(ホワイトリストの正規表現 `/^(?!admin$).*$/`。ログインのたびに外されないため)。画面で設定したプロバイダーが、公開ホスト名でクラスタ内の Authentik(プライベートの IP に解決する)へ届くよう、ローカルのアドレスへの通信を許す(`allow_local_remote_servers`。Nextcloud の既定では拒む)。そのため、ユーザーが指定する URL(カレンダーの購読、リンクのプレビューなど)でも、Nextcloud から LAN とクラスタ内へ届く。届く先は、ルータと NetworkPolicy で絞る。
  - 緊急用の `admin` は、最初のインストールのときに、チャートが vault のパスワードで作る。`admin` にはアプリパスワードを作らない(外からも使えるため)。
  - クライアント(同期・カレンダー・連絡先)には、アプリパスワードだけを使わせる(`token_auth_enforced`)。外からのクライアントは、ブラウザで Authentik にログインして、端末ごとのアプリパスワードを受け取る(Login Flow v2)。Tunnel 専用の入口で塞ぐのは、パスワードを受け取るパスだけで、このログインの流れは通す。
  - ログインの失敗の制限(IP ごと)は、Authentik と同じく、Pod のネットワークからの通信には掛けない(Tunnel を通る通信は、すべて `cloudflared` の Pod の IP に見えるため)。LAN からは、クライアントの実 IP で数える。外からの試行回数は Cloudflare のレート制限で絞り、対象に Nextcloud のログインと、同期・カレンダーのパス(`/remote.php` など)を含める。
  - 分割アップロードの大きさは 20MiB にする(`files.chunked_upload.max_size`)。Cloudflare の1リクエストの上限(100MB)を超えないため。分割に対応しないクライアントで 100MB を超えるファイルは、LAN か VPN から送る。iOS のアプリのバックグラウンドのアップロードが分割に従うかは、実機で確かめる。
  - External sites に並べるサイトと、その表示(リンクにするか、埋め込むか)は、画面で設定する(状態)。使い方に合わせて変わるため。
  - 各サービスの状態を一覧で表示するダッシュボードは置かない。ポータルは Nextcloud Hub にする。

### 未決(クラスタ内アプリ)

- 緊急用の `akadmin` を、外からのログインで拒否する方法。Authentik のログインは全員が同じ経路を通るため、経路では塞げない。`akadmin` の API トークン(`vault/authentik.yml`)も、外から Authentik の API に使える(MFA も試行回数の制限も通らない)。API のパスは画面も使うため、経路では塞げない。
- 自宅LANからラボへの通信が NAT される場合の、ログインの失敗の制限。LAN の全員が同じ IP に見え、誰かの失敗で全員が拒否される。NAT を1段だけにする方針([network.md](network.md))で、自宅LANとラボの間が NAT なしのルーティングになれば、起きない。

## 未決

- `ssd01` に収まらない容量が要るときの、ディスクの置き先(k3s01 のディスクを、Hermes と共用の pve01 の `ssd03` へ移すなど)。Nextcloud Hub のボリュームの容量と合わせて決める。
