import re
import subprocess
import sys


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def error(msg):
    eprint("error:", msg)
    sys.exit(1)


def run(*cmd):
    output = subprocess.run(cmd, capture_output=True)
    return output.stdout.decode("utf-8").strip(), output.stderr.decode("utf-8").strip()


def parse_commit_msg(msg):
    regex = (
        "^(?P<type>feat|fix)(\((?P<scope>[^)]+)\))?(?P<is_breaking>!)?: "
        "(?P<desc>(?P<group>[a-z]+) [^\n.]+)"
        "(\n\n(?P<body>[\s\S]+))?$"
    )
    match = re.match(regex, msg)
    if match is None:
        error(f'Failed parsing: "{msg}"')

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

    obj = {
        "group": group,
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

    return obj
