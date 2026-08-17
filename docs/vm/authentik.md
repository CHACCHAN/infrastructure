# authentik.yml — Authentik(認証基盤)を構築する

Docker composeでAuthentik(OIDC SSO)をVMごと一気通貫で構築する。構築後は `http://<IP>:9000/`(初回セットアップは `/if/flow/initial-setup/`)。ヘルスチェック(`/-/health/ready/`)の応答まで確認してから終わる。

## 実行方法

```sh
# インベントリ実行(authentikグループの宣言どおり)
ansible-playbook playbooks/vm/authentik.yml

# 直接実行(インベントリ外に検証用をもう1台)
ansible-playbook playbooks/vm/authentik.yml \
  -e target=authentik02 -e profile=authentik -e vmid=902 -e node=pve02 -e ip=172.16.11.92
```

## 変数一覧(サービス固有の主要なもの)

接続系の共通変数は [README.md](README.md#共通の変数全サービスplaybook)。全既定値の正は [roles/vm_authentik/defaults/main.yml](../../roles/vm_authentik/defaults/main.yml)。

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `authentik_version` | str | | `2026.5.6` | イメージのバージョン |
| `authentik_http_port` / `authentik_https_port` | int | | `9000` / `9443` | 公開ポート |
| `authentik_install_dir` | str | | `/opt/authentik` | 配置先 |
| `authentik_pg_password` | str | | 自動生成 | DBパスワード(初回に生成し、再実行では既存値を引き継ぐ) |
| `authentik_secret_key` | str | | 自動生成 | Authentikの秘密鍵(同上) |
| `authentik_bootstrap_password` / `_email` / `_token` | str | | なし | 初期管理者の一括設定(**初回起動時のみ**反映) |
| `authentik_extra_env` | dict | | `{}` | 追加の環境変数 |

## AWXでの実行

Job Template **`vm-authentik`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。Surveyは共通12問(インベントリ実行なら全問未回答でよい)。サービス固有値を変えるときは変数欄で渡す。

## つまずきやすいポイント

- **パスワード類は自動生成される** → 明示指定しなくてよい。値はVM上の `.env` にある(再実行しても変わらない)
- **`authentik_bootstrap_*` は初回起動時のみ効く** → 2回目以降に変えたい場合はAuthentik UI側で操作する
- **他サービスのOIDC連携より先に構築する** → wg-easyやk8sアプリ群(pgAdmin等)のSSOはAuthentikを参照する
