# template.yml — テンプレートを単体で収束させる

(OS, ノード)単位のcloud-imageテンプレートを**単体で**作る。通常は [provision.yml](provision.md) が必要時に自動で行うため使わない。新しいOSの検証や、構築前のテンプレート事前準備に使う。

## 実行方法

インベントリを参照しない(直接実行のみ)。

```sh
ansible-playbook playbooks/pve/template.yml -e os=debian -e version=13 -e target_node=pve01
```

## 変数一覧

| 変数 | 型 | 必須 | 既定値 | 説明 |
| --- | --- | :-: | --- | --- |
| `os` | str | ✔ | - | `debian` / `ubuntu` / `rocky` / `almalinux`(カタログは [README.md](README.md#テンプレートの仕組み)) |
| `version` | str | ✔ | - | OSのバージョン(カタログに存在するもの。例 `13`) |
| `target_node` | str | ✔ | - | 構築先PVEノード(例 `pve01`) |
| `vmid` | int | | 規則(`9XXNN`)から算出 | テンプレートVMIDを明示する(検証用) |
| `name` | str | | OS・バージョン・ノードから算出 | テンプレート名を明示する(検証用) |
| `pve_storage` | str | | group_vars/all | テンプレート用ストレージ(`-e pve_storage=` や `pve_template_storage` で上書き可) |
| `pve_bridge` | str | | group_vars/all | テンプレートNICのブリッジ(同上) |
| `pve_template_image_storage` | str | | `local` | cloud-image置き場 |
| `pve_template_download_timeout` | int | | `300` | イメージダウンロード上限(秒) |
| `pve_template_disk_import_timeout` | int | | `600` | ディスク取り込み上限(秒) |
| `vault_proxmox_api_*` | str | ✔ | - | API認証4変数([vault/proxmox_api.yml](../../vault/proxmox_api.yml)) |

※ このplaybookは `hosts: localhost` のため group_vars/all が自動では届かず、vars_files で明示的に読み込んでいる。インベントリ外の環境でも `pve_storage` / `pve_bridge` はリポジトリの宣言から解決される。

## 動きかた

1. `os` / `version` / `target_node` を検証(カタログ外・形式ミスは実行前に停止)
2. テンプレートVMIDと名前を規則(`9XXNN` / `<os><version>-template-<node>`)から解決(`-e vmid=` / `-e name=` を渡した場合はその値)
3. 未作成なら、cloud-imageをPVEノードが**チェックサム検証付きで直接ダウンロード**し、テンプレートVMを作成して変換する(作成済みなら `changed=0`)

## AWXでの実行

Job Template **`pve-template`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。

- Survey: `os`(**必須**)、`version`(**必須**)、`target_node`(**必須**)

## つまずきやすいポイント

- **ノードごとに必要** → ストレージがノードローカルのため、VMを置く予定の全ノードにテンプレートが要る(provisionは自動で解決する)
- **「テンプレートではないVMが存在」** → テンプレート用VMIDに過去の残骸がいる。PVE UIで確認し、不要なら [destroy.md](destroy.md) で削除してから再実行
- **対応していないOS/バージョン** → カタログ([roles/pve_template/vars/os/](../../roles/pve_template/vars/os/))への追加が先
