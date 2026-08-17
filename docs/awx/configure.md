# configure.yml — AWX側の設定をコードから収束させる

AWXのProject / Inventory / Credential / Execution Environment / Job Template(+Survey)を、[awx/*.yml](../../awx/) の定義どおりに**冪等に収束**させる。AWX UIでの手動設定は不要(UIで変えても次回実行で定義に戻る)。

## 実行方法

AWX API(OAuthトークン)経由のため、インベントリは使わない(直接実行のみ)。

```sh
# 事前に1回: トークンを設定(発行手順はファイル内コメント)
ansible-vault edit vault/awx_api.yml

# 初回(kubeconfigも登録する)
ansible-playbook playbooks/awx/configure.yml \
  -e awx_kubeconfig_content="$(cat ~/.kube/config)"

# 2回目以降(定義を変えたら流すだけ)
ansible-playbook playbooks/awx/configure.yml
```

トークンをまだ発行していない初回は、awx.awxコレクション標準の環境変数で管理者ログインを渡せる(ブートストラップ経路。トークン設定後は不要):

```sh
export CONTROLLER_USERNAME=admin
export CONTROLLER_PASSWORD=<AWX管理者パスワード>   # 実体はクラスタのSecret awx-admin-password
ansible-playbook playbooks/awx/configure.yml -e awx_kubeconfig_content="$(cat ~/.kube/config)"
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `vault_awx_host` / `vault_awx_oauthtoken` | str | ✔ | vault | AWXのURLとOAuthトークン([vault/awx_api.yml](../../vault/awx_api.yml)) |
| `awx_admin_user` / `awx_admin_password` | str | 初回のみ | 環境変数 `CONTROLLER_USERNAME` / `CONTROLLER_PASSWORD` | トークン未発行時のブートストラップ認証(トークンが設定済みならそちらが優先) |
| `awx_vault_password` | str | | 環境変数から自動 | Vault credentialへ登録する復号パスワード。既定は `ANSIBLE_VAULT_PASSWORD_FILE` の中身(空ならcredential作成をスキップ) |
| `awx_kubeconfig_content` | str | 初回✔ | なし | k8s-deploy用kubeconfigの内容。未指定なら登録済みの値を変更しない |
| `awx_scm_username` / `awx_scm_token` | str | | なし | プライベートリポジトリ用のSCM認証(GitHubユーザー+PAT)。指定時のみcredential作成 |
| `awx_validate_certs` | bool | | `true` | AWX APIの証明書検証 |
| 定義本体(`awx_project_*` / `awx_inventory_*` / `awx_credential_*` / `awx_ee_*` / `awx_job_templates` / `awx_survey_common`) | | ✔ | [awx/*.yml](../../awx/) | 収束させる対象の宣言(単一の真実)。変更はファイル編集で |

## 動きかた

1. トークン未設定(`CHANGE_ME`)なら実行前に停止
2. Credential類(SCM→Vault→kubeconfig型→kubeconfig)を先に収束(Job Templateが名前で参照するため)
3. Project(Git同期)→ Inventory + Source(Project由来 `inventory/`)→ EE を収束
4. Job Template 14本を、共通Survey+JT固有Surveyを合成して収束(`k8s-deploy` の `app` 選択肢は `k8s_apps` から実行時解決)

## つまずきやすいポイント

- **Job TemplateをAWX UIで直さない** → 定義は [awx/job_templates.yml](../../awx/job_templates.yml) が正。UIの変更は次回のconfigure実行で上書きされる
- **kubeconfig credentialは「渡したときだけ」更新** → 毎回渡す必要はない。ローテーション時だけ `-e awx_kubeconfig_content=` を付けて再実行
- **EEイメージのURLが未設定** → [awx/execution_environment.yml](../../awx/execution_environment.yml) の `awx_ee_image` を、push先レジストリのURLへ更新してから再実行([README.md](README.md#eeイメージのビルドと登録))
- **このplaybook自体をAWXのJTにはしていない** → AWXが自分の定義を書き換えるループを避けるため、実行はDevContainer等の外側から行う
