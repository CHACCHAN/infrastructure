# Helm から 素マニフェスト + Kustomize への移行

> **このリポジトリのクラスタでは 2026-08-07 に実施済み。**
> 以下は実施手順の記録であり、同じことをするときの参照用。
> 実施結果は末尾の「実施ログ」を参照。

稼働中のサービスを止めずに、Helm リリースを kubectl 管理へ引き渡す手順。

一つ前の移行 (生マニフェスト → Helm チャート、2026-08-06 実施) の記録は
`git show <このコミットの親>:docs/MIGRATION.md` で読める。

## 何をどう置き換えたか

| 旧 (Helm) | 新 (Kustomize) |
| --- | --- |
| `charts/external-service` + `releases/external/*/values.yaml` | `platform/external/*/` の素マニフェスト |
| `charts/app-route` + `releases/apps/portainer/route.yaml` | `platform/apps/portainer/ingress.yaml` |
| `charts/app-workload` | `platform/apps/_example/` (コピーして使うひな形) |
| 上流チャート 3 本 (cert-manager / NFS / Portainer) | `values.yaml` + `README.md` のみ置き、`helm template \| kubectl apply` で適用 |
| `manifests/` | `namespaces/` `platform/certificates/` `cloudflare/cloudflared/` |
| `helmfile.yaml` | ルートの `kustomization.yaml` |

**リソースの名前は 1 つも変えていない**。Ingress / Service / EndpointSlice /
Middleware / ServersTransport はすべて同名のまま引き取られる。
そのため改名にともなう新旧併存の期間がなく、前回の移行より単純になる。

変わるのはラベルだけ。

| ラベル | 旧 | 新 |
| --- | --- | --- |
| `app.kubernetes.io/name` | `external-service` / `app-route` (チャート名) | `authentik` / `pve01` など (サービス名) |
| `app.kubernetes.io/managed-by` | `Helm` | `kustomize` |
| `app.kubernetes.io/instance` | リリース名 | (廃止) |
| `helm.sh/chart` | `external-service-0.1.0` | (廃止) |

Service はセレクタを持たない (`external-service` は EndpointSlice で
エンドポイントを手動管理する) ため、ラベルを変えても転送先は変わらない。
Deployment の `spec.selector` は不変フィールドだが、そちらは
上流チャートのレンダリング結果をそのまま適用するので変化しない。

## 事前に確認すること

### 上流チャートが namespace を出力するか

`helm template -n <ns>` は、チャートが `metadata.namespace` を明示していない場合、
**namespace のないマニフェストを出力する**。これを `kubectl apply` すると
`default` namespace に作られる。

このリポジトリでは `nfs-subdir-external-provisioner` が該当した
(ServiceAccount / Role / RoleBinding / Deployment の 4 つ)。
`kubectl apply --namespace storage` で補っている。

```sh
# どの namespace に落ちるかを事前に見る (クラスタは変わらない)
helm template <名前> <チャート> --version <v> -n <ns> \
  --values values.yaml --no-hooks \
  | kubectl apply --dry-run=server -f - -o json \
  | jq -r '.items[] | "\(.kind)/\(.metadata.name) ns=\(.metadata.namespace)"' | sort -u
```

### 逆に、namespace を一括指定してはいけないチャートもある

cert-manager が該当する。leaderelection の Role / RoleBinding は意図的に
`kube-system` にあり (`global.leaderElection.namespace` の既定値)、
`kubectl apply --namespace cert-manager` を付けるとエラーになる。

```
the namespace from the provided object "kube-system" does not match the
namespace "cert-manager". You must pass '--namespace=kube-system' ...
```

**チャートが `metadata.namespace` を正しく出力しているなら、何も指定しないのが正解。**

> 移行の途中、レンダリング結果をコミットして kustomize の `namespace:` で
> 打ち消す方式を一度試した。そのときも同じ罠を踏み、`kubectl diff` が
> 「新規作成される 4 リソース」として出してくれたので気づけた。
> **適用前に diff を見る理由がこれ。**

### Helm フックを除外する

