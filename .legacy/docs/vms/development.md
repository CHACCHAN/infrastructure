# development.yml
起動済みのVMに開発環境を構築します。

接続情報と共通オプションは [README](../README.md#全playbook共通の指定) を参照してください。

```sh
ansible-playbook playbooks/vms/development.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名>"
```

cockpitやRDPのログインパスワードはここでは設定しません。
**VM構築時のcloud-initで設定されたパスワード**をそのまま使用します。

## 指定できる項目
| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| `cockpit_user` | `vm_ssh_user` | cockpitのログインユーザー(dockerグループ追加もこのユーザー) |
| `vm_gui_required` | `false` | `true`でXFCE+xrdpのGUIデスクトップを構成(後述) |
| `development_vscode_cleanup_retention_days` | `14` | VSCode Serverの古い版を何日放置したら削除するか |
| `development_vscode_cleanup_schedule` | `weekly` | クリーンアップの実行頻度(systemdの`OnCalendar`書式) |
| `development_libvirt_default_network_autostart` | `true` | libvirtの`default`ネットワークを自動起動するか |
| `development_default_browser_bin` | `/usr/bin/google-chrome-stable` | 既定ブラウザの実行ファイル(GUI時のみ) |
| `development_default_browser_desktop` | `google-chrome.desktop` | 既定ブラウザのdesktopファイル(GUI時のみ) |
| `development_packagekit_dummy_ip4` | `10.99.99.1/24` | PackageKit対策のダミー接続のIP(後述) |
| `development_packagekit_dummy_gw4` | `10.99.99.254` | 同ゲートウェイ |

## 実施する内容
1. [全VM共通のセットアップ](../README.md#共通セットアップtasks)(OS確認、OS更新、タイムゾーン、
   ロケール、zram、sudoグループ、基本パッケージ、QEMUエージェント)
2. Cockpit + プラグイン
   - Cockpit本体(ログインはcloud-initで設定済みのパスワード)
   - Cockpit Navigator(ファイルブラウザ。後述)
   - Cockpit Machines(KVM/libvirt仮想マシン管理。後述)
   - Cockpit Docker Manager。**GPG署名の無い第三者リポジトリ**(`trusted=yes`)から
     導入するため、信頼できるソースかは各自でご判断ください
3. Docker(公式スクリプト。sudoなしで`docker`が使えます)
4. PackageKit(Cockpitの「ソフトウェア更新」)のオフライン誤検知の回避(後述)
5. kubectl・Helm(いずれも公式配布物・公式インストールスクリプト)
6. VSCode Server(Remote-SSH)の定期クリーンアップ。接続のたびに溜まる
   `~/.vscode-server/bin/<バージョン>` を、一定日数触られていなければsystemd timerで削除します
   (標準のCockpitのServicesページからそのまま確認・操作できます)
7. `vm_gui_required=true` のときのみXFCE + xrdp + ブラウザ(後述)

## Cockpit Navigator
Cockpit上でファイル操作ができるプラグイン
([45Drives/cockpit-navigator](https://github.com/45Drives/cockpit-navigator))。
Debian公式リポジトリに無いためGitHubのリリースから`.deb`を取得します。

**バージョンは固定していません。** 45Drivesは`.deb`が添付されないリリースも公開しているため、
「最新リリース」ではなく**アセットの有無で判定**して最新版を選びます。
配布は`bookworm`向けビルドですが、アーキテクチャ非依存(`Architecture: all`)の
JavaScript/PythonプラグインのためDebian 13でも動作します
(将来`trixie`向けが出ればそちらが優先されます)。

## Cockpit Machines
Cockpit上でKVM/libvirtの仮想マシンを管理できるプラグイン。
すべてDebian公式リポジトリのmainから導入します。

| パッケージ | 内容 |
| --- | --- |
| `qemu-system-x86` | x86仮想マシンのエミュレータ本体 |
| `libvirt-daemon-system` | libvirtデーモンとシステム設定一式 |
| `libvirt-clients` | `virsh` などの管理コマンド |
| `cockpit-machines` | Cockpitの仮想マシン管理プラグイン |

SSHユーザーは`libvirt`グループに追加されるため、`qemu:///system`への接続時に
polkitのパスワード入力を求められません(反映にはログインし直しが必要)。

### ネストした仮想化が必要です
**このVM自体がProxmox上のKVMゲストのため、VM内でさらに仮想マシンを動かすには
ホスト側でネストした仮想化を有効にする必要があります**(CPUタイプを `host` にするなど)。
これは `playbooks/proxmox/` 側の管轄で、本ロールでは行いません。

無効のままでもインストールは成功しますが、`/dev/kvm` が無いため仮想マシンは
TCG(ソフトウェアエミュレーション)で動作し**著しく低速**になります
(その場合はplaybook実行時に警告を表示します。構成は失敗しません)。

```sh
ls -l /dev/kvm                          # あればハードウェア支援が有効
grep -oE 'vmx|svm' /proc/cpuinfo | sort -u   # CPUの仮想化フラグ
virsh domcapabilities | grep -m1 domain      # kvm なら有効、qemu ならTCG
```

### defaultネットワーク
Debianの`libvirt-daemon-config-network`は`default`ネットワーク(NAT/`virbr0`、
`192.168.122.0/24`)を**定義するだけで自動起動を設定しません**。そのままだと再起動のたびに
非アクティブになり仮想マシン作成時に選べないため、本ロールで自動起動を有効化しています。
`192.168.122.0/24` が既存ネットワークと衝突する場合は
`-e "development_libvirt_default_network_autostart=false"` で無効にできます。

## PackageKitのオフライン誤検知への対処
Cockpitの「ソフトウェア更新」が `Cannot refresh cache whilst offline` で失敗するのを避けるため、
**NetworkManager管理下にダミーの仮想インターフェースを1つ追加**しています。

| 項目 | 値 |
| --- | --- |
| 接続名 / インターフェース名 | `packagekit-online-workaround` / `packagekit-fix` |
| IPアドレス / ゲートウェイ | `10.99.99.1/24` / `10.99.99.254`(実在しないアドレス) |
| 経路メトリック | `20000` |

**判定用の存在で、実際の通信には一切使いません。**

原因はCockpitのバグではなく、PackageKitとNetworkManagerの既知の相互作用です。
本環境ではeth0がifupdown(cloud-init)管理でNetworkManagerの管理対象外、docker0は
管理下だがゲートウェイを持ちません。PackageKitは自分で疎通確認せずNetworkManagerに
問い合わせるだけなので、「管理下にゲートウェイ付きの有効な接続が無い」→「ローカルのみ接続」→
オフラインと誤判定します(実際はeth0で正常に疎通しており`apt`は動きます)。

ダミー接続にはデフォルトゲートウェイが必要ですが、実通信の経路を奪わないよう
**メトリックを20000**にしてeth0側(metric 0)が常に優先されるようにしています。
アドレスが衝突する場合は
`-e "development_packagekit_dummy_ip4=172.31.99.1/24 development_packagekit_dummy_gw4=172.31.99.254"`
で変更できます。

```sh
nmcli general status        # CONNECTIVITY が full
ip route show default       # dev eth0 が最上位
```

## RDPデスクトップを追加する
`vm_gui_required=true` のときのみXFCEデスクトップ + xrdpを構成します
(**既定では一切インストールされません**)。接続先は**VM自身のIPの3389番ポート**で、
Windowsのリモートデスクトップ接続(mstsc)等からそのまま繋げます。

```sh
ansible-playbook playbooks/vms/development.yml -vv \
-e "vm_ip=<VMのIPアドレス> vm_ssh_user=<SSHユーザ名> vm_ssh_prikey=~/.ssh/<秘密鍵ファイル名> \
    vm_gui_required=true"
```

- ログインは**PAM経由のLinux通常ログインパスワード**です(RDP専用のパスワードはありません)
- ディスプレイタイプの変更は不要です。ホスト側で必要なのはQEMUゲストエージェントの
  有効化(`qm set <vmid> --agent enabled=1`)のみです

### 構成される内容
1. XFCE一式(X11セッション。**Waylandは対象外**)、日本語フォント、`dbus-x11`
2. `xrdp`(常時起動、ポート3389)。RDPセッションで`startxfce4`が起動するよう `~/.xsession`
   を配置します(パッケージのconffile `/etc/xrdp/startwm.sh` は変更しません)
3. ブラウザ(**Google Chrome** と **Firefox ESR**)。**既定はChrome**
   - ChromeはDebian公式リポジトリに無いため、Google公式aptリポジトリをGPG署名鍵付きで追加
   - 既定ブラウザは `x-www-browser`(update-alternatives)と `/etc/xdg/mimeapps.list` の両方で設定
   - Firefoxを既定にする場合: `-e "development_default_browser_bin=/usr/bin/firefox-esr
     development_default_browser_desktop=firefox-esr.desktop"`

ディスプレイマネージャ(lightdm等)は導入しません。xrdpは接続のたびに`xrdp-sesman`が
Xセッションを起動するため不要で、起動ターゲットも`multi-user.target`のままで動作します。
オンデマンド起動・アイドルタイムアウトは実装していません(常時起動を許容する方針)。

### 動作確認
```sh
systemctl status xrdp.service xrdp-sesman.service qemu-guest-agent.service
ss -tlnp | grep 3389

# デスクトップが表示されない場合
cat ~/.xsession-errors
journalctl -u xrdp.service -u xrdp-sesman.service
```
