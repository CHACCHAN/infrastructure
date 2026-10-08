# inventory_sync.yml — AWXのInventory Sourceを同期する

Project由来のInventory Source(既定: `lab` / `project-inventory`)の同期を実行し、Gitへpush済みの `inventory/` の変更をAWXへ反映させる。完了まで待ち、同期が失敗すればこのplaybookも失敗する。

通常は `update_on_launch: true`(ジョブ起動時に自動同期)のため不要だが、**ジョブを起動せずにインベントリだけ先に反映したい**とき(ホスト追加の確認など)に使う。

## 実行方法

```sh
# 既定(lab / project-inventory)を同期
ansible-playbook playbooks/utils/awx/inventory_sync.yml

# 別のInventory/Sourceを対象にする
ansible-playbook playbooks/utils/awx/inventory_sync.yml \
  -e inventory_name=lab -e inventory_source=project-inventory
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `inventory_name` | str | | `awx_inventory_name`(=lab) | 対象Inventory名。既定は [awx/inventory.yml](../../../awx/inventory.yml) から |
| `inventory_source` | str | | `awx_inventory_source_name`(=project-inventory) | 対象Source名。同上 |
| `awx_job_timeout` | int | | `600` | 同期完了待ちの上限(秒) |

## AWXでの実行

Job Template **`utils-awx-inventory-sync`**(Surveyなし。そのまま起動)。

## つまずきやすいポイント

- **同期してもホストが増えない** → AWXが見るのはGitのProject。手元の変更をcommit & pushしてから実行する(Projectは `scm_update_on_launch: true` のため同期時に最新化される)
