# job_status.yml — AWXのJobの実行状況を取得する

Job IDを指定して現在の状態(status / 開始・終了時刻 / 所要秒)を表示する。`awx_job_wait=true` なら完了まで待つ(失敗ジョブは待ちタスクが失敗になる)。

## 実行方法

```sh
# 現在状況の表示のみ
ansible-playbook playbooks/utils/awx/job_status.yml -e job_id=123

# 完了まで待つ
ansible-playbook playbooks/utils/awx/job_status.yml -e job_id=123 -e awx_job_wait=true
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `job_id` | int | ✔ | | 対象のJob ID(`job_launch.yml` の出力かAWXのジョブ一覧で確認) |
| `awx_job_wait` | bool | | `false` | 完了まで待ってから表示する |
| `awx_job_timeout` | int | | `1800` | 完了待ちの上限(秒) |

## AWXでの実行

Job Template **`utils-awx-job-status`**。Surveyで `job_id`(必須)と `awx_job_wait` を回答する。

## つまずきやすいポイント

- **HTTPエラーで取得できない** → `job_id` の打ち間違い(削除済みJobは404)か、`vault/awx_api.yml` のトークン失効。トークンを含むためAPI呼び出しの詳細は `no_log` で伏せている(assertのメッセージにHTTP状態だけ出る)
- statusの意味: `successful` / `failed` / `error` / `canceled` が終端。`pending` / `waiting` / `running` は進行中
