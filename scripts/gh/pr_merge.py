#!/usr/bin/env python3

import os
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_DIR = os.path.realpath(os.path.join(SCRIPT_DIR, "../.."))

sys.path.append(f"{SCRIPT_DIR}/..")
from util import eprint, error, parse_commit_msg, run


def pr_merge_squash():
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


def pr_merge_ff():
    refs, _ = run("git", "-C", REPO_DIR, "rev-list", "main..HEAD")

    for ref in refs.splitlines():
        msg, _ = run("git", "-C", REPO_DIR, "log", "--format=%B", "-1", ref)
        parse_commit_msg(msg)

    source_branch, _ = run("git", "-C", REPO_DIR, "branch", "--show-current")
    run("git", "-C", REPO_DIR, "checkout", "main", capture_output=False)
    run("git", "-C", REPO_DIR, "merge", source_branch, "--ff-only", capture_output=False)
    run("git", "-C", REPO_DIR, "push", capture_output=False)


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if arg == "--squash":
            should_squash = True
        elif arg == "--ff":
            should_squash = False
        elif arg.startswith("-"):
            error(f"unknown flag: {arg}")
        else:
            error(f"unexpected argument: {arg}")

        if len(sys.argv) > 2:
            error(f"unexpected extra arguments: {' '.join(sys.argv[2:])}")
    else:
        error("expected either `--squash` flag or `--ff` flag")

    if should_squash:
        pr_merge_squash()
    else:
        pr_merge_ff()
