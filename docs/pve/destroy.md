# destroy.yml — VM/テンプレートを削除する

VMIDを直接指定して、**停止中の**VMまたはテンプレートを削除する。誤操作防止のため**VMIDの二重入力(confirm)が必須**。

## 実行方法

インベントリを参照せずVMIDだけで動くため、実行方法は1通り(直接実行のみ)。adhocで作った一時VMもそのまま削除できる。

```sh
ansible-playbook playbooks/pve/destroy.yml -e vmid=992 -e confirm=992
ansible-playbook playbooks/pve/destroy.yml -e vmid=992 -e confirm=992 -e purge=true        # バックアップジョブ等も掃除
ansible-playbook playbooks/pve/destroy.yml -e vmid=992 -e confirm=992 -e expect_name=tmp01 # 名前も照合してから削除
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `vmid` | int | ✔ | - | 削除対象のVMID |
| `confirm` | int | ✔ | - | 確認のためvmidと同じ値を再入力。不一致なら実行しない |
| `expect_name` | str | | なし | 指定時のみ、実VM名とも照合してから削除 |
| `purge` | bool | | `false` | バックアップジョブ・レプリケーション設定等も削除 |
| `pve_destroy_timeout` | int | | `300` | 削除待ちの上限(秒) |
| `vault_proxmox_api_*` | str | ✔ | - | API認証4変数([vault/proxmox_api.yml](../../vault/proxmox_api.yml)) |

## 動きかた

1. `vmid == confirm` を検証(不一致なら何もせず停止)
2. 対象を検索し、`expect_name` 指定時は実名とも照合
3. **停止中であることを確認**(起動中なら停止を促して停止)
4. 削除

## AWXでの実行

Job Template **`pve-destroy`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。

- Survey: `vmid`(**必須**)、`confirm`(**必須**。同じ値を再入力)
- `expect_name` / `purge` を使う場合は変数欄で渡す

## つまずきやすいポイント

- **「削除が拒否される」** → 仕様。`confirm` の不一致、または対象が起動中。先に [power.md](power.md) で `stopped` にする
- **消してよいVMか不安なとき** → `-e expect_name=<VM名>` を足すと、VMIDと名前の両方が一致したときだけ削除される
- **テンプレートも消せる** → 壊れたテンプレート(構築途中の残骸)の掃除にも使う。テンプレートのVMID体系は [README.md](README.md#テンプレートの仕組み)
