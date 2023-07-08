#!/usr/bin/env python3

import os
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_DIR = os.path.realpath(os.path.join(SCRIPT_DIR, "../.."))

sys.path.append(f"{SCRIPT_DIR}/..")
from util import eprint, error, parse_commit_msg, run


def pr_merge(should_squash=False):
    output, _ = run("git", "-C", REPO_DIR, "status", "-s")
    if len(output.strip()) > 0:
        error(f"uncommited changes:\n{output}")

    if should_squash:
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

        parse_commit_msg(msg)

        run("git", "-C", REPO_DIR, "reset", "--soft", "main", capture_output=False)
        run("git", "-C", REPO_DIR, "commit", "-m", msg, capture_output=False)
        run("git", "-C", REPO_DIR, "push", "--force-with-lease", capture_output=False)

    refs, _ = run("git", "-C", REPO_DIR, "rev-list", "main..HEAD")

    for ref in refs.splitlines():
        msg, _ = run("git", "-C", REPO_DIR, "log", "--format=%B", "-1", ref)
        parse_commit_msg(msg)

    source_branch, _ = run("git", "-C", REPO_DIR, "branch", "--show-current")
    run("git", "-C", REPO_DIR, "checkout", "main", capture_output=False)
    run("git", "-C", REPO_DIR, "merge", source_branch, "--ff-only", capture_output=False)
    run("git", "-C", REPO_DIR, "push", capture_output=False)
    run("git", "-C", REPO_DIR, "branch", "--delete", source_branch, capture_output=False)
    run("git", "-C", REPO_DIR, "push", "origin", "--delete", source_branch, capture_output=False)


if __name__ == "__main__":
    should_squash = False
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if arg == "--squash":
            should_squash = True
        elif arg.startswith("-"):
            error(f"unknown flag: {arg}")
        else:
            error(f"unexpected argument: {arg}")

        if len(sys.argv) > 2:
            error(f"unexpected extra arguments: {' '.join(sys.argv[2:])}")

    pr_merge(should_squash)
