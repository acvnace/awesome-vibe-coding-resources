"""Check the table of contents and new or changed resource listings."""

import argparse
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

HEADING = re.compile(r"^## (.+?)(?:\s+<!--.*-->)?$")
CONTENTS_LINK = re.compile(r"^- \[[^\[\]]+\]\(#([^\s)]+)\)$")
LISTING_LINK = re.compile(r"^[-+]\s+(?:🔥\s+|\*\*)?\[[^\[\]]+\]\((https?://[^\s)]+)\)")
PLAIN_LISTING = re.compile(r"^- \[[^\[\]<>]+\]\((https?://[^\s)]+)\)(?: - \S.*)?$")
PROMOTION = re.compile(
    r"\b(?:(?:affiliate|referral) (?:link|code)|(?:promo|coupon|discount) code|use code)\b",
    re.IGNORECASE,
)
HYPE = re.compile(
    r"\b(?:amazing|game[- ]changing|revolutionary|unmatched|unbeatable|best[- ]in[- ]class|"
    r"world['’]s (?:best|first)|infinite memory)\b",
    re.IGNORECASE,
)
PROMOTIONAL_PARAMS = {
    "aff", "aff_id", "affiliate", "affiliate_id", "referral", "referral_code",
    "coupon", "discount_code", "promo_code",
}
CONCEPT = "What is Vibe Coding"


def read_sections(text):
    sections = {}
    section = ""
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        heading = HEADING.fullmatch(raw)
        if heading:
            section = heading[1]
            sections.setdefault(section, [])
        elif line:
            sections.setdefault(section, []).append((number, line))
    return sections


def heading_anchor(heading):
    return re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-")


def review(before, after):
    previous = read_sections(before)
    current = read_sections(after)
    issues = []
    for section in ("Contents", CONCEPT):
        if not current.get(section):
            issues.append(("error", 1, f"Keep the {section} section and its entries."))

    anchors = {heading_anchor(heading) for heading in current if heading != "Contents"}
    for number, line in current.get("Contents", []):
        link = CONTENTS_LINK.fullmatch(line)
        if not link or link[1] not in anchors:
            issues.append(("error", number, "Use a link to a README section in the table of contents."))

    for section, lines in current.items():
        if section in {"", "Contribute", "Contents"}:
            continue
        old_lines = Counter(line for _, line in previous.get(section, []))
        previous_links = {
            link[1]: line for _, line in previous.get(section, [])
            if (link := LISTING_LINK.match(line))
        }
        for number, line in lines:
            if old_lines[line]:
                old_lines[line] -= 1
                continue
            link = LISTING_LINK.match(line)
            old_line = previous_links.get(link[1], "") if link else ""
            if not PLAIN_LISTING.fullmatch(line) and (not old_line or PLAIN_LISTING.fullmatch(old_line)):
                issues.append(("error", number, "Use a plain Markdown link followed by a factual description."))
                continue

            if PROMOTION.search(line) and not PROMOTION.search(old_line):
                issues.append(("error", number, "Remove referral, coupon, and discount promotions."))
            urls = re.findall(r"\]\((https?://[^\s)]+)\)", line)
            for url in urls:
                try:
                    parts = urlsplit(url)
                    host = parts.hostname
                except ValueError:
                    host = None
                if not host:
                    issues.append(("error", number, "Use a valid HTTP or HTTPS URL."))
                    continue
                keys = {key.casefold() for key, _ in parse_qsl(parts.query)}
                if keys & PROMOTIONAL_PARAMS and url not in old_line:
                    issues.append(("error", number, "Use a direct URL without affiliate or discount parameters."))
                if section == CONCEPT and not old_line and host == "github.com" and len(parts.path.strip("/").split("/")) == 2:
                    issues.append(("error", number, "List tool repositories in a resource category. Link to an explanation in the introduction."))

            if section == CONCEPT and not old_line:
                issues.append(("warning", number, "Review whether this source explains vibe coding."))
            if HYPE.search(line) and not HYPE.search(old_line):
                issues.append(("warning", number, "Check superlatives and broad claims against the source."))
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("proposed", type=Path)
    args = parser.parse_args()
    issues = review(args.base.read_text(encoding="utf-8"), args.proposed.read_text(encoding="utf-8"))
    for level, line, message in issues:
        print(f"::{level} file=README.md,line={line}::{message}")
    if not issues:
        print("README review passed.")
    return int(any(level == "error" for level, _, _ in issues))


if __name__ == "__main__":
    raise SystemExit(main())