`helm template` は Helm フック (cert-manager の `startupapicheck` Job、
portainer のテスト Pod) も出力する。kubectl 管理ではフックが実行されないので、
適用するとただのゴミリソースになる。特に Job は再適用時に
`field is immutable` で失敗する。

各 README の `helm template` コマンドには `--no-hooks` を付けてある。

### OCI チャートの情報行

OCI レジストリからチャートを取ると、helm は `Pulled:` / `Digest:` という
情報行を **stdout に混ぜてくる**。そのままファイルに落とすと YAML が壊れ、
kustomize が `missing Resource metadata` で失敗する。

そのため cert-manager は OCI ではなく HTTP リポジトリ
(`https://charts.jetstack.io`) を使っている。レンダリング結果は
OCI 版とバイト単位で同一であることを確認済み。

どうしても OCI を使う場合は最初の `---` より前を落とす。

```sh
helm template ... | sed -n '/^---$/,$p' | kubectl apply -f -
```

## 手順

### 0. 現状を控えておく

```sh
BK=.migration-backup/$(date +%Y%m%d-%H%M%S)
mkdir -p "$BK"

# リソースの現状
kubectl -n platform get ingress,svc,endpointslice,middleware,serverstransport -o yaml > "$BK/platform.yaml"

# Helm リリースの現状 (切り戻し用)
helm list -A -o yaml > "$BK/helm-releases.yaml"
for r in authentik proxmox truenas wg-easy technitium cloudflare-ddns-ui portainer portainer-route; do
  helm -n platform get manifest "$r" > "$BK/helm-manifest-$r.yaml"
done
for ns in platform cert-manager storage; do
  kubectl -n "$ns" get secret -l owner=helm -o yaml > "$BK/helm-release-secrets-$ns.yaml"
done

# 疎通のベースライン
for h in auth nas dns doh wgui ddns portainer pve01 pve02 pve03 pve04 pve05; do
  printf '%-10s https=%s http=%s\n' "$h" \
    "$(curl -s -o /dev/null -m 8 -w '%{http_code}' "https://$h.cc-chacchan.com/")" \
    "$(curl -s -o /dev/null -m 8 -w '%{http_code}' "http://$h.cc-chacchan.com/")"
done | tee "$BK/connectivity-before.txt"
```

> **バックアップには Helm リリース Secret が含まれる。git にコミットしないこと。**
> `.gitignore` に `.migration-backup/` を入れてある。

### 1. レンダリング結果を確認する

```sh
kubectl kustomize .        # 通ること
kubectl kustomize . | grep '^kind:' | sort | uniq -c   # リソース数が想定どおりか
```

### 2. 稼働中との差分を確認する

**ここが最重要**。差分が metadata (ラベル・注釈) だけであることを確認する。
spec に差分が出ていたら、マニフェストの書き写しを間違えている。

```sh
kubectl diff -k . > /tmp/diff.txt
grep -E '^[+-][^+-]' /tmp/diff.txt | sed -E 's/:.*/:/' | sort | uniq -c
```

新規作成 (`-` 側が空) のリソースが出ていないことも確認する。
出ていたら、名前か namespace が旧構成とずれている。

### 3. 適用する

```sh
kubectl apply -k . --server-side --force-conflicts
```

`--server-side` はフィールドの所有者を kubectl に移すため。Helm 4 は SSA を
使うので、付けないと以降の apply で所有権の衝突警告が出続ける。
`--force-conflicts` は Helm のフィールドマネージャから所有権を奪う指定で、
**リソースの削除も再作成もしない**。

この時点ではまだ Helm リリースが残っているので、失敗したら `helm rollback` で戻せる。

### 4. 疎通を確認する

```sh
for h in auth nas dns doh wgui ddns portainer pve01 pve02 pve03 pve04 pve05; do
  printf '%-10s https=%s http=%s\n' "$h" \
    "$(curl -s -o /dev/null -m 8 -w '%{http_code}' "https://$h.cc-chacchan.com/")" \
    "$(curl -s -o /dev/null -m 8 -w '%{http_code}' "http://$h.cc-chacchan.com/")"
done | diff -u "$BK/connectivity-before.txt" -
```

Pod が再起動していないことも見る。

