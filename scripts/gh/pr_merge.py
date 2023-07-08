#!/usr/bin/env python3

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

sys.path.append(f"{SCRIPT_DIR}/..")
from util import error, parse_commit_msg, run


def pr_merge(msg):
    parse_commit_msg(msg)

    msg_lines = msg.splitlines()
    title = msg_lines[0];
    body = "\n".join(msg_lines[2..])

    run("gh", "pr", "merge", "--squash", f"--subject={subject}", f"--body={body}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        error("Commit message argument missing")

    pr_merge(sys.argv[1])
