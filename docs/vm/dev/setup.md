# dev/setup.yml — 開発VMを一式構築する

開発VMをVMごと一気通貫で構築する: Cockpit(:9090)+Navigator/Machines/Docker Manager、Docker、kubectl/helm、VSCode Serverの定期掃除。`-e vm_gui_required=true` でXFCEデスクトップ+xrdp(:3389)+ブラウザも入る。

## 実行方法

```sh
# インベントリ実行(devグループ全台)
ansible-playbook playbooks/vm/dev/setup.yml
ansible-playbook playbooks/vm/dev/setup.yml -l yuya-dev   # 1台に絞る

# 直接実行(使い捨ての検証VM)
ansible-playbook playbooks/vm/dev/setup.yml \
  -e target=tmp01 -e profile=dev -e vmid=799 -e node=pve07 -e ip=172.16.11.99
```

## 変数一覧

接続系の共通変数は [../README.md](../README.md#共通の変数)。全既定値の正は [roles/vm_dev/defaults/main.yml](../../../roles/vm_dev/defaults/main.yml)。

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `vm_gui_required` | bool | | `false` | XFCE+xrdp+ブラウザまで入れるか |
| `cockpit_user` | str | | 接続ユーザー | Cockpitからdockerを操作するユーザー(dockerグループに追加する) |
| `pve_ssh_password` | str | | なし | ログインパスワードの同時設定(内包する [password.md](password.md) が処理) |
| `dev_vscode_cleanup_retention_days` | int | | `14` | VSCode Server旧版の保持日数 |
| `dev_default_browser_bin` | str | | Chrome | GUI時の既定ブラウザ |

## AWXでの実行

Job Template **`vm-dev-setup`**(定義: [awx/job_templates.yml](../../../awx/job_templates.yml))。Surveyは共通セット+`pve_ssh_password`(暗号化・任意)。

## つまずきやすいポイント

- **パスワード設定はVM構築の後に走る** → password.ymlはQEMUゲストエージェント経由でVMを停止する。エージェントを入れるのは `roles/vm` のため、setup.ymlは最後にpassword.ymlを呼ぶ
- **GUIは重い** → `vm_gui_required=true` はディスク・メモリを多く使う。プロファイル(group_vars/dev.yml)のスペックを確認
- **Cockpit/xrdpに入れない** → PAMパスワード未設定。[password.md](password.md) で設定する
