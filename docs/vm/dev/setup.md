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

## 変数一覧(このplaybookに固有のもの)

接続系の共通変数は [../README.md](../README.md#共通の変数全サービスplaybook)。全既定値の正は [roles/vm_dev/defaults/main.yml](../../../roles/vm_dev/defaults/main.yml)。

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `vm_gui_required` | bool | | `false` | XFCE+xrdp+ブラウザまで入れるか |
| `pve_ssh_password` | str | | なし | ログインパスワードの同時設定(内包する [password.md](password.md) が処理) |
| `development_vscode_cleanup_retention_days` | int | | `14` | VSCode Server旧版の保持日数 |
| `development_default_browser_bin` | str | | Chrome | GUI時の既定ブラウザ |

## AWXでの実行

Job Template **`vm-dev-setup`**(定義: [awx/job_templates.yml](../../../awx/job_templates.yml))。Surveyは共通12問+`pve_ssh_password`(暗号化・任意)。

## つまずきやすいポイント

- **パスワード設定の内包位置はVM構築の後(最終ステップ)** → password.ymlはPVE側からVMを停止するが、停止要求はQEMUゲストエージェント経由で出る。エージェントを入れるのは `roles/vm` なので、それより前に置くと新規VMの初回構築でだけ停止がタイムアウトする(現在の順序はこの問題を回避済み)
- **GUIは重い** → `vm_gui_required=true` はディスク・メモリを多く使う。プロファイル(group_vars/dev.yml)のスペックを確認
- **Cockpit/xrdpに入れない** → PAMパスワード未設定。[password.md](password.md) で設定する
