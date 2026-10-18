---
name: new-host
description: Add a host (VM or physical machine) to the Ansible inventory following the VLAN / ID / VMID / IP rules. Use when a new VM, Proxmox node or other machine needs an inventory entry.
---

# new-host

The rules and the VLAN table are in [docs/design/network.md](../../../docs/design/network.md). This skill only describes the procedure.

## Rules in brief

- VLANs: 10 Proxmox nodes · 11 Private · 12 k3s · 13 Hermes Agent. Core (PBS, TrueNAS) has no VLAN yet (undecided); ask the owner before adding hosts there.
- `VMID = VLAN × 100 + ID`, `IP = 172.16.<VLAN>.<ID>`, gateway `172.16.<VLAN>.254`; ID is an integer 1–99, unique within the VLAN across physical and virtual hosts. Write it without leading zeros in YAML (`08` is read as a string, `010` as octal).
- Reserved IDs are listed in docs/design/network.md (for example VLAN12 `5` and `6`, the VIPs). Never assign them.
- A host belongs to the VLAN of its primary NIC. A second NIC on another network does not change the VMID.

## Steps

1. **Pick the VLAN** from the host's purpose. If the purpose does not clearly match one VLAN, or the VLAN is not in the table, ask the owner. Do not invent a VLAN.
2. **Pick an ID.** List existing IDs in `inventory/hosts/<NN>_*.yml` and skip reserved ones. Physical machines (for example PBS or TrueNAS) take an ID too, even though they have no VMID.
3. **Compute** VMID and IP with the formulas above. Confirm that neither is used anywhere else in the inventory (`grep` the VMID and the IP, then check `ansible-inventory --list`).
4. **Place the host** in `inventory/hosts/<NN>_<vlan-name>.yml`, under the group named after its role or service. The host name differs from the group name (`k3s01` in group `k3s`).
   - Declare `id`, plus `node` for VMs (physical machines have no node); the group declares `vlan`. VMID, IP, gateway and VLAN tag are derived in `inventory/group_vars/all/`. If that derivation does not exist yet, ask the owner before adding the host. Never hand-write derived values.
   - `node` is the Proxmox node (pveNN). k3s placement is decided in docs/design/k3s.md (ノード); follow it.
   - A Proxmox node (group `pve`) also declares `lan_nic`, the physical NIC number on the LAN side (bridges are `vmbr<lan_nic><VLAN>`, docs/design/pve.md), and `template_storage` once its storage layout is decided. Ask the owner for both; do not guess.
5. **Per-host overrides** (CPU, memory, disk) go next to the host only when they differ from the role defaults.
6. **Validate** with the `validate` skill: `ansible-inventory --graph` must print no warnings.

## Do not

- Copy a VMID or IP from `legacy/`; its numbering does not follow these rules, even where it also uses `172.16.x`.
- Create or modify the VM on Proxmox. That is a separate, explicitly requested run.
