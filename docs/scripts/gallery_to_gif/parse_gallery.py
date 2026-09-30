"""Parse edit-evaluation cases from GALLERY.md."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

CASE_HEADER = re.compile(
    r"^### (?P<op>\w+) · (?P<outcome>[\w_]+) · `(?P<source>[^`]+)` · (?P<dataset>\S+)\s*$"
)
META_KD = re.compile(
    r"- `k=(\d+)` inserted, `d=(\d+)` deleted, at position (\d+), (\d+) tokens before the edit fires"
)
META_SPANS = re.compile(
    r"- gold span `\[(.*?)\)`, model span `\[(.*?)\)`; Levenshtein to gold (\d+) → (\d+)"
)
GUILLEMET = re.compile(r"«««(.*?)»»»", re.DOTALL)
EMITTED_EDIT = re.compile(
    r"⟦EDIT start=(\d+) end=(\d+)⟧(.*?)(?=⟦EDIT|⟦RET⟧|\Z)",
    re.DOTALL,
)

DRAFT_LABEL = re.compile(r"\*\*1\. Draft it was given\*\*.*?\n```\n", re.DOTALL)
EMITTED_LABEL = re.compile(r"\*\*2\. What it emitted\*\*.*?\n```\n", re.DOTALL)
RESOLVED_LABEL = re.compile(r"\*\*3\. Resolved text after applying the edit:\*\*\n```\n", re.DOTALL)
GOLD_LABEL = re.compile(r"\*\*4\. Gold\*\*.*?\n```\n", re.DOTALL)
CODE_FENCE_END = re.compile(r"\n```")


@dataclass
class GalleryCase:
    index: int
    op: str
    outcome: str
    source: str
    dataset: str
    section: str
    k_insert: int
    d_delete: int
    edit_position: int
    lag_tokens: int
    gold_span: str
    model_span: str
    lev_before: int
    lev_after: int
    draft: str
    emitted: str
    resolved: str
    gold: str
    left_context: str
    right_context: str
    before_middle: str
    after_middle: str
    gold_middle: str
    left_omitted: bool
    right_omitted: bool

    @property
    def before_snippet(self) -> str:
        return self.left_context + self.before_middle + self.right_context

    @property
    def after_snippet(self) -> str:
        return self.left_context + self.after_middle + self.right_context

    @property
    def gold_snippet(self) -> str:
        return self.left_context + self.gold_middle + self.right_context


def _section_for_line(sections: list[tuple[str, int]], line_no: int) -> str:
    current = ""
    for title, start in sections:
        if start <= line_no:
            current = title
    return current


def _parse_sections(lines: list[str]) -> list[tuple[str, int]]:
    sections: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        if line.startswith("## ") and "/" in line and "cases)" in line:
            sections.append((line[3:].strip(), i))
    return sections


def _extract_after(label: re.Pattern[str], block: str) -> str:
    m = label.search(block)
    if not m:
        return ""
    rest = block[m.end() :]
    end = CODE_FENCE_END.search(rest)
    if not end:
        return rest.strip()
    return rest[: end.start()]


def _context_window(text: str, marker_start: int, marker_end: int, ctx: int = 48) -> tuple[str, str, str]:
    inner = text[marker_start:marker_end]
    left = text[max(0, marker_start - ctx) : marker_start]
    right = text[marker_end : marker_end + ctx]
    return left, inner, right


def _strip_guillemets(text: str) -> str:
    return GUILLEMET.sub(lambda m: m.group(1), text)


def _align_region(reference: str, draft_clean: str) -> str:
    if not reference:
        return ""
    prefix_len = min(len(draft_clean), len(reference))
    p = 0
    while p < prefix_len and draft_clean[p] == reference[p]:
        p += 1
    suffix_len = min(len(draft_clean) - p, len(reference) - p)
    s = 0
    while s < suffix_len and draft_clean[len(draft_clean) - 1 - s] == reference[len(reference) - 1 - s]:
        s += 1
    start = p
    end = max(start, len(reference) - s)
    return reference[start:end]


def _middle_from_emitted(emitted: str) -> str:
    edits = EMITTED_EDIT.findall(emitted)
    if not edits:
        return ""
    return edits[0][2].strip()


def _extract_from_diff(draft_clean: str, other: str, ctx: int = 48) -> tuple[str, str, str, str]:
    matcher = difflib.SequenceMatcher(None, draft_clean, other, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        left = draft_clean[max(0, i1 - ctx) : i1]
        before_mid = draft_clean[i1:i2]
        right = draft_clean[i2 : i2 + ctx]
        after_mid = other[j1:j2]
        return left, before_mid, right, after_mid
    return "", "", "", ""


CTX = 48


def _extract_edit_region(
    draft: str, resolved: str, gold: str, emitted: str
) -> tuple[str, str, str, str, str, bool, bool]:
    draft_clean = _strip_guillemets(draft)
    m = GUILLEMET.search(draft)
    if not m:
        left, before_mid, right, after_mid = _extract_from_diff(draft_clean, resolved)
        _, _, _, gold_mid = _extract_from_diff(draft_clean, gold)
        if not after_mid.strip():
            after_mid = _middle_from_emitted(emitted)
        left_omitted = len(left) > 0 and draft_clean.find(left) > 0
        right_omitted = bool(right) and not draft_clean.endswith(right)
        return left, before_mid, right, after_mid, gold_mid, left_omitted, right_omitted

    inner = m.group(1)
    i1 = m.start()
    i2 = i1 + len(inner)
    left, _, right = _context_window(draft_clean, i1, i2, ctx=CTX)
    before_mid = inner
    after_mid = _align_region(resolved, draft_clean)
    gold_mid = _align_region(gold, draft_clean)
    emitted_mid = _middle_from_emitted(emitted)
    if emitted_mid and (
        not after_mid
        or len(after_mid) > max(96, len(before_mid) * 4 + 32)
        or "\n" in after_mid
        and len(before_mid) < 24
    ):
        after_mid = emitted_mid
    # NOTE: deliberately no "after_mid = gold_mid" fallback here. That used
    # to compensate for a weaker alignment heuristic that often failed to
    # find real model-emitted text, but it also fabricated a MODEL EDIT panel
    # that silently copied the GOLD panel whenever the model genuinely made
    # no edit (after_mid legitimately empty) or emitted an unrelated result,
    # making the two panels look identical when they should differ.
    left_omitted = i1 > CTX
    right_omitted = i2 + CTX < len(draft_clean)
    return left, before_mid, right, after_mid, gold_mid, left_omitted, right_omitted


def parse_gallery(path: Path) -> list[GalleryCase]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections = _parse_sections(lines)

    cases: list[GalleryCase] = []
    case_index = 0
    header_re = re.compile(CASE_HEADER.pattern, re.MULTILINE)
    header_matches = list(header_re.finditer(text))

    for i, hm in enumerate(header_matches):
        start = hm.start()
        end = header_matches[i + 1].start() if i + 1 < len(header_matches) else len(text)
        chunk = text[start:end]

        line_no = text[:start].count("\n")
        section = _section_for_line(sections, line_no)

        kd = META_KD.search(chunk)
        sp = META_SPANS.search(chunk)
        if not kd or not sp:
            continue

        draft = _extract_after(DRAFT_LABEL, chunk)
        emitted = _extract_after(EMITTED_LABEL, chunk)
        resolved = _extract_after(RESOLVED_LABEL, chunk)
        gold = _extract_after(GOLD_LABEL, chunk)

        left, before_mid, right, after_mid, gold_mid, left_om, right_om = _extract_edit_region(
            draft, resolved, gold, emitted
        )

        cases.append(
            GalleryCase(
                index=case_index,
                op=hm.group("op"),
                outcome=hm.group("outcome"),
                source=hm.group("source"),
                dataset=hm.group("dataset"),
                section=section,
                k_insert=int(kd.group(1)),
                d_delete=int(kd.group(2)),
                edit_position=int(kd.group(3)),
                lag_tokens=int(kd.group(4)),
                gold_span=sp.group(1),
                model_span=sp.group(2),
                lev_before=int(sp.group(3)),
                lev_after=int(sp.group(4)),
                draft=draft,
                emitted=emitted,
                resolved=resolved,
                gold=gold,
                left_context=left,
                right_context=right,
                before_middle=before_mid,
                after_middle=after_mid,
                gold_middle=gold_mid,
                left_omitted=left_om,
                right_omitted=right_om,
            )
        )
        case_index += 1

    return cases


def iter_cases(path: Path) -> Iterator[GalleryCase]:
    yield from parse_gallery(path)
