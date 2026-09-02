# dev/password.yml — ログインパスワードだけを更新する

開発VMのログインパスワード(**CockpitとxrdpのPAM認証**で使う。SSHは公開鍵のまま)だけを更新する。cloud-initの `cipassword` をPVE API経由で書き込み、反映のためVMの電源を再投入する。

## 実行方法

```sh
ansible-playbook playbooks/vm/dev/password.yml -e target=yuya-dev -e pve_ssh_password=<パスワード>
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `target` | str | ✔ | - | 対象ホスト(**1台のみ**。2台以上が対象だと実行前に止まる) |
| `pve_ssh_password` | str | ✔ | なし | 設定するパスワード。8文字以上・空白なし。未指定なら全スキップ(`changed=0`) |
| `pve_power_timeout` | int | | `300` | 停止待ちの上限(秒) |
| `pve_power_force` | bool | | `false` | ゲストが応答しない場合の強制停止 |
| `vault_proxmox_api_*` | str | ✔ | vault | cloud-initドライブの作り直しに必要(API4変数) |

## 動きかた

- `pve_ssh_password` を渡したときだけ動く。値はログにも `--diff` にも出ない
- **反映にはVMの電源再投入が要る**。cloud-initのドライブはPVEがVMの起動時に作り直すため、ゲスト内の `reboot` では反映されない。playbookが停止→起動まで行う
- **対象は1台まで**。1つのパスワードを複数VMへ配る事故と、広い指定で全VMを電源再投入する事故を防ぐ
- 電源再投入でcloud-initは初回相当の処理をやり直すため、**SSHホスト鍵も作り直される**(このリポジトリは検証しない設計のため影響なし。手元のsshクライアントは警告を出す)
- 最後にSSHで `passwd --status` が `P`(PAMで使える状態)になったことを確認する。SSH鍵が無い実行では確認をスキップし、Cockpitでの確認方法を案内する
- 冪等性の例外(渡したら必ず書き込む)である理由は [docs/pve/README.md](../../pve/README.md#冪等性の設計)

## AWXでの実行

Job Template **`vm-dev-password`**(定義: [awx/job_templates.yml](../../../awx/job_templates.yml))。Surveyは `target`(必須)+`pve_ssh_password`(**暗号化・必須**)の2問のみ。

- **必ず暗号化したSurveyで渡す**(Job Templateの変数欄は画面から見えるため)
- 手元の `-e` はシェル履歴に残る。使い捨てでないパスワードは履歴に残らない方法で渡す

## つまずきやすいポイント

- **`guest-ping failed - got timeout`** → 対象VMにQEMUゲストエージェントが未導入(中身を構築していない新規VM)。先に [setup.md](setup.md) を流すか、`-e pve_power_force=true`(猶予時間の経過後に強制停止)を付ける
- **パスワードが弱いと止まる** → 形式チェック(8文字以上・空白なし)は実行前に検証される
- **SSHが突然警告を出す** → 電源再投入でホスト鍵が変わったため(仕様)。接続自体は公開鍵のまま通る
