"""実際の Ansible をローカル HTTPS API に接続し、秘密と再試行を検証する。"""

import hashlib
import http.server
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class MockApi(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, data, status=200):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        state = self.server.state
        path = urlsplit(self.path)
        state["reads"].append(self.path)
        if path.path == "/model/info":
            self.reply({"data": state["models"]})
        elif path.path == "/key/list":
            self.reply({"keys": list(state["keys"].values()), "total_count": len(state["keys"]),
                        "total_pages": 1 if state["keys"] else 0, "current_page": 1})
        elif path.path == "/credentials":
            self.reply({"success": True, "credentials": []})
        elif path.path == "/router/settings":
            self.reply({"current_values": {"routing_groups": state["routing_groups"],
                                           "fallbacks": state["fallbacks"]},
                        "source": {"routing_groups": "db", "fallbacks": "db"}})
        elif path.path == "/api/v3/core/applications/":
            query = parse_qs(path.query)
            if query.get("superuser_full_list") != ["true"]:
                return self.reply({"results": [], "pagination": {"count": 0, "total_pages": 0}})
            page = int(query["page"][0])
            apps = state["apps"]
            self.reply({"results": apps[(page - 1) * 100:page * 100], "pagination": {
                "count": len(apps), "total_pages": (len(apps) + 99) // 100, "current": page}})
        else:
            self.reply({}, 404)

    def body(self):
        return json.loads(self.rfile.read(int(self.headers["Content-Length"])))

    def do_POST(self):
        state = self.server.state
        body = self.body()
        state["writes"].append((self.path, body))
        if self.path == "/key/generate":
            if any(row.get("key_alias") == body.get("key_alias") for row in state["keys"].values()):
                return self.reply({"error": "表示名はキーごとに一意である必要があります"}, 409)
            key_hash = digest(body["key"])
            state["keys"][key_hash] = {"token": key_hash, "blocked": False,
                                       **{key: value for key, value in body.items() if key not in ("key", "key_type")}}
        elif self.path == "/key/regenerate":
            old = state["keys"].pop(body["key"])
            key_hash = digest(body["new_key"])
            state["keys"][key_hash] = {**old, "token": key_hash}
        elif self.path in ("/key/block", "/key/unblock"):
            state["keys"][body["key"]]["blocked"] = self.path.endswith("/block")
        elif self.path == "/config/update":
            # 管理画面と同じく、送った項目だけを置き換える。
            state.update(body["router_settings"])
        else:
            return self.reply({}, 404)
        if state["fail_after_commit"]:
            state["fail_after_commit"] = False
            self.reply({"error": "模擬的な応答失敗"}, 503)
        else:
            self.reply({"ok": True})

    def do_PATCH(self):
        state = self.server.state
        body = self.body()
        state["writes"].append((self.path, body))
        if self.path.startswith("/api/v3/core/applications/"):
            slug = self.path.rstrip("/").split("/")[-1]
            app = next(row for row in state["apps"] if row["slug"] == slug)
            app.update(body)
        elif self.path.startswith("/model/"):
            model_id = self.path.split("/")[2]
            model = next(row for row in state["models"] if row["model_info"]["id"] == model_id)
            model["model_name"] = body["model_name"]
            model["litellm_params"].update(body["litellm_params"])
        else:
            return self.reply({}, 404)
        self.reply({"ok": True})


class ApiTaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tls_dir = tempfile.TemporaryDirectory(prefix="ansible-api-tls-")
        cert_dir = Path(cls.tls_dir.name)
        cls.cert = cert_dir / "cert.pem"
        cls.private = cert_dir / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-keyout", str(cls.private), "-out", str(cls.cert), "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=DNS:localhost"], check=True, capture_output=True)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockApi)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cls.cert, cls.private)
        cls.server.socket = tls.wrap_socket(cls.server.socket, server_side=True)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.url = "https://localhost:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join()
        cls.tls_dir.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="ansible-api-test-")
        self.work_path = Path(self.work.name)
        self.password = self.work_path / "vault-password"
        self.password.write_text("local-test-password\n")
        self.password.chmod(0o600)
        self.key_file = self.work_path / "keys.yml"
        self.state = {"keys": {}, "models": [], "routing_groups": [], "fallbacks": [], "apps": [], "reads": [], "writes": [], "fail_after_commit": False}
        self.server.state = self.state
        self.env = {"HOME": self.work.name, "PATH": os.environ["PATH"], "LANG": "C.UTF-8",
                    "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"),
                    "ANSIBLE_ROLES_PATH": str(ROOT / "roles"),
                    "ANSIBLE_FILTER_PLUGINS": str(ROOT / "filter_plugins"),
                    "ANSIBLE_VAULT_PASSWORD_FILE": str(self.password),
                    "SSL_CERT_FILE": str(self.cert), "NO_PROXY": "localhost,127.0.0.1"}

    def tearDown(self):
        self.work.cleanup()

    def run_role(self, role, entry, variables, check=False, success=True):
        play = [{"name": "ローカル API の安全性を検証する", "hosts": "localhost", "connection": "local",
                 "gather_facts": False, "vars": {"ansible_python_interpreter": sys.executable,
                 "ansible_pipelining": True, **variables}, "tasks": [
                     {"name": "模擬 API でロールを検証する", "ansible.builtin.include_role": {
                         "name": role, "tasks_from": entry}}]}]
        play_file = self.work_path / "play.yml"
        play_file.write_text(yaml.safe_dump(play, allow_unicode=True))
        args = ["ansible-playbook", "-i", "localhost,", str(play_file)]
        if check:
            args += ["--check", "--diff"]
        result = subprocess.run(args, env=self.env, capture_output=True, text=True, timeout=90)
        if success:
            self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-7000:])
        else:
            self.assertNotEqual(result.returncode, 0)
        return result.stdout + result.stderr

    def registry(self):
        result = subprocess.run(["ansible-vault", "view", str(self.key_file)], env=self.env,
                                capture_output=True, text=True, check=True)
        self.assertTrue(self.key_file.read_bytes().startswith(b"$ANSIBLE_VAULT;"))
        return yaml.safe_load(result.stdout)["vault_litellm_key_material"]

    def lifecycle(self, action, **kwargs):
        return self.run_role("k3s_litellm", "key_lifecycle", {
            "litellm_master_key": "sk-fake-master-for-local-tests",
            "litellm_management_url": self.url,
            "litellm_key_file": str(self.key_file),
            "litellm_key_name": "client", "litellm_key_action": action,
            "litellm_key_confirm": "client/" + action,
            "litellm_managed_keys": [{"name": "client", "settings": {"key_alias": "test", "models": ["model"]}}],
        }, **kwargs)

    def test_lifecycle_recovery_check_mode_idempotence_and_lock(self):
        self.lifecycle("create", check=True)
        self.assertFalse(self.key_file.exists())
        self.assertFalse(Path(str(self.key_file) + ".lock").exists())
        self.assertEqual(self.state["writes"], [])
        untouched = {"hash": "f" * 64, "settings": {"metadata": {"private": "preserve-me"}}}
        subprocess.run(["ansible-vault", "encrypt", "--output", str(self.key_file)],
                       input=yaml.safe_dump({"vault_litellm_key_material": {"untouched": untouched}}),
                       env=self.env, capture_output=True, text=True, check=True)
        self.state["fail_after_commit"] = True
        self.lifecycle("create", success=False)
        pending = self.registry()["client"]
        self.assertIn("pending_token", pending)
        self.assertEqual(len(self.state["writes"]), 1)
        output = self.lifecycle("create")
        active = self.registry()["client"]
        self.assertEqual(active["token"], pending["pending_token"])
        self.assertEqual(active["hash"], digest(active["token"]))
        self.assertNotIn("pending_token", active)
        self.assertNotIn(active["token"], output)
        self.assertNotIn(active["hash"], output)
        self.assertEqual(len(self.state["writes"]), 1)
        again = self.lifecycle("create")
        self.assertIn("changed=0", again)
        self.assertEqual(len(self.state["writes"]), 1)
        lock = Path(str(self.key_file) + ".lock")
        lock.mkdir()
        self.lifecycle("block", success=False)
        self.assertTrue(lock.exists())
        self.assertEqual(len(self.state["writes"]), 1)
        lock.rmdir()
        self.lifecycle("block")
        self.assertTrue(self.state["keys"][active["hash"]]["blocked"])
        ordinary = self.run_role("k3s_litellm", "manage", {
            "litellm_master_key": "sk-fake-master-for-local-tests", "litellm_management_url": self.url,
            "litellm_managed_models": [], "litellm_managed_keys": [
                {"name": "client", "settings": {"key_alias": "test", "models": ["model"]}}],
            "litellm_key_material": self.registry()})
        self.assertIn("changed=0", ordinary)
        self.assertTrue(self.state["keys"][active["hash"]]["blocked"])
        writes = len(self.state["writes"])
        self.assertIn("changed=0", self.lifecycle("block"))
        self.assertEqual(len(self.state["writes"]), writes)
        self.lifecycle("unblock")
        self.assertFalse(self.state["keys"][active["hash"]]["blocked"])
        self.state["fail_after_commit"] = True
        self.lifecycle("rotate", success=False)
        pending = self.registry()["client"]
        self.assertEqual(pending["hash"], active["hash"])
        self.assertIn("pending_token", pending)
        writes = len(self.state["writes"])
        self.lifecycle("rotate")
        rotated = self.registry()["client"]
        self.assertEqual(rotated["token"], pending["pending_token"])
        self.assertNotEqual(rotated["hash"], active["hash"])
        self.assertIn(active["hash"], self.state["keys"])
        self.assertFalse(self.state["keys"][active["hash"]]["blocked"])
        self.assertFalse(rotated["previous_retired"])
        self.assertEqual(len(self.state["writes"]), writes)
        self.lifecycle("rotate", success=False)
        self.assertEqual(len(self.state["writes"]), writes)
        self.lifecycle("retire")
        self.assertTrue(self.state["keys"][active["hash"]]["blocked"])
        self.assertFalse(self.state["keys"][rotated["hash"]]["blocked"])
        self.assertTrue(self.registry()["client"]["previous_retired"])
        writes = len(self.state["writes"])
        self.assertIn("changed=0", self.lifecycle("retire"))
        self.assertEqual(len(self.state["writes"]), writes)
        self.assertFalse(lock.exists())
        self.assertEqual(self.registry()["untouched"], untouched)

    def test_confirmation_failure_never_reads_api_or_writes_files(self):
        self.run_role("k3s_litellm", "key_lifecycle", {
            "litellm_master_key": "sk-fake-master-for-local-tests", "litellm_management_url": self.url,
            "litellm_key_file": str(self.key_file), "litellm_key_name": "client",
            "litellm_key_action": "create", "litellm_key_confirm": "wrong",
            "litellm_managed_keys": [{"name": "client", "settings": {"key_alias": "test", "models": []}}],
        }, success=False)
        self.assertEqual(self.state["reads"], [])
        self.assertEqual(self.state["writes"], [])
        self.assertFalse(self.key_file.exists())
        self.assertFalse(Path(str(self.key_file) + ".lock").exists())

    def test_manage_rejects_duplicate_key_hash_before_api_access(self):
        output = self.run_role("k3s_litellm", "manage", {
            "litellm_master_key": "sk-fake-master-for-local-tests", "litellm_management_url": self.url,
            "litellm_managed_models": [], "litellm_managed_keys": [
                {"name": "first", "settings": {"rpm_limit": 10}},
                {"name": "second", "settings": {"rpm_limit": 20}}],
            "litellm_key_material": {"first": {"hash": "a" * 64}, "second": {"hash": "a" * 64}},
        }, success=False)
        self.assertEqual(self.state["reads"], [])
        self.assertEqual(self.state["writes"], [])
        self.assertNotIn("a" * 64, output)

    def test_manage_routing_groups_check_apply_and_idempotence(self):
        self.state["routing_groups"] = [
            {"group_name": "ui-only", "models": ["x"], "routing_strategy": "priority"},
            {"group_name": "tier", "models": ["a"], "routing_strategy": "simple-shuffle",
             "routing_strategy_args": None}]
        variables = {
            "litellm_master_key": "sk-fake-master-for-local-tests", "litellm_management_url": self.url,
            "litellm_managed_models": [], "litellm_managed_keys": [], "litellm_key_material": {},
            "litellm_managed_routing_groups": [
                {"group_name": "tier", "models": ["a", "b"], "routing_strategy": "simple-shuffle"}]}
        self.run_role("k3s_litellm", "manage", variables, check=True)
        self.assertEqual(self.state["writes"], [])
        self.run_role("k3s_litellm", "manage", variables)
        self.assertEqual([path for path, _ in self.state["writes"]], ["/config/update"])
        self.assertEqual(self.state["routing_groups"], [
            {"group_name": "ui-only", "models": ["x"], "routing_strategy": "priority"},
            {"group_name": "tier", "models": ["a", "b"], "routing_strategy": "simple-shuffle"}])
        self.assertIn("changed=0", self.run_role("k3s_litellm", "manage", variables))
        self.assertEqual(len(self.state["writes"]), 1)

    def test_manage_fallbacks_merge_declared_and_keep_others(self):
        self.state["routing_groups"] = [
            {"group_name": name, "models": [name], "routing_strategy": "priority"} for name in ("a", "b", "c")]
        self.state["fallbacks"] = [{"c": ["a"]}, {"a": ["c"]}]
        variables = {
            "litellm_master_key": "sk-fake-master-for-local-tests", "litellm_management_url": self.url,
            "litellm_managed_models": [], "litellm_managed_keys": [], "litellm_key_material": {},
            "litellm_managed_fallbacks": [{"a": ["b", "c"]}, {"b": ["a"]}]}
        self.run_role("k3s_litellm", "manage", variables, check=True)
        self.assertEqual(self.state["writes"], [])
        self.run_role("k3s_litellm", "manage", variables)
        self.assertEqual(self.state["writes"], [
            ("/config/update", {"router_settings": {"fallbacks": [{"c": ["a"]}, {"a": ["b", "c"]}, {"b": ["a"]}]}})])
        self.assertEqual(len(self.state["routing_groups"]), 3)
        self.assertIn("changed=0", self.run_role("k3s_litellm", "manage", variables))
        self.assertEqual(len(self.state["writes"]), 1)

    def test_export_refuses_to_overwrite_key_registry(self):
        self.lifecycle("create")
        encrypted_before = self.key_file.read_bytes()
        reads_before = len(self.state["reads"])
        self.run_role("k3s_litellm", "export", {
            "litellm_master_key": "sk-fake-master-for-local-tests", "litellm_management_url": self.url,
            "litellm_export_file": str(self.key_file), "litellm_export_overwrite": True,
        }, success=False)
        self.run_role("k3s_authentik", "export", {
            "authentik_api_token": "fake-token", "authentik_host": "auth.example.test",
            "authentik_management_url": self.url, "authentik_export_file": str(self.key_file),
            "authentik_export_overwrite": True,
        }, success=False)
        self.assertEqual(self.key_file.read_bytes(), encrypted_before)
        self.assertEqual(len(self.state["reads"]), reads_before)
        self.assertEqual(len(self.state["writes"]), 1)

    def test_snapshot_exports_are_idempotent_and_reject_templates(self):
        cases = [
            ("k3s_litellm", "litellm", {"litellm_master_key": "fake-token", "litellm_management_url": self.url}),
            ("k3s_authentik", "authentik", {"authentik_api_token": "fake-token",
             "authentik_host": "auth.example.test", "authentik_management_url": self.url}),
        ]
        for role, prefix, variables in cases:
            snapshot = self.work_path / (prefix + "_snapshot.yml")
            variables = {**variables, prefix + "_export_file": str(snapshot), prefix + "_export_overwrite": True}
            self.run_role(role, "export", variables)
            encrypted_before = snapshot.read_bytes()
            self.assertTrue(encrypted_before.startswith(b"$ANSIBLE_VAULT;"))
            self.assertIn("changed=0", self.run_role(role, "export", variables))
            self.assertEqual(snapshot.read_bytes(), encrypted_before)
            self.assertEqual(self.state["writes"], [])
        self.state["apps"] = [{"slug": "app", "name": "{{ 7 * 7 }}"}]
        before = (self.work_path / "authentik_snapshot.yml").read_bytes()
        self.run_role("k3s_authentik", "export", {
            "authentik_api_token": "fake-token", "authentik_host": "auth.example.test",
            "authentik_management_url": self.url,
            "authentik_export_file": str(self.work_path / "authentik_snapshot.yml"),
            "authentik_export_overwrite": True,
        }, success=False)
        self.assertEqual((self.work_path / "authentik_snapshot.yml").read_bytes(), before)

    def test_authentik_pagination_and_patch_preserve_authorization(self):
        self.state["apps"] = [{"slug": "app" + str(i), "name": "old", "provider": 42,
                                "policy_engine_mode": "all"} for i in range(101)]
        variables = {"authentik_management_url": self.url, "authentik_host": "auth.example.test",
                     "authentik_api_token": "fake-token", "authentik_managed_applications": [
                         {"slug": "app100", "settings": {"name": "new"}}]}
        self.run_role("k3s_authentik", "manage", variables, check=True)
        self.assertEqual(self.state["writes"], [])
        self.assertEqual(self.state["apps"][100]["name"], "old")
        self.run_role("k3s_authentik", "manage", variables)
        self.assertEqual(self.state["writes"], [("/api/v3/core/applications/app100/", {"name": "new"})])
        self.assertEqual(self.state["apps"][100]["provider"], 42)
        self.assertEqual(self.state["apps"][100]["policy_engine_mode"], "all")
        self.assertTrue(any("page=2" in path for path in self.state["reads"]))
        self.assertIn("changed=0", self.run_role("k3s_authentik", "manage", variables))
        self.assertEqual(len(self.state["writes"]), 1)


if __name__ == "__main__":
    unittest.main()
