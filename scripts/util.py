import re
import subprocess
import sys


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def error(msg):
    eprint("error:", msg)
    sys.exit(1)


def run(*cmd, capture_output=True):
    output = subprocess.run(cmd, capture_output=capture_output)

    if output.returncode != 0:
        if capture_output:
            eprint(output.stderr.decode("utf-8").strip())
        sys.exit(output.returncode)

    if capture_output:
        return output.stdout.decode("utf-8").strip(), output.stderr.decode("utf-8").strip()


TYPES = {
    "feat": [],
    "fix": [],
    "ci": ["scripts"],
    "docs": [],
}
IGNORED_TYPES = ["release"]
def parse_commit_msg(msg):
    regex = (
        "^(?P<type>[a-z]+)(\((?P<scope>[^)\n]+)\))?(?P<is_breaking>!)?: "
        "(?P<group>[^\s]+) (?P<desc>[^\n]+)"
        "(\n\n(?P<body>[\s\S]+))?$"
    )
    match = re.match(regex, msg)
    if match is None:
        error(f'Failed parsing: "{msg}"')

    change_type = match.group("type")

    if change_type in IGNORED_TYPES:
        return None

    scope = match.group("scope")
    is_breaking = match.group("is_breaking") is not None
    group = match.group("group").lower()
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

    if change_type not in TYPES:
        error(f"Unsupported change type: {change_type}")

    if scope is not None and scope not in TYPES[change_type]:
        error(f"Unsupported scope: {scope}")

    if group in ["add", "support"]:
        group = "Added"
    elif group in ["remove", "delete"]:
        group = "Removed"
    elif group == "fix" or change_type == "fix":
        if group != "fix":
            desc = f"Fixed {desc}"
        group = "Fixed"
    else:
        desc = f"{group} {desc}"
        group = "Changed"

    change = {
        "type": change_type,
        "group": group,
        "description": "%c%s%s" % (desc[0].upper(), desc[1:], "." if desc[-1] != "." else ""),
        "is_breaking_change": is_breaking or breaking_desc is not None,
    }

    if scope is not None:
        change["scope"] = scope

    if body is not None:
        change["long_description"] = "%c%s%s" % (
            body[0].upper(),
            body[1:],
            "." if body[-1] != "." else ""
        )

    if breaking_desc is not None:
        change["breaking_change_description"] = "%c%s" % (
            breaking_desc[0].upper(),
            breaking_desc[1:],
            "." if breaking_desc[-1] != "." else ""
        )

    return change
