#!/usr/bin/env python3
"""Claude Code の Bash ツールの PreToolUse フック。実機を変えうるコマンドの前に、オーナーの確認を求める。

AGENTS.md では、実機を変える実行は、オーナーが会話で頼んだときだけ行う。このフックはその規則の保険で、
規則の代わりではない。コマンドの文字列だけを読むため、スクリプトの中から呼ぶものや、ssh・curl での直接の操作は見えない。

確認を求めるもの(読み取りとして挙げたもの以外はすべて。解析できないコマンドも確認に倒す):
- ansible-playbook: --syntax-check・--list-*、playbooks/k3s/ の --check(AGENTS.md の「Always allowed」)を除く
- ansible のアドホック実行: ping・setup のモジュールを除く。ansible-pull・ansible-console
- kubectl・helm: 読み取りのサブコマンド、--help、client・server の dry-run を除く
"""
import json
import os
import re
import shlex
import sys

TOOLS = ("ansible-playbook", "ansible-pull", "ansible-console", "ansible", "kubectl", "helm")
KEYWORD = re.compile(r"(?<![\w.-])(?:%s)(?![\w.-])" % "|".join(map(re.escape, TOOLS)))
NAME = r"[A-Za-z_][A-Za-z0-9_]*"
ASSIGNMENT = re.compile(r"^(%s)=(.*)$" % NAME, re.S)
VARIABLE = re.compile(r"^\$(?:(%s)|\{(%s)\})$" % (NAME, NAME))
REFERENCE = re.compile(r"\$(?:(%s)|\{(%s)\})" % (NAME, NAME))
PLACEHOLDER = "__substitution__"
OPERATORS = ";&|()<>\n"
MAX_DEPTH = 8

# 文字列をコマンドとして動かすもの(シェル・リモートシェル・端末の多重化)
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "eval", "ssh", "su", "script", "watch", "tmux", "screen"}
# 引数の並びの途中から、別のプログラムを動かすもの
WRAPPERS = {
    "sudo", "doas", "env", "timeout", "nice", "nohup", "stdbuf", "time", "command", "builtin", "exec", "xargs",
    "setsid", "flock", "chroot", "nsenter", "ionice", "taskset", "unbuffer", "parallel", "find", "k3s", "uv", "uvx",
    "pipx", "runuser", "systemd-run",
}
LAUNCHERS = SHELLS | WRAPPERS
RESERVED = {"{", "}", "!", "if", "then", "else", "elif", "fi", "do", "done", "while", "until"}
DECLARATIONS = {"export", "declare", "local", "readonly", "typeset"}
# ヒアドキュメントの本文はデータとして読み飛ばす。シェルへ渡す行の本文だけをコマンドとして読む
HEREDOC = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z0-9_.-]+)\1")
SHELL_FED = re.compile(r"(?<![\w.-])(?:bash|sh|zsh|dash|ksh|ssh|eval|su|sudo)(?![\w.-])")
HELP = {"-h", "--help"}

KUBECTL_VALUE_FLAGS = {
    "-n", "--namespace", "-s", "--server", "--token", "--certificate-authority", "--client-certificate",
    "--client-key", "--context", "--cluster", "--user", "--kubeconfig", "--as", "--as-group", "--as-uid",
    "--request-timeout", "--tls-server-name", "--cache-dir", "-v", "--v", "--vmodule", "--log-file", "--profile",
    "--profile-output", "--username", "--password", "-o", "--output", "-l", "--selector", "-f", "--filename",
    "-c", "--container", "--field-selector", "--sort-by", "--since", "--tail", "--template",
}
KUBECTL_READ = {
    "get", "describe", "logs", "top", "explain", "api-resources", "api-versions", "version", "cluster-info",
    "events", "diff", "wait", "completion", "options", "help", "kustomize",
}
KUBECTL_READ_SUB = {
    "auth": {"can-i", "whoami"},
    "rollout": {"status", "history"},
    "config": {"view", "get-contexts", "get-clusters", "get-users", "current-context"},
    "plugin": {"list"},
}
KUBECTL_DRY_RUN_VERBS = {
    "apply", "create", "delete", "patch", "replace", "label", "annotate", "set", "scale", "expose", "run",
    "autoscale", "taint", "drain", "cordon", "uncordon",
}
KUBECTL_DRY_RUNS = {"--dry-run=client", "--dry-run=server"}

