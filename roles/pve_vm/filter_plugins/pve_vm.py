"""pve_vm ロールが、宣言値と VM の現在設定を比べるフィルタ。"""

from __future__ import annotations

import re

from ansible.errors import AnsibleFilterError


def _to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _tokens(value, bare=None):
    # "key=value,key=value" を要素の集合にする。先頭の key なしの値は bare=値 とみなす。
    tokens = set()
    for index, token in enumerate(str(value).split(",")):
        token = token.strip()
        if not token:
            continue
        if index == 0 and bare and "=" not in token:
            token = f"{bare}={token}"
        tokens.add(token)
    return tokens


def _items(value, split):
    return [item for item in re.split(f"[{re.escape(split)}]+", str(value)) if item]


def _differs(spec, current, desired):
    # current は設定に項目がないとき None。
    kind = spec["type"]
    if current is None:
        current = spec.get("default")
        if current is None:
            return True

    if kind == "bool":
        return _to_bool(current) != _to_bool(desired)
    if kind == "int":
        try:
            return int(float(current)) != int(float(desired))
        except ValueError:
            return True
    if kind == "str":
        return str(current).strip() != str(desired).strip()
    if kind == "prop":
        bare = spec.get("bare")
        return not _tokens(desired, bare) <= _tokens(current, bare)
    if kind == "set":
        return _tokens(desired) != _tokens(current)
    if kind == "list":
        wanted = [str(item) for item in desired]
        have = _items(current, spec["split"])
        if spec.get("sorted"):
            wanted, have = sorted(wanted), sorted(have)
        return wanted != have
    raise AnsibleFilterError(f"pve_vm_changes: 未知の type です: {kind}")


def pve_vm_changes(config, declared, specs, devices):
    """宣言値のうち、現在の設定と違うものを {オプション名: 宣言値} で返す。

    config:   proxmox_vm_info が返す VM の設定
    declared: 宣言された値 {オプション名: 値}(null は含めない)
    specs:    スカラー項目の仕様 {オプション名: {type, default, key, bare, split, sorted}}
    devices:  デバイスの辞書として扱うオプション名のリスト
    """
    changes = {}
    for name, value in declared.items():
        if name in devices:
            differing = {
                key: item
                for key, item in value.items()
                if key not in config or not _tokens(item) <= _tokens(config[key])
            }
            if differing:
                changes[name] = differing
            continue
        if name not in specs:
            raise AnsibleFilterError(f"pve_vm_changes: 仕様にない項目です: {name}")
        spec = specs[name]
        if _differs(spec, config.get(spec.get("key", name)), value):
            changes[name] = value
    return changes


_NET_OPTIONS = ("bridge", "firewall", "link_down", "macaddr", "model", "mtu", "queues", "rate", "tag", "trunks")
_NET_BOOLS = ("firewall", "link_down")
# 起動中の VM で変更すると、通信が切れるおそれがあるオプション(ブリッジ・タグの付け替え、NIC の取り外しと再接続)。
_NET_DISRUPTIVE = ("bridge", "tag", "model", "macaddr", "queues", "mtu", "firewall", "link_down", "trunks")


def _parse_net(value):
    # "virtio=MAC,bridge=vmbr021,tag=10" と "model=virtio,macaddr=MAC,bridge=…" の両方を読む。
    options = {}
    for token in str(value).split(","):
        token = token.strip()
        if not token:
            continue
        key, _, item = token.partition("=")
        if key in _NET_OPTIONS:
            options[key] = item
        else:
            options["model"] = key
            if item:
                options["macaddr"] = item
    return options


def _net_text(options):
    # モデルと MAC を先頭に、ほかは名前順に並べる。
    head = options.get("model", "virtio")
    if options.get("macaddr"):
        head = f"{head}={options['macaddr']}"
    rest = [f"{key}={options[key]}" for key in sorted(options) if key not in ("model", "macaddr")]
    return ",".join([head, *rest])


def pve_vm_nics(config, nets):
    """宣言した NIC のうち、現在の設定と違うものを返す。

    宣言したキーだけを比べ、宣言にないキー(MAC・MTU など)は現在値を保つ。
    戻り値: {"changes": {"net0": "文字列", …}, "disruptive": ["net0", …]}
    disruptive は、既存の NIC で _NET_DISRUPTIVE のオプションが変わるもの。モデルは、宣言したときだけ比べる(新しい NIC は virtio)。
    """
    changes, disruptive = {}, []
    for index, net in enumerate(nets):
        key = f"net{index}"
        declared = {name: value for name, value in net.items() if value is not None}
        for name in _NET_BOOLS:
            if name in declared:
                declared[name] = "1" if _to_bool(declared[name]) else "0"
        declared = {name: str(value) for name, value in declared.items()}

        existing = key in config
        current = _parse_net(config[key]) if existing else {}
        if not existing:
            declared.setdefault("model", "virtio")
        differing = [
            name
            for name, value in declared.items()
            if (current.get(name, "0") if name in _NET_BOOLS else current.get(name)) != value
        ]
        if existing and not differing:
            continue
        changes[key] = _net_text({**current, **declared})
        if existing and any(name in _NET_DISRUPTIVE for name in differing):
            disruptive.append(key)
    return {"changes": changes, "disruptive": disruptive}


def pve_vm_pending_keys(current, pending):
    """起動中の VM にまだ反映されていない設定のキー(現在値と、保留中の値が違うもの)。"""
    return sorted(
        key
        for key, value in pending.items()
        if key != "digest" and str(current.get(key)) != str(value)
    )


class FilterModule:
    def filters(self):
        return {
            "pve_vm_changes": pve_vm_changes,
            "pve_vm_nics": pve_vm_nics,
            "pve_vm_pending_keys": pve_vm_pending_keys,
        }
