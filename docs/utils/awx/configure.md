# configure.yml — AWX側の設定をコードから収束させる

AWXのProject / Inventory / Credential / Execution Environment / Job Template(+Survey)を、[awx/*.yml](../../../awx/) の定義どおりに**冪等に収束**させる。AWX UIでの手動設定は不要(UIで変えても次回実行で定義に戻る)。

## 実行方法

AWX API(OAuthトークン)経由のため、インベントリは使わない(直接実行のみ)。

```sh
# 事前に1回: トークンを設定(発行手順はファイル内コメント)
ansible-vault edit vault/awx_api.yml

# 初回(kubeconfigも登録する)
ansible-playbook playbooks/utils/awx/configure.yml \
  -e awx_kubeconfig_file=~/.kube/config

# 2回目以降(定義を変えたら流すだけ)
ansible-playbook playbooks/utils/awx/configure.yml
```

トークンをまだ発行していない初回は、awx.awxコレクション標準の環境変数で管理者ログインを渡せる(ブートストラップ経路。トークン設定後は不要):

```sh
export CONTROLLER_USERNAME=admin
export CONTROLLER_PASSWORD=<AWX管理者パスワード>   # 実体はクラスタのSecret awx-admin-password
ansible-playbook playbooks/utils/awx/configure.yml -e awx_kubeconfig_file=~/.kube/config
```

`-e 変数=値` は値を空白で切るため、kubeconfigのような複数行の値は渡せない(先頭の1語だけが届く)。パスで渡す `awx_kubeconfig_file` を使うか、内容を直接渡すなら `-e '{"awx_kubeconfig_content": "..."}'` のJSON形式にする。

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `vault_awx_host` / `vault_awx_oauthtoken` | str | ✔ | vault | AWXのURLとOAuthトークン([vault/awx_api.yml](../../../vault/awx_api.yml)) |
| `awx_admin_user` / `awx_admin_password` | str | 初回のみ | 環境変数 `CONTROLLER_USERNAME` / `CONTROLLER_PASSWORD` | トークン未発行時のブートストラップ認証(トークンが設定済みならそちらが優先) |
| `awx_vault_password` | str | | 環境変数から自動 | Vault credentialへ登録する復号パスワード。既定は `ANSIBLE_VAULT_PASSWORD_FILE` の中身(空ならcredential作成をスキップ) |
| `awx_kubeconfig_file` | str | 初回✔ | なし | k8s-deploy用kubeconfigのパス(例 `~/.kube/config`)。CLIからの推奨形 |
| `awx_kubeconfig_content` | str | | なし | kubeconfigの内容そのもの(AWXのSurveyとJSON形式の `-e` 用)。指定時はこちらが優先。どちらも未指定なら登録済みの値を変更しない |
| `awx_update_secrets` | bool | | `false` | Credentialの実値をAWX側へ上書きするか。ローテーション時のみ `-e awx_update_secrets=true` |
| `awx_project_update` | bool | | `false` | ProjectのGit同期を実行するか。新しいplaybookを参照するJob Templateを追加した実行では `-e awx_project_update=true` |
| `vault_awx_scm_prikey` | str | | vault | ProjectのSSH同期用GitHub秘密鍵。設定されているときのみSCM credentialを作成しProjectへ紐づけ |
| `awx_validate_certs` | bool | | `true` | AWX APIの証明書検証 |
| `awx_project_sync_timeout` | int | | `300` | ProjectのGit同期完了を待つ上限(秒) |
| 定義本体(`awx_project_*` / `awx_inventory_*` / `awx_credential_*` / `awx_ee_*` / `awx_job_templates` / `awx_survey_common`) | | ✔ | [awx/*.yml](../../../awx/) | 収束させる対象の宣言(単一の真実)。変更はファイル編集で |

## 動きかた

1. トークン未設定(`CHANGE_ME`)なら実行前に停止
2. Vault credential と kubeconfig credential が「登録済み」か「今回実値を渡した」かを確認し、Credential類(SCM→Vault→kubeconfig型→kubeconfig)を先に収束(Job Templateが名前で参照するため)
3. Project を収束させる(`awx_project_update=true` ならGitの最新リビジョンへ同期して完了を待つ。Job Template の playbook パスは同期済みリビジョンで検証される)→ Inventory + Source(Project由来 `inventory/`)→ EE を収束
4. `awx_job_templates` の全Job Templateを、共通Survey+JT固有Surveyを合成して収束(`k8s-deploy` の `app` 選択肢は `k8s_apps` から実行時解決)

## つまずきやすいポイント

- **`Playbook not found for project.`** → 新しい playbook が GitHub に push されていない(Project は `awx/project.yml` のブランチを同期する)。push してから再実行する
- **Job TemplateをAWX UIで直さない** → 定義は [awx/job_templates.yml](../../../awx/job_templates.yml) が正。UIの変更は次回のconfigure実行で上書きされる
- **kubeconfig credentialは「渡したときだけ」更新** → 毎回渡す必要はない。ローテーション時だけ `-e awx_kubeconfig_file=~/.kube/config` を付けて再実行する(渡した内容で常に上書きされるため `awx_update_secrets` は不要)
- **`clusters: / contexts: がありません` で止まる** → `-e awx_kubeconfig_content="$(cat ...)"` のように複数行の値を `-e 変数=値` で渡している。`awx_kubeconfig_file` かJSON形式で渡す
- **`Playbook not found for project.` が出るのに同期されない** → 既定ではProjectのGit同期を行わない。`-e awx_project_update=true` を付けて再実行する
- **EEイメージのpullに失敗する** → 実体は `ghcr.io/chacchan/awx-ee-custom:latest`([awx/execution_environment.yml](../../../awx/execution_environment.yml))。プライベートイメージのpullは replicator が配る `ghcr-pull-secret` に依存するため、pull失敗時はまずそちらを確認([docs/utils/awx/README.md](README.md#eeイメージのビルドと登録))
- **このplaybook自体をAWXのJTにはしていない** → AWXが自分の定義を書き換えるループを避けるため、実行はDevContainer等の外側から行う
