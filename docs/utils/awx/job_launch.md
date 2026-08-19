# job_launch.yml — AWXのJob Templateを起動する

CLIからAWXのJob Templateを名前指定で起動する。既定では完了まで待ち、ジョブが失敗すればこのplaybookも失敗する(CIや手元スクリプトからの利用を想定)。

## 実行方法

```sh
# 起動して完了まで待つ(既定)
ansible-playbook playbooks/utils/awx/job_launch.yml -e job_template=pve-provision

# 変数を渡して起動(job_extra_varsは辞書なのでJSONで)
ansible-playbook playbooks/utils/awx/job_launch.yml -e job_template=pve-power \
  -e '{"job_extra_vars": {"target": "k8s", "state": "started"}}'

# 起動だけして戻る(Job IDが表示される)
ansible-playbook playbooks/utils/awx/job_launch.yml -e job_template=k8s-deploy -e awx_job_wait=false
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `job_template` | str | ✔ | | 起動するJob Template名(一覧は [docs/awx/README.md](README.md)) |
| `job_extra_vars` | dict | | なし | JTへ渡すextra vars(JT側は全て変数欄を許可済み) |
| `awx_job_wait` | bool | | `true` | 完了まで待つか。失敗ジョブは待ちタスクが失敗になる |
| `awx_job_timeout` | int | | `1800` | 完了待ちの上限(秒) |

接続情報は `vault/awx_api.yml` から自動供給(トークン未発行時は環境変数 `CONTROLLER_USERNAME` / `CONTROLLER_PASSWORD` にフォールバック。configure.ymlと同じ仕組み)。

## AWXでの実行

Job Template **`utils-awx-job-launch`**。Surveyで `job_template`(必須)と `awx_job_wait` を回答し、`job_extra_vars` は変数欄でYAML/JSON指定する。

## つまずきやすいポイント

- **extra varsが無視される** → 起動先JTが変数を受ける設定(`ask_variables_on_launch` かSurvey)になっているか。このリポジトリのJTは全て変数欄を許可している
- **完了待ちでタイムアウト** → `-e awx_job_timeout=3600` を足すか、`awx_job_wait=false` で起動だけして `job_status.yml` で追う
