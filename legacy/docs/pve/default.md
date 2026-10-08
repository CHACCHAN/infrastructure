# <playbook名>.yml — <Proxmox側で何を収束させるか>

<!--
このディレクトリ(①Proxmox APIドメイン)のページはこのテンプレートに従う。
- 1ページ = 1playbook。ファイル名はplaybookと同名
- `##` 見出しは下記の名称・順序のまま使う。該当しない節だけ丸ごと削除し、固有の話題は該当する `##` の下に `###` で書く
- 文章もコメントも「説明」だけを書く。判断の経緯・変更の過程は書かない
- 変数の既定値の正は roles/pve*/defaults/main.yml と inventory/group_vars/
- 新規追加時は docs/pve/README.md のplaybook一覧にも1行足す
-->

<概要。2〜4文で「何を収束させるか」「インベントリ実行と直接実行の位置づけ」を書く。>

## 実行方法

### インベントリ実行

```sh
ansible-playbook playbooks/pve/<playbook名>.yml
ansible-playbook playbooks/pve/<playbook名>.yml -l <ホスト名>
```

### 直接実行(インベントリ外VM)

```sh
ansible-playbook playbooks/pve/<playbook名>.yml \
  -e target=<ホスト名> -e profile=<役割> -e vmid=<VMID> -e node=<ノード> -e ip=<IP>
```

## 変数一覧

<!-- 変数が少ないplaybookは小節を作らず表1つにする -->

### 必須(ホストごと)

| 変数 | 型 | 説明 |
| --- | --- | --- |
| `<変数>` | <型> | <説明> |

### 主な任意(既定値はrole defaultsまたはプロファイル)

| 変数 | 型 | 既定値 | 説明 |
| --- | --- | --- | --- |
| `<変数>` | <型> | `<既定値>` | <説明> |

### 認証情報(vault)

<vault/proxmox_api.yml など、参照する暗号化ファイルと変数名。>

## 動きかた

<APIをどの順で叩き、どの状態へ収束するか。番号付きリストか表で書く。>

## AWXでの実行

Job Template **`pve-<動詞>`**(定義: [awx/job_templates.yml](../../awx/job_templates.yml))。<Surveyの構成と注意点。>

## つまずきやすいポイント

- **<症状>** → <原因と対処>