HELM_VALUE_FLAGS = {
    "-n", "--namespace", "--kube-apiserver", "--kube-token", "--kube-ca-file", "--kube-context", "--kubeconfig",
    "--kube-as-user", "--kube-as-group", "--kube-tls-server-name", "--registry-config", "--repository-cache",
    "--repository-config", "--burst-limit", "--qps", "--content-cache", "-o", "--output", "-f", "--values",
    "--set", "--set-string", "--set-file", "--set-json", "--set-literal", "--version", "--max", "--timeout",
    "--revision", "--repo", "--post-renderer",
}
HELM_READ = {
    "list", "ls", "status", "get", "history", "hist", "show", "inspect", "template", "lint", "search", "version",
    "env", "help", "completion", "verify", "pull", "fetch", "package", "diff",
}
HELM_READ_SUB = {
    "repo": {"list", "ls"},
    "plugin": {"list", "ls"},
    "dependency": {"list", "ls"},
    "dep": {"list", "ls"},
}
HELM_DRY_RUN_VERBS = {"install", "upgrade", "uninstall", "delete", "del", "un", "rollback"}
HELM_DRY_RUNS = {"--dry-run", "--dry-run=client", "--dry-run=server", "--dry-run=true"}

PLAYBOOK_VALUE_FLAGS = {
    "-i", "--inventory", "--inventory-file", "-e", "--extra-vars", "-l", "--limit", "-t", "--tags", "--skip-tags",
    "-u", "--user", "-f", "--forks", "-M", "--module-path", "--vault-id", "--vault-password-file",
    "--vault-pass-file", "--private-key", "--key-file", "-c", "--connection", "-T", "--timeout",
    "--ssh-common-args", "--sftp-extra-args", "--scp-extra-args", "--ssh-extra-args", "--start-at-task",
    "--become-method", "--become-user", "--become-password-file", "--connection-password-file",
}
PLAYBOOK_NO_RUN = {"--syntax-check", "--list-tasks", "--list-hosts", "--list-tags", "--version"} | HELP
CHECKABLE_PLAYBOOK = re.compile(r"(?:^|/)playbooks/k3s/[^/]+\.ya?ml$")
CHECK_FLAG = re.compile(r"^-[A-Za-z]*C[A-Za-z]*$")
ADHOC_NO_RUN = {"--version", "--list-hosts"} | HELP
ADHOC_VALUE_FLAGS = PLAYBOOK_VALUE_FLAGS | {
    "-m", "--module-name", "-a", "--args", "-B", "--background", "-P", "--poll", "--playbook-dir", "--task-timeout",
}
ADHOC_READ_MODULES = {"ping", "setup", "ansible.builtin.ping", "ansible.builtin.setup"}


def strip_heredocs(text):
    """シェルへ渡さないヒアドキュメントの本文を除く。"""
    lines, pending, dropped = [], [], []
    for line in text.split("\n"):
        if pending:
            delimiter, keep = pending[0]
            if line.strip() == delimiter:
                pending.pop(0)
                dropped = []
            elif keep:
                lines.append(line)
            else:
                dropped.append(line)
            continue
        lines.append(line)
        for match in HEREDOC.finditer(line):
            pending.append((match.group(2), bool(SHELL_FED.search(line[:match.start()]))))
    if pending:
        # 終わりの行が無いものはヒアドキュメントと見なさず、残りもコマンドとして読む
        lines += dropped
    return "\n".join(lines)


