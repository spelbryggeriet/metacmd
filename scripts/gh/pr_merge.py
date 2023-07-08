#!/usr/bin/env python3

import os
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_DIR = os.path.realpath(os.path.join(SCRIPT_DIR, "../.."))

sys.path.append(f"{SCRIPT_DIR}/..")
from util import eprint, parse_commit_msg, run


def pr_merge(msg=None):
    if msg is None:
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "gh-pr-msg")

            with open(path, "wb") as file:
                output, _ = run("git", "-C", REPO_DIR, "log", "--format=* %s%n%b", "main..HEAD")
                file.write(bytes("\n# ".join(["\n", *output.splitlines()]), "utf-8"))
                file.flush()

            run(os.environ.get("EDITOR", "vim"), path, capture_output=False)

            with open(path, "rb") as file:
                msg = file.read().decode("utf-8").strip()

    msg = "\n".join(filter(
        lambda line: not line.startswith("#"),
        map(lambda line: line.strip(), msg.splitlines())))
    msg = msg.strip()

    if len(msg) == 0:
        eprint("Empty commit message, aborting")
        return

    parse_commit_msg(msg)

    msg_lines = msg.splitlines()
    subject = msg_lines[0]
    body = "\n".join(msg_lines[2:])

    run("gh", "pr", "merge",
        "--squash", "--delete-branch",
        f"--subject={subject}", f"--body={body}",
        capture_output=False)


if __name__ == "__main__":
    pr_merge(sys.argv[1] if len(sys.argv) >= 2 else None)
