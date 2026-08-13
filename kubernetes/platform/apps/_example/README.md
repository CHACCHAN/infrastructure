# _example — 自前コンテナのひな形

上流 Helm チャートが存在しないコンテナ (GHCR の自前イメージなど) を
k3s 上で動かすときの型。**どこからも参照されていない**ので、コピーして使う。

```sh
cp -r platform/apps/_example platform/apps/myapp
```

コピーしたら以下を置換する。

| 置換前 | 置換後 | 出てくる場所 |
| --- | --- | --- |
| `myapp` | アプリ名 | Deployment / Service / PVC / Ingress の名前、ラベル、selector |
| `ghcr.io/chacchan/myapp:1.0.0` | イメージ | Deployment |
| `8080` | コンテナの待ち受けポート | Deployment / Service |
| `myapp.cc-chacchan.com` | 公開ホスト名 | Ingress |
| `/data` `5Gi` | 永続ボリューム | Deployment / PVC |

最後に `platform/apps/kustomization.yaml` へ 1 行足す。

```yaml
resources:
  - myapp
```

確認してから適用する。

```sh
kubectl kustomize platform/apps/myapp   # レンダリング結果を見る
kubectl diff -k .                       # クラスタとの差分を見る
kubectl apply -k .
```

## 上流チャートがあるアプリの場合

こちらは使わない。同じ `platform/apps/<名前>/` に
`values.yaml` と `README.md` を置き、本体は helm で入れる。
kustomize が扱うのは `ingress.yaml` だけ。

[`platform/apps/portainer/`](../portainer/) が実例なので、
そのディレクトリごとコピーするのが早い。

```sh
cp -r platform/apps/portainer platform/apps/myapp
```

**`kubectl apply` に `--namespace` が要るかどうかはチャートごとに違う。**
必ず確認して README に書くこと (教科書 05 章)。

## 気をつけること

### イメージタグ

`latest` は使わない。再起動のたびに中身が変わって再現性がなくなる。
完全に固定したいなら digest を使う。

```yaml
image: ghcr.io/chacchan/myapp@sha256:e39ee8da81ad5e05d77f38d2f51c60ca51bf2a8450ac3abab50c17fdb91d91bf
```

### 秘密情報

マニフェストに書かない。base64 は暗号化ではないので、git に入れたら平文と同じ。
先に Secret を作って `envFrom` で読む。

```sh
kubectl -n platform create secret generic myapp-secrets \
  --from-literal=DB_PASSWORD='...'
```

```yaml
envFrom:
  - secretRef:
      name: myapp-secrets
```

### selector は変更できない

`spec.selector.matchLabels` は Deployment 作成後に変更できない。
変えたくなったら Deployment を作り直すことになる。
そのためひな形では `app.kubernetes.io/name` の 1 つだけにしてある。

### 更新戦略

PVC を `ReadWriteOnce` で使う場合、`strategy: Recreate` にしないと
新旧 Pod が同時にマウントできず、ローリング更新が `Multi-Attach` で
永久に止まる。ひな形は `Recreate` にしてある。

複数レプリカで共有したい場合は PVC の `accessModes` を `ReadWriteMany` にする
(`truenas-nfs` は NFS なので RWX が使える)。その場合は `RollingUpdate` に戻せる。

### PVC を消すとデータが消える

Helm 時代は PVC に `helm.sh/resource-policy: keep` を付けて
`helm uninstall` から守っていた。kustomize には削除の概念がないので、
`kubectl apply -k` で PVC が消えることはない。

ただし `kubectl delete -k` を打つと消える。**そのコマンドは使わないこと**。
不要になったリソースは、マニフェストを消したうえで
`kubectl delete <kind> <name>` と個別に指定して消す。

### StatefulSet が要る場合

このひな形は Deployment のみ。安定したネットワーク ID や Pod ごとの PVC が
要るミドルウェア (DB など) は、上流チャートを探すか専用のマニフェストを書く。
