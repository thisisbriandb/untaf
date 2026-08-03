"""Markdown to Typst converter.

Converts markdown content (bold, italic, links, code) into Typst markup syntax.
Extracted from rendercv and adapted for standalone use.
"""

import itertools
import re
from xml.etree.ElementTree import Element

import markdown
import markdown.core


def to_typst_string(elem: Element) -> str:
    """Recursively convert XML Element tree to Typst markup string."""
    result = []

    if elem.text:
        result.append(escape_typst_characters(elem.text))

    for child in elem:
        match child.tag:
            case "strong":
                inner = to_typst_string(child)
                child_content = f"#strong[{inner}]"

            case "em":
                inner = to_typst_string(child)
                child_content = f"#emph[{inner}]"

            case "code":
                child_content = f"`{child.text}`"

            case "a":
                href = child.get("href") if child.get("href") else "https://example.com"
                inner = to_typst_string(child)
                child_content = f'#link("{href}")[{inner}]'

            case "div":
                child_content = (
                    "#summary["
                    + to_typst_string(child).strip("\n").replace("\n", " \\ ")
                    + "]"
                )

            case _:
                if getattr(child, "attrib", {}).get("class") == "admonition-title":
                    continue
                child_content = to_typst_string(child)

        result.append(child_content)

        if child.tail:
            result.append(escape_typst_characters(child.tail))

    return "".join(result)


typst_command_pattern = re.compile(r"#([A-Za-z_-]+)(\([^\)]*\))?(\[[^\]]*\])?")
math_pattern = re.compile(r"(\$\$.*?\$\$)")


def escape_typst_characters(string: str) -> str:
    """Escape Typst special characters while preserving Typst commands and math."""
    if string == "\n":
        return string

    # Preserve Typst commands and math expressions
    typst_command_mapping = {}
    for i, match in enumerate(
        itertools.chain(
            math_pattern.finditer(string),
            typst_command_pattern.finditer(string),
        )
    ):
        dummy_name = f"CVENGINETYPSTCMD{i}"
        typst_command_mapping[dummy_name] = match.group(0)
        string = string.replace(typst_command_mapping[dummy_name], dummy_name)
        typst_command_mapping[dummy_name] = typst_command_mapping[dummy_name].replace(
            "$$", "$"
        )

    escape_dictionary = {
        "[": "\\[",
        "]": "\\]",
        "\\": "\\\\",
        '"': '\\"',
        "#": "\\#",
        "$": "\\$",
        "@": "\\@",
        "%": "\\%",
        "~": "\\~",
        "_": "\\_",
        "/": "\\/",
        ">": "\\>",
        "<": "\\<",
    }

    string = string.translate(str.maketrans(escape_dictionary))

    longer_escape_dictionary = {
        "* ": "#sym.ast.basic ",
        "*": "#sym.ast.basic#h(0pt, weak: true) ",
    }
    for key, value in longer_escape_dictionary.items():
        string = string.replace(key, value)

    for dummy_name, full_command in typst_command_mapping.items():
        string = string.replace(dummy_name, full_command)

    return string


# Markdown instance configured for Typst output
_md = markdown.core.Markdown(extensions=["admonition"])
_md.output_formats["typst"] = to_typst_string  # type: ignore
_md.set_output_format("typst")  # type: ignore
_md.parser.blockprocessors.deregister("hashheader")
_md.parser.blockprocessors.deregister("setextheader")
_md.parser.blockprocessors.deregister("olist")
_md.parser.blockprocessors.deregister("ulist")
_md.parser.blockprocessors.deregister("quote")
_md.stripTopLevelTags = False


def markdown_to_typst(markdown_string: str) -> str:
    """Convert Markdown string to Typst markup.

    Lines are processed independently to prevent emphasis markers on adjacent
    lines from interacting. Admonition blocks are kept together.

    Args:
        markdown_string: Markdown content.

    Returns:
        Typst-formatted string.
    """
    lines = markdown_string.split("\n")
    result_parts: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("!!!"):
            # Admonition block
            block = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].startswith("    "):
                block.append(lines[i])
                i += 1
            _md.reset()
            result_parts.append(_md.convert("\n".join(block)))
        else:
            _md.reset()
            result_parts.append(_md.convert(lines[i]))
            i += 1
    return "\n".join(result_parts)