def take_substitutions(text):
    """$(...)・<(...)・>(...)・`...` を目印に置き換え、その中身を返す(中身も別にコマンドとして読むため)。

    単一引用符の中は、シェルと同じく置換と見なさない。
    """
    out, inner, i, quote = [], [], 0, None
    while i < len(text):
        if quote == "'":
            quote = None if text[i] == "'" else quote
            out.append(text[i])
            i += 1
        elif text[i] == "\\":
            out.append(text[i:i + 2])
            i += 2
        elif text[i] == "'" and quote is None or text[i] == '"':
            quote = None if quote == text[i] else text[i]
            out.append(text[i])
            i += 1
        elif text[i] == "`":
            end = text.find("`", i + 1)
            if end < 0:
                raise ValueError("閉じていないバッククォート")
            inner.append(text[i + 1:end])
            out.append(PLACEHOLDER)
            i = end + 1
        elif text[i] in "$<>" and text.startswith("(", i + 1):
            depth, j = 0, i + 1
            while j < len(text):
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            else:
                raise ValueError("閉じていないコマンド置換")
            inner.append(text[i + 2:j])
            out.append(PLACEHOLDER)
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out), inner


def simple_commands(text):
    """演算子(; & | ( ) < > 改行)で区切った、単純なコマンドの語の並びを返す。"""
    lexer = shlex.shlex(text, posix=True, punctuation_chars=OPERATORS)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    commands, words, redirect_target = [], [], False
    for token in lexer:
        if token and set(token) <= set(OPERATORS):
            if set(token) <= set("<>&") and set(token) & set("<>"):
                # リダイレクトはコマンドを区切らない。前のファイル記述子の番号と、後ろの宛先は引数ではない
                if words and words[-1].isdigit():
                    words.pop()
                redirect_target = True
                continue
            if words:
                commands.append(words)
            words, redirect_target = [], False
        elif redirect_target:
            redirect_target = False
        else:
            words.append(token)
    if words:
        commands.append(words)
    return commands


def expand(word, variables):
    """語の中の $NAME・${NAME} を展開する。展開できない参照や、置換の目印が残れば None。"""
    missing = []

    def value(match):
        name = match.group(1) or match.group(2)
        found = variables.get(name, os.environ.get(name))
        if found is None:
            missing.append(name)
            return ""
        return found

    result = REFERENCE.sub(value, word)
    if missing or "$" in result or "`" in result or PLACEHOLDER in result:
        return None
    return result


def before_separator(args):
    return args[:args.index("--")] if "--" in args else args


def positional(args, value_flags):
    """フラグとフラグの値を除いた引数を返す(-- より前だけ)。"""
    result, skip = [], False
    for arg in before_separator(args):
        if skip:
            skip = False
        elif arg.startswith("-") and arg != "-":
            skip = arg in value_flags
        else:
            result.append(arg)
    return result


def check_kubectl(args):
    head = set(before_separator(args))
    words = positional(args, KUBECTL_VALUE_FLAGS)
    if head & HELP or not words:
        return []
    verb = words[0]
    if verb in KUBECTL_READ:
        return []
    if len(words) > 1 and words[1] in KUBECTL_READ_SUB.get(verb, ()):
        return []
    if verb in KUBECTL_DRY_RUN_VERBS and head & KUBECTL_DRY_RUNS:
        return []
    return ["kubectl " + " ".join(words[:2])]


def check_helm(args):
    head = set(before_separator(args))
    words = positional(args, HELM_VALUE_FLAGS)
    if head & HELP or not words:
        return []
    verb = words[0]
    if verb in HELM_READ:
        return []
    if len(words) > 1 and words[1] in HELM_READ_SUB.get(verb, ()):
        return []
    if verb in HELM_DRY_RUN_VERBS and head & HELM_DRY_RUNS:
        return []
    return ["helm " + " ".join(words[:2])]


def check_playbook(args):
    playbooks = positional(args, PLAYBOOK_VALUE_FLAGS)
    if set(args) & PLAYBOOK_NO_RUN or not playbooks:
        return []
    check = any(arg == "--check" or CHECK_FLAG.match(arg) for arg in args)
    if check and playbooks and all(CHECKABLE_PLAYBOOK.search(os.path.normpath(p)) for p in playbooks):
        return []
    return ["ansible-playbook " + " ".join(playbooks) + (" --check" if check else "")]