```sh
kubectl get pod -A | grep -E 'cert-manager|nfs|portainer|cloudflared'
```

### 5. Helm リリースの記録を消す

**4 の確認が通ってから**実行する。

`helm uninstall` は使わない。リソースごと消える危険があるため
(`helm.sh/resource-policy: keep` を全リソースに付ければ防げるが、
1 つでも付け忘れると消える)。

リリース Secret を消すだけなら、リソースには一切触れない。

```sh
for ns in platform cert-manager storage; do
  kubectl -n "$ns" delete secret -l owner=helm
done
```

> **`kube-system` は対象外**。`traefik` / `traefik-crd` は k3s が
> HelmChart CRD で管理しているので、消すと k3s が作り直そうとして荒れる。

### 6. 残留メタデータを剥がす

リリース Secret を消しても、リソース側の注釈・ラベルは残る。
存在しないリリースを指したままなので剥がす。

```sh
# meta.helm.sh/* 注釈 (もう存在しないリリースを指している)
# helm.sh/chart + app.kubernetes.io/instance ラベル (廃止したローカルチャート由来)
kubectl -n platform annotate ingress,svc,endpointslice,middleware,serverstransport --all \
  meta.helm.sh/release-name- meta.helm.sh/release-namespace-
```

上流チャート由来のリソース (cert-manager / NFS / Portainer) に付いている
`helm.sh/chart` と `app.kubernetes.io/managed-by: Helm` ラベルは**剥がさない**。
レンダリング結果に含まれているので、次の apply で書き戻される。

### 7. 一致を確認する

リポジトリとクラスタが完全に一致していることを確認する。

```sh
kubectl diff -k . && echo "差分なし"
helm list -A          # traefik / traefik-crd だけが残るのが正解
```

## 切り戻し

### 5 より前 (Helm リリースが残っている)

```sh
helm -n platform rollback <リリース名>
```

### 5 より後

Helm リリースの記録は消えているので、リリース Secret を戻してから rollback する。

```sh
kubectl apply -f "$BK/helm-release-secrets-platform.yaml"
helm -n platform rollback <リリース名>
```

あるいはリソースを直接戻す。

```sh
kubectl apply -f "$BK/helm-manifest-<リリース名>.yaml"
```

## 移行にあたって直したこと

| 内容 | 理由 |
| --- | --- |
| `nfs-provisioner` の namespace を kustomize 側で `storage` に固定 | チャートが `metadata.namespace` を出力しないため、素の `kubectl apply` では 4 リソースが `default` に作られていた |
| `cloudflared` に `imagePullPolicy: IfNotPresent` を明示 | 稼働中の値は `Always` だった。イメージが `latest` だった頃に API サーバが埋めた既定値が、タグ固定後も残っていたもの。SSA で kubectl が所有権を取ると既定値が再計算されて `IfNotPresent` になり、意図しないローリング更新が 1 回起きた。明示しておけば以後ぶれない |
| `helm template --no-hooks` を使用 | Helm フック (cert-manager の `startupapicheck` Job、portainer のテスト Pod) が kubectl 管理ではゴミリソースになるため |
| OCI チャートの `Pulled:` / `Digest:` 行をコメントへ退避 | helm が stdout に混ぜてくるため、そのままでは YAML が壊れる |
| ラベルを `app.kubernetes.io/name: <サービス名>` に変更 | 旧構成では全リソースが `external-service` (チャート名) だったため、`-l app.kubernetes.io/name=truenas` のような絞り込みができなかった |

## 未対応 / 要判断

- **Cloudflare Tunnel のオリジンが平文 HTTP**。
  `auth.cc-chacchan.com` → `http://traefik.kube-system.svc.cluster.local:80`。
  Cloudflare 側の設定 (このリポジトリの管理外) を
  `https://traefik.kube-system.svc.cluster.local:443` + `noTLSVerify` に変えれば、
  Authentik も `websecure` 専用にできて web エントリポイントを完全に閉じられる。
  それまでは Traefik の web → websecure 常時リダイレクトを**有効にしないこと**
  (cloudflared が 301 を返し続けてリダイレクトループになる)。
