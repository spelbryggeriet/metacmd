#!/usr/bin/env python3

from get_version import get_version as get_current_version
import datetime
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_DIR = os.path.realpath(os.path.join(SCRIPT_DIR, "../.."))

sys.path.append(f"{SCRIPT_DIR}/..")
from util import error, parse_commit_msg, run


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


def parse_git_history():
    versions, _ = run("git", "-C", REPO_DIR, "tag", "--sort", "v:refname")
    prev_versions = [None, *versions.splitlines()]
    next_versions = [*versions.splitlines(), None]

    releases = []
    for prev_version, next_version in zip(prev_versions, next_versions):
        to_ref = next_version or "HEAD"

        if prev_version is not None:
            refs, _ = run("git", "-C", REPO_DIR, "rev-list", f"{prev_version}..{to_ref}")
        else:
            refs, _ = run("git", "-C", REPO_DIR, "rev-list", f"{to_ref}")

        bump_comp_idx = 2
        release = {"version": next_version, "groups": {}}
        for ref in refs.splitlines():
            message, _ = run("git", "-C", REPO_DIR, "log", "--format=%B", "-1", ref)

            change = parse_commit_msg(message)
            if change is None:
                continue

            group_name = change["group"]
            if group_name not in release["groups"]:
                release["groups"][group_name] = {"unscoped": [], "scopes": {}} 
            group = release["groups"][group_name]

            if "scope" not in change:
                scope = group["unscoped"]
            else:
                scope_name = change["scope"]
                if change["scope"] not in group["scopes"]:
                    group["scopes"][scope_name] = []
                scope = group["scopes"][scope_name]
            scope.append(change)

            if change["is_breaking_change"]:
                bump_comp_idx = 0
            elif change["type"] == "feat" and bump_comp_idx > 1:
                bump_comp_idx = 1

        release["groups"] = {i: v for i, v in sorted(release["groups"].items())}
        for group in release["groups"].values():
            group["scopes"] = {i: v for i, v in sorted(group["scopes"].items())}

        if release["version"] is None:
            release["version"] = get_next_version(bump_comp_idx, get_current_version())

        releases.append(release)

    return releases


def update_version_file(new_version, path):
    version_path = os.path.join(REPO_DIR, path)
    with open(version_path, "w") as f:
        f.write(new_version)


def update_manifest(new_version, path, current_version):
    manifest_path = os.path.join(REPO_DIR, path)
    with open(manifest_path, "r") as f:
        content = f.read()

    new_content = re.sub(f'^(\[package\]\n(?:\w+ = .*\n)*?version = "){current_version}', f"\g<1>{new_version}", content, count=1)
    if new_content == content:
        error(f"Failed to find version field in {path}")

    with open(manifest_path, "w") as f:
        f.write(new_content)


def update_changelog(releases, path):
    changelog = (
        "# Changelog\n\n"
        "All notable changes to this project will be documented in this file.\n\n"
        "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project\n"
        "adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)."
    )

    for release in reversed(releases):
        if release["version"] == releases[-1]["version"]:
            date = datetime.datetime.now(datetime.timezone.utc)
        else:
            raw_date, _ = run("git", "-C", REPO_DIR, "log", "-1", release["version"], "--format=%ci")
            date = datetime.datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S %z")

        formatted_date = date.strftime("%Y-%m-%d")
        changelog += "\n\n## [%s] - %s" % (
            release["version"][1:] if release["version"].startswith("v") else release["version"], 
            formatted_date,
        )

        for group_name, group in release["groups"].items():
            changelog += f"\n\n### {group_name}\n"

            changes = [*reversed(group["unscoped"]), *[change for scope in group["scopes"].values() 
                                                              for change in reversed(scope)]]
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
    releases = parse_git_history()

    current_version = get_current_version()
    new_version = releases[-1]["version"]

    if not dry_run:
        update_version_file(new_version, "VERSION")
        update_manifest(new_version, "Cargo.toml", current_version)
        update_changelog(releases, "CHANGELOG.md")

    return new_version


if __name__ == "__main__":
    dry_run = False
    if len(sys.argv) >= 2 and sys.argv[1] in ["-d", "--dry-run"]:
        dry_run = True

    print(bump_version(dry_run))