def check_adhoc(args):
    if set(args) & ADHOC_NO_RUN or not positional(args, ADHOC_VALUE_FLAGS):
        return []
    module = "command"
    for i, arg in enumerate(args):
        if arg in ("-m", "--module-name") and i + 1 < len(args):
            module = args[i + 1]
        elif arg.startswith("--module-name="):
            module = arg.split("=", 1)[1]
        elif arg.startswith("-m") and len(arg) > 2:
            module = arg[2:]
    if module in ADHOC_READ_MODULES:
        return []
    return ["ansible -m " + module]


def check_program(words, variables, depth):
    name = os.path.basename(words[0])
    args = words[1:]
    if name == "kubectl":
        return check_kubectl(args)
    if name == "helm":
        return check_helm(args)
    if name == "ansible-playbook":
        return check_playbook(args)
    if name == "ansible":
        return check_adhoc(args)
    if name in ("ansible-pull", "ansible-console"):
        return [] if set(args) & ({"--version"} | HELP) else [name]
    if name not in LAUNCHERS or name == "command" and args[:1] in (["-v"], ["-V"]):
        return []
    reasons = []
    # 起動するプログラムの位置は、ラッパーごとのオプションで変わるため、最初に現れる対象のツールかラッパーから読む
    for i, arg in enumerate(args):
        if os.path.basename(arg) in TOOLS or os.path.basename(arg) in LAUNCHERS:
            reasons += check_program(args[i:], variables, depth)
            break
    if name in SHELLS:
        for arg in args:
            if any(c.isspace() for c in arg) and (KEYWORD.search(arg) or "$" in arg or PLACEHOLDER in arg):
                reasons += analyse(arg, dict(variables), depth + 1)
    return reasons


def check_words(words, variables, depth):
    words = list(words)
    while words:
        assignment = ASSIGNMENT.match(words[0])
        if assignment:
            variables[assignment.group(1)] = assignment.group(2)
        elif words[0] not in RESERVED:
            break
        words.pop(0)
    if not words:
        return []
    if words[0] in DECLARATIONS:
        for word in words[1:]:
            assignment = ASSIGNMENT.match(word)
            if assignment:
                variables[assignment.group(1)] = assignment.group(2)
        return []
    whole = VARIABLE.match(words[0])
    if whole:
        name = whole.group(1) or whole.group(2)
        value = variables.get(name, os.environ.get(name))
        if value is not None:
            # 変数ひとつがプログラムと引数をまとめて持つことがあるため、値をコマンドとして読み直す
            return analyse(value + " " + " ".join(shlex.quote(w) for w in words[1:]), variables, depth + 1)
    program = expand(words[0], variables)
    if program is None:
        return ["実行するプログラムが変数で決まるコマンド(%s)" % words[0].replace(PLACEHOLDER, "$(…)")]
    words[0] = program
    return check_program(words, variables, depth)


def analyse(text, variables, depth):
    """確認が要る理由の一覧を返す。空なら確認は要らない。"""
    if depth > MAX_DEPTH:
        return ["入れ子が深く、判定できないコマンド"]
    text, inner = take_substitutions(strip_heredocs(text.replace("\\\n", " ")))
    reasons = []
    for part in inner:
        reasons += analyse(part, dict(variables), depth + 1)
    for words in simple_commands(text):
        reasons += check_words(words, variables, depth)
    return reasons


def ask(reasons):
    text = (
        "確認が要るコマンドです: %s。AGENTS.md の規則で、実機を変える実行は、オーナーが頼んだときだけ行います。"
        % "、".join(dict.fromkeys(reasons))
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": text,
        },
    }, ensure_ascii=False))


def main():
    try:
        event = json.load(sys.stdin)
        if event.get("tool_name") != "Bash":
            return
        command = event["tool_input"]["command"]
    except (ValueError, KeyError, TypeError, AttributeError):
        ask(["フックへの入力を読めず、判定できないコマンド"])
        return
    if not isinstance(command, str) or not KEYWORD.search(command):
        return
    try:
        reasons = analyse(command, {}, 0)
    except Exception as error:  # 解析の失敗は確認に倒す
        reasons = ["解析できないコマンド(%s)" % type(error).__name__]
    if reasons:
        ask(reasons)


if __name__ == "__main__":
    main()
