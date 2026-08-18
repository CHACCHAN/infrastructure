# deploy.yml — k8sアプリ群を宣言どおりに収束させる

クラスタ上の全アプリ(またはapp指定で1つ)を、登録簿 `k8s_apps` の順に**冪等に収束**させる。書き込む前に「接続先が宣言(`k8s_api_server`)と一致するか」を検証するため、誤ったkubeconfigのまま別クラスタへ適用する事故は起きない。

## 実行方法

インベントリのホストへはSSHしない(kubeconfig経由でAPIサーバーだけを操作する `hosts: localhost` のplaybook)。

```sh
ansible-playbook playbooks/k8s/deploy.yml --check          # 差分の有無(クラスタに触らない)
ansible-playbook playbooks/k8s/deploy.yml                  # 全アプリ収束(収束済みならchanged=0)
ansible-playbook playbooks/k8s/deploy.yml -e app=portainer # 1アプリだけ
ansible-playbook playbooks/k8s/deploy.yml -e force=true    # フィールド所有権の衝突を強制取得(一度きり)
```

- 適用順は `k8s_apps` 登録簿([inventory/group_vars/all/k8s.yml](../../inventory/group_vars/all/k8s.yml))の並び順。依存(cert-manager→証明書、CRD→AWX)はロール内のwaitで担保
- `kubectl` の直接利用は状態確認(`get`/`describe`/`logs`)に限る。書き込みは必ずdeploy.yml経由

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `app` | str | | なし(=全アプリ) | 適用するアプリ1つ(`k8s_apps` にある名前) |
| `force` | bool | | `false` | SSAの所有権衝突(`FieldManagerConflict`)の強制取得。`--check` で差分確認してから一度だけ使う |
| `k8s_domain` | str | ✔ | group_vars | サービス公開ドメイン |
| `k8s_api_server` | str | ✔ | group_vars | 接続先検証に使うAPIサーバーURL |
| `k8s_apps` | list | ✔ | group_vars | アプリ登録簿(適用順) |
| `k8s_secret_*` | dict | ✔ | vault | Secret実値([vault/k8s_secrets.yml](../../vault/k8s_secrets.yml)。`ansible-vault edit` で編集) |
| 各アプリの `<役割>_helm_version` / `<役割>_values` ほか | | | role defaults | アプリごとの設定([README.md](README.md#アプリの追加のしかた)) |

接続(kubeconfig)は kubernetes.core の標準解決に任せている: `K8S_AUTH_KUBECONFIG` 環境変数 → `~/.kube/config` の順。

## AWXでの実行

Job Template **`k8s-deploy`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。

- Survey: `app`(任意・選択式。**選択肢は `k8s_apps` から自動生成**され二重管理しない)、`force`(任意・選択式)
- **kubeconfigはCredentialで渡す**: カスタムCredential Type `kubeconfig` が内容をファイルとして注入し `K8S_AUTH_KUBECONFIG` を設定する(登録は `playbooks/utils/awx/configure.yml -e awx_kubeconfig_content="$(cat ~/.kube/config)"`)
- AWX PodのServiceAccountへのフォールバックは**効かない**(内部APIのURLが宣言と一致せずpreflightで止まる)。これは事故防止の仕様

## つまずきやすいポイント

- **まず `--check`** → クラスタに触らず差分の有無だけ確認できる。バージョン更新や設定変更は必ずcheck→本適用の順
- **`changed=0` は成功** → 「何も起きなかった」ではなく「宣言どおりだった」
- **`FieldManagerConflict`** → 過去に別の管理者名で適用されたリソース。`--check` で差分を確認してから `-e force=true` を一度だけ
- **Secretを変えたのに反映されない** → vault編集後に該当アプリを `-e app=X` で適用する。Podへの反映はアプリによって再起動が要る
- **kubeconfigの置き場所** → 手元はDevContainerの `~/.kube/config`、AWXはCredential。playbook側の変数では渡さない(経路を1つにするため)
