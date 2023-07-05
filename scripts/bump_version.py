#!/usr/bin/env python3

from get_version import get_version as get_current_version
from util import error
import datetime
import os
import re
import subprocess
import sys


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_DIR = os.path.realpath(os.path.join(SCRIPT_DIR, ".."))


def run(*cmd):
    output = subprocess.run(cmd, capture_output=True)
    return output.stdout.decode("utf-8").strip(), output.stderr.decode("utf-8").strip()


def get_next_version(bump_comp_idx, current_version):
    components = current_version.split(".")

    all_digits = lambda c: all(map(str.isdigit, c))
    is_empty = lambda c: len(c) == 0
    is_int = lambda c: not is_empty(c) and all_digits(c)

    has_three_components = len(components) == 3
    all_components_are_ints = all(map(is_int, components))

    if not (has_three_components and all_components_are_ints):
        error(f'"{version}" version number invalid')

    components[bump_comp_idx] = int(components[bump_comp_idx]) + 1
    [major, minor, patch] = [*components[:bump_comp_idx+1], 0, 0, 0][:3]

    return f"{major}.{minor}.{patch}"


def update_version_file(new_version, path):
    version_path = os.path.join(REPO_DIR, path)
    with open(version_path, "w") as f:
        f.write(new_version)


def parse_git_history():
    versions, _ = run("git", "-C", REPO_DIR, "tag", "--sort", "v:refname")
    prev_versions = [None, *versions.splitlines()]
    next_versions = [*versions.splitlines(), None]

    contexts = []
    for prev_version, next_version in zip(prev_versions, next_versions):
        to_ref = next_version or "head"

        if prev_version is not None:
            refs, _ = run("git", "-C", REPO_DIR, "rev-list", f"{prev_version}..{to_ref}")
        else:
            refs, _ = run("git", "-C", REPO_DIR, "rev-list", f"{to_ref}")

        bump_comp_idx = 2
        context = {"version": next_version, "groups": {}}
        for ref in refs.splitlines():
            message, _ = run("git", "-C", REPO_DIR, "log", "--format=%B", "-n", "1", ref)

            regex = (
                "^(?P<type>feat|fix)(\((?P<scope>[^)]+)\))?(?P<is_breaking>!)?: "
                "(?P<desc>(?P<group>[a-z]+) [^\n.]+)"
                "(\n\n(?P<body>[\s\S]+))?$"
            )
            match = re.match(regex, message)
            if match is None:
                error(f'Failed parsing: "{message}"')

            type = match.group("type")
            scope = match.group("scope")
            is_breaking = match.group("is_breaking") is not None
            group = match.group("group")
            desc = match.group("desc")
            body = match.group("body")
            breaking_desc = None

            if body is not None:
                body_regex = (
                    "^((?P<body>[\s\S]+?)\n\n)?"
                    "BREAKING[ -]CHANGE: (?P<breaking_desc>[\s\S]+)$"
                )
                match = re.match(body_regex, body)
                if match is not None:
                    body = match.group("body")
                    breaking_desc = match.group("breaking_desc")

                whitespace_regex = " *\n *"
                if body is not None:
                    body = re.sub(whitespace_regex, " ", body)
                if breaking_desc is not None:
                    breaking_desc = re.sub(whitespace_regex, " ", breaking_desc)

            if group in ["add", "support"]:
                group = "Added"
            elif group in ["remove", "delete"]:
                group = "Removed"
            elif group == "fix" or type == "fix":
                group = "Fixed"
            else:
                group = "Changed"

            if group not in context["groups"]:
                context["groups"][group] = []

            obj = {
                "description": "%c%s." % (desc[0].upper(), desc[1:]),
                "is_breaking_change": is_breaking or breaking_desc is not None,
            }
            if scope is not None:
                obj["scope"] = scope
            if body is not None:
                obj["long_description"] = "%c%s" % (body[0].upper(), body[1:])
                if body[-1] != ".":
                    obj["long_description"] += "."
            if breaking_desc is not None:
                obj["breaking_change_description"] = "%c%s" % (breaking_desc[0].upper(), breaking_desc[1:])
                if breaking_desc[-1] != ".":
                    obj["breaking_change_description"] += "."
            context["groups"][group].append(obj)

            if obj["is_breaking_change"]:
                bump_comp_idx = 0
            elif type == "feat" and bump_comp_idx > 1:
                bump_comp_idx = 1

        if context["version"] is None:
            context["version"] = get_next_version(bump_comp_idx, get_current_version())

        contexts.append(context)

    return contexts


def update_changelog(contexts, path):
    changelog = (
        "# Changelog\n\n"
        "All notable changes to this project will be documented in this file.\n\n"
        "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project\n"
        "adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)."
    )

    for context in reversed(contexts):
        if context["version"] == contexts[-1]["version"]:
            date = datetime.datetime.now(datetime.timezone.utc)
        else:
            raw_date, _ = run("git", "-C", REPO_DIR, "show", context["version"], "--format=%ci")
            date = datetime.datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S %z")
            
        formatted_date = date.strftime("%Y-%m-%d")
        changelog += "\n\n## [%s] - %s" % (context["version"], formatted_date)

        for group, changes in context["groups"].items():
            changelog += f"\n\n### {group}\n"

            for change in changes:
                changelog += "\n- "
                if "scope" in change:
                    changelog += "(%s) " % change["scope"]
                changelog += "%s" % change["description"]
                if "long_description" in change:
                    changelog += " %s" % change["long_description"]
                if change["is_breaking_change"]:
                    changelog += " **BREAKING CHANGE**"
                    if "breaking_change_description" in change:
                        changelog += ": %s" % change["breaking_change_description"]

    changelog_path = os.path.join(REPO_DIR, path)
    with open(changelog_path, "w") as f:
        f.write(changelog)


def bump_version(dry_run):
    contexts = parse_git_history()

    new_version = contexts[-1]["version"]

    if not dry_run:
        update_version_file(new_version, "VERSION")
        update_changelog(contexts, "CHANGELOG.md")

    return new_version


if __name__ == "__main__":
    dry_run = False
    if len(sys.argv) >= 2 and sys.argv[1] in ["-d", "--dry-run"]:
        dry_run = True

    print(bump_version(dry_run))