- **`.legacy/` に秘密鍵と Secret マニフェストが git 追跡されたまま残っている**
  (`infrastructure/jupyter-lab/jupyterhub/tls.key` ほか)。
  今回の移行では触っていない。履歴に入っているため `.gitignore` では消えず、
  除去するには `git filter-repo` 等での履歴書き換えが要る。
  該当する鍵・認証情報は失効済みとして扱うこと。
- **Technitium の DoH で JSON API (`accept: application/dns-json`) を叩くと
  `http://doh.cc-chacchan.com` へ 302 が返る**。Technitium が自分の外部 URL を
  http と認識しているため。RFC 8484 の wire format
  (`accept: application/dns-message`) は 200 を返すので、実際の DoH
  クライアントには影響しない。気になる場合は Technitium の管理画面で
  Web Service の URL 設定を https に直す (このリポジトリの管理外)。
- cloudflared の 2 レプリカが同じノードに乗ることがある。
  `topologySpreadConstraints` は `whenUnsatisfiable: ScheduleAnyway` の
  ソフト制約なので、ローリング更新の途中経過によっては寄る。
  厳格にしたい場合は `DoNotSchedule` にする (ノード障害時にスケジュール
  できなくなるリスクとのトレードオフ)。

## Kustomize にして失ったもの

正直に書いておく。

- **記述量が増えた**。`external-service` チャートは values 約 10 行から
  Service / EndpointSlice / Ingress / Middleware を生成していた。
  同じものを素の YAML で書くと 60〜80 行になる。
  Proxmox の 5 ノードのように同型のものが並ぶ場合、差分は IP とホスト名だけなのに
  ファイルを 5 つ持つことになる。
- **依存順序を表現できない**。helmfile の `needs` に相当するものがない。
  通常運用では問題にならない (全部揃っている状態に収束させるだけ) が、
  新規構築時は README の「新規構築」のように手で 2 段階に分ける必要がある。
- **バリデーションがない**。旧チャートは `image.tag: latest` や
  `host` 未指定をレンダリング時に `fail` で弾いていた。素の YAML にその機構はない。

- **`kubectl apply -k .` だけではクラスタが揃わない**。上流チャートを使う 3 つは
  別コマンドになる (手順は [system/README.md](../system/README.md))。
- **上流の変更が事前に見えない**。レンダリング結果をコミットしていないので、
  何が変わるかは `| kubectl diff -f -` を打つまで分からない。

得たものは、テンプレート言語を読まなくてよいこと、`kubectl kustomize` の出力が
そのまま適用されると信じられること、そしてリポジトリが小さく保てること。

## 実施ログ (2026-08-07)

| 項目 | 結果 |
| --- | --- |
| 適用したリソース | 108 個 (`serverside-applied`)。エラー 0 |
| リソースの再作成 | **なし**。全 44 リソースが「更新」扱いで、新規作成 0 |
| 稼働中との差分 | metadata のみ (ラベル 81 行 + EndpointSlice の `generation` 10 件)。spec の差分 0 |
| Pod の再起動 | cloudflared のみ (`imagePullPolicy` の既定値再計算による。上表参照)。cert-manager / portainer / nfs は age 3 日以上を維持 |
| PVC | `portainer` は Bound のまま。データ影響なし |
| HTTPS / HTTP 疎通 | 全 12 ホストで移行前と**完全一致** |
| DoH (wire format) | 200 |
| 削除した Helm リリース | 10 個 (`authentik` `cloudflare-ddns-ui` `portainer` `portainer-route` `proxmox` `technitium` `truenas` `wg-easy` `cert-manager` `nfs`) |
| 残した Helm リリース | `traefik` / `traefik-crd` (k3s 管理のため対象外) |
| 剥がしたメタデータ | 138 件 (注釈 98 + ラベル 40)。失敗 0 |
| 最終確認 | `kubectl diff -k .` が差分なし = リポジトリとクラスタが完全一致 |

移行前の状態は `.migration-backup/20260807-003137/` に保存した
(`.gitignore` 済み。長期保存したい場合はリポジトリ外へ退避すること)。
