"""Render edit-region animations as stacked-panel GIFs."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from parse_gallery import GalleryCase

SUCCESS_OUTCOMES = frozenset({"repaired"})
PARTIAL_OUTCOMES = frozenset({"partial_repair"})
MAX_INSERT_STEPS = 32
MAX_DELETE_STEPS = 24
MAX_MIDDLE_DISPLAY = 180
MAX_MIDDLE_LINES = 8

RENDER_SCALE = 2.0


def _px(n: float) -> int:
    return max(1, int(round(n * RENDER_SCALE)))


def set_render_scale(scale: float) -> None:
    global RENDER_SCALE
    RENDER_SCALE = max(1.0, float(scale))


def _layout_px() -> None:
    """Refresh pixel constants after ``set_render_scale``."""
    global CANVAS_W, GRID_GAP, FONT_SIZE, LABEL_SIZE, HEADER_H, ROW_LABEL_H
    global PAD, BANNER_W, BANNER_GAP, LABEL_TEXT_X, HEADER_FONT_SIZE, MIN_QUAD_H

    CANVAS_W = _px(1100)
    GRID_GAP = _px(10)
    FONT_SIZE = _px(12)
    LABEL_SIZE = _px(11)
    HEADER_FONT_SIZE = _px(14)
    HEADER_H = _px(76)
    ROW_LABEL_H = _px(28)
    PAD = _px(12)
    BANNER_W = _px(5)
    BANNER_GAP = _px(10)
    LABEL_TEXT_X = PAD + BANNER_W + BANNER_GAP
    MIN_QUAD_H = _px(88)


_layout_px()

CONTINUATION_INDENT = "    "

# Match autoindexer_supplementary/docs/assets/styles.css
PAPER = (255, 255, 255)
PAPER_DEEP = (248, 250, 252)
INK = (30, 41, 59)
INK_MUTED = (100, 116, 139)
HEADER_BG = (30, 41, 59)

STYLE = {
    "context": {"fg": INK, "bg": None, "strike": False},
    "muted": {"fg": INK_MUTED, "bg": None, "strike": False},
    "select": {"fg": (194, 65, 12), "bg": (255, 247, 237), "strike": False},
    "insert": {"fg": (21, 128, 61), "bg": (240, 253, 244), "strike": False},
    "removed": {"fg": (185, 28, 28), "bg": (254, 226, 226), "strike": True},
    "added": {"fg": (21, 128, 61), "bg": (240, 253, 244), "strike": False},
    "draft_bad": {"fg": (153, 27, 27), "bg": (254, 242, 242), "strike": False},
    "gold": {"fg": (29, 78, 216), "bg": (239, 246, 255), "strike": False},
}

VERDICT_THEME = {
    "success": {
        "label": "SUCCESS",
        "badge": (34, 120, 72),
        "accent": (186, 244, 210),
    },
    "partial_success": {
        "label": "PARTIAL",
        "badge": (168, 118, 18),
        "accent": (255, 232, 160),
    },
    "fail": {
        "label": "FAIL",
        "badge": (168, 42, 52),
        "accent": (255, 205, 210),
    },
}


@dataclass
class CaseMetadata:
    filename: str
    case_index: int
    op: str
    outcome: str
    source: str
    dataset: str
    section: str
    verdict: str
    description: str
    reason: str
    k_insert: int
    d_delete: int
    lev_before: int
    lev_after: int
    before_middle: str
    after_middle: str
    gold_middle: str


@dataclass(frozen=True)
class StyledRun:
    text: str
    style: str


@dataclass
class AnimFrame:
    parts: list[tuple[str, str]]
    pulse: float = 0.0


@dataclass
class DisplayText:
    left: str
    right: str
    selected: str
    after: str
    gold: str
    show_gold_row: bool


def _pick_font(
    size: int,
    bold: bool = False,
    mono: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Project page: Helvetica Neue (UI) + SF Mono (code tokens)."""
    if mono:
        candidates: list[tuple[str, int | None]] = [
            ("/System/Library/Fonts/SFNSMono.ttf", None),
            ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", None),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", None),
        ]
    elif bold:
        candidates = [
            ("/System/Library/Fonts/Supplemental/HelveticaNeue-Medium.ttf", None),
            ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
            ("/System/Library/Fonts/Helvetica.ttc", 1),
        ]
    else:
        candidates = [
            ("/System/Library/Fonts/HelveticaNeue.ttc", 0),
            ("/System/Library/Fonts/Helvetica.ttc", 0),
            ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", None),
        ]
    for path, index in candidates:
        p = Path(path)
        if not p.exists():
            continue
        try:
            if index is None:
                return ImageFont.truetype(str(p), size=size)
            return ImageFont.truetype(str(p), size=size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def _line_metrics(font: ImageFont.ImageFont) -> int:
    ascent, descent = font.getmetrics()
    return ascent + descent + _px(5)


def _sanitize_filename_part(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s).strip("_") or "unknown"


def case_filename(case: GalleryCase) -> str:
    return (
        f"{case.index:03d}_{_sanitize_filename_part(case.op)}_"
        f"{_sanitize_filename_part(case.outcome)}_{_sanitize_filename_part(case.source)}.gif"
    )


def classify_case(case: GalleryCase) -> tuple[str, str, str]:
    if case.outcome in SUCCESS_OUTCOMES:
        verdict = "success"
        reason = (
            f"Model repair matched gold (Levenshtein {case.lev_before} → {case.lev_after})."
        )
    elif case.outcome in PARTIAL_OUTCOMES:
        verdict = "partial_success"
        reason = (
            f"Partial repair: distance improved but not exact "
            f"({case.lev_before} → {case.lev_after}, outcome={case.outcome})."
        )
    else:
        verdict = "fail"
        reason = _fail_reason(case)
    desc = (
        f"{case.op} / {case.outcome} on {case.source} ({case.dataset}): "
        f"k={case.k_insert}, d={case.d_delete}, Levenshtein {case.lev_before}→{case.lev_after}."
    )
    return verdict, desc, reason


def _fail_reason(case: GalleryCase) -> str:
    labels = {
        "no_edit": "No edit was applied; corruption remained.",
        "made_worse": "Edit increased Levenshtein distance to gold.",
        "wrong_position": "Edit targeted the wrong span.",
        "wrong_content": "Edit position ok but replacement text was wrong.",
        "over_delete": "Model deleted more than the corrupted span.",
        "under_delete": "Model deleted too little of the corruption.",
        "spurious_damaging": "Unneeded edit damaged clean text.",
        "spurious_harmless": "Spurious edit without matching gold repair.",
    }
    base = labels.get(case.outcome, f"Outcome classified as {case.outcome}.")
    return f"{base} Distance {case.lev_before} → {case.lev_after}."


def _expand_tabs(s: str) -> str:
    return s.replace("\t", CONTINUATION_INDENT)


def _leading_indent(segment: str) -> tuple[str, str]:
    i = 0
    while i < len(segment) and segment[i] in (" ", "\t"):
        i += 1
    return _expand_tabs(segment[:i]), _expand_tabs(segment[i:])


def _clip_middle(s: str) -> str:
    lines = s.split("\n")
    if len(lines) > MAX_MIDDLE_LINES:
        lines = lines[: MAX_MIDDLE_LINES - 1] + ["…"]
    s = "\n".join(lines)
    if len(s) <= MAX_MIDDLE_DISPLAY:
        return s
    half = MAX_MIDDLE_DISPLAY // 2
    return s[:half] + "…" + s[-half:]


def _prepare_display(case: GalleryCase) -> DisplayText:
    left = case.left_context
    right = case.right_context
    if case.left_omitted:
        left = "…" + left
    if case.right_omitted:
        right = right + "…"
    selected = _clip_middle(case.before_middle)
    after = _clip_middle(case.after_middle)
    gold = _clip_middle(case.gold_middle)
    show_gold = bool(gold.strip())
    return DisplayText(
        left=left,
        right=right,
        selected=selected,
        after=after,
        gold=gold,
        show_gold_row=show_gold,
    )


def _break_token(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    token: str,
    max_width: int,
) -> list[str]:
    if not token:
        return []
    if draw.textlength(token, font=font) <= max_width:
        return [token]
    chunks: list[str] = []
    buf = ""
    for ch in token:
        trial = buf + ch
        if buf and draw.textlength(trial, font=font) > max_width:
            chunks.append(buf)
            buf = ch
        else:
            buf = trial
    if buf:
        chunks.append(buf)
    return chunks


def _layout_styled(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    parts: Sequence[tuple[str, str]],
    max_width: int,
) -> list[list[StyledRun]]:
    lines: list[list[StyledRun]] = [[]]
    line_w = 0.0
    wrap_indent = ""
    at_line_start = True
    active_style = "context"

    def begin_line(indent: str, indent_style: str) -> None:
        nonlocal line_w, wrap_indent, at_line_start
        if lines[-1]:
            lines.append([])
        wrap_indent = indent
        line_w = 0.0
        at_line_start = True
        if indent:
            lines[-1].append(StyledRun(text=indent, style=indent_style))
            line_w = draw.textlength(indent, font=font)
            at_line_start = False

    def soft_break() -> None:
        begin_line(wrap_indent, active_style)

    def append_piece(piece: str, style: str) -> None:
        nonlocal line_w, at_line_start, active_style
        active_style = style
        if not piece:
            return
        for chunk in _break_token(draw, font, piece, max_width):
            w = draw.textlength(chunk, font=font)
            if not at_line_start and line_w + w > max_width:
                soft_break()
                w = draw.textlength(chunk, font=font)
            if at_line_start and w > max_width:
                for ch in chunk:
                    cw = draw.textlength(ch, font=font)
                    if not at_line_start and line_w + cw > max_width:
                        soft_break()
                    lines[-1].append(StyledRun(text=ch, style=style))
                    line_w += cw
                    at_line_start = False
                return
            lines[-1].append(StyledRun(text=chunk, style=style))
            line_w += w
            at_line_start = False

    def layout_words(content: str, style: str) -> None:
        i = 0
        while i < len(content):
            if content[i] == " ":
                append_piece(" ", style)
                i += 1
                continue
            j = i
            while j < len(content) and content[j] != " ":
                j += 1
            append_piece(content[i:j], style)
            i = j

    first_line = True
    for raw, style in parts:
        text = _expand_tabs(raw.replace("\r", ""))
        if not text:
            continue
        for seg_i, segment in enumerate(text.split("\n")):
            indent, content = _leading_indent(segment)
            if first_line and seg_i == 0:
                if indent:
                    begin_line(indent, style)
                first_line = False
            else:
                begin_line(indent, style)
            layout_words(content, style)

    if not lines[0]:
        lines = [[StyledRun(text="", style="context")]]
    return lines


def _count_lines(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    parts: Sequence[tuple[str, str]],
    max_width: int,
) -> int:
    return len(_layout_styled(draw, font, parts, max_width))


def _blend(bg: tuple[int, int, int], pulse: float) -> tuple[int, int, int]:
    if pulse <= 0:
        return bg
    alpha = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(pulse))
    return tuple(int(bg[i] * alpha + PAPER[i] * (1 - alpha)) for i in range(3))


def _draw_styled_lines(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    lines: list[list[StyledRun]],
    x0: int,
    y0: int,
    pulse: float,
) -> None:
    lh = _line_metrics(font)
    y = y0
    for line in lines:
        x = x0
        for run in line:
            if not run.text:
                continue
            spec = STYLE.get(run.style, STYLE["context"])
            fg = spec["fg"]
            bg = spec["bg"]
            w = draw.textlength(run.text, font=font)
            if bg and w > 0:
                bbox = draw.textbbox((x, y), run.text, font=font)
                fill = _blend(bg, pulse) if run.style == "select" else bg
                pad = _px(1)
                draw.rectangle(
                    [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
                    fill=fill,
                )
            draw.text((x, y), run.text, fill=fg, font=font)
            if spec["strike"] and w > 0:
                bbox = draw.textbbox((x, y), run.text, font=font)
                mid_y = (bbox[1] + bbox[3]) // 2
                draw.line(
                    [(bbox[0], mid_y), (bbox[2], mid_y)],
                    fill=fg,
                    width=max(1, _px(1)),
                )
            x += w
        y += lh


def _quad_width() -> int:
    return (CANVAS_W - 2 * PAD - GRID_GAP) // 2


def _row_panel_height(line_count: int, font: ImageFont.ImageFont | None = None) -> int:
    f = font or _pick_font(FONT_SIZE, mono=True)
    lh = _line_metrics(f)
    return ROW_LABEL_H + lh * line_count + PAD


def _draw_row_label(
    draw: ImageDraw.ImageDraw,
    font_label: ImageFont.ImageFont,
    font_sub: ImageFont.ImageFont,
    y: int,
    title: str,
    subtitle: str,
    accent: tuple[int, int, int],
) -> None:
    bar_h = _px(20)
    bar_top = y + (ROW_LABEL_H - bar_h) // 2
    draw.rounded_rectangle(
        [PAD, bar_top, PAD + BANNER_W, bar_top + bar_h],
        radius=_px(3),
        fill=accent,
    )
    title_bbox = draw.textbbox((0, 0), title, font=font_label)
    title_h = title_bbox[3] - title_bbox[1]
    text_y = y + (ROW_LABEL_H - title_h) // 2 - title_bbox[1]
    draw.text((LABEL_TEXT_X, text_y), title, fill=INK, font=font_label)
    title_w = draw.textlength(title, font=font_label)
    sub_x = LABEL_TEXT_X + title_w + _px(10)
    draw.text((sub_x, text_y), subtitle, fill=INK_MUTED, font=font_sub)


def _draw_header(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    font_bold: ImageFont.ImageFont,
    case: GalleryCase,
    verdict: str,
    y0: int,
    width: int,
) -> None:
    theme = VERDICT_THEME[verdict]
    draw.rectangle([0, y0, width, y0 + HEADER_H], fill=HEADER_BG)

    badge_text = theme["label"]
    badge_w = draw.textlength(badge_text, font=font_bold) + _px(24)
    badge_h = _px(28)
    bx, by = PAD, y0 + _px(12)
    draw.rounded_rectangle(
        [bx, by, bx + badge_w, by + badge_h],
        radius=_px(6),
        fill=theme["badge"],
    )
    draw.text((bx + _px(12), by + _px(5)), badge_text, fill=(255, 255, 255), font=font_bold)

    status_line = f"{case.outcome.replace('_', ' ').upper()}"
    draw.text(
        (bx + badge_w + _px(16), by + _px(4)),
        status_line,
        fill=theme["accent"],
        font=font_bold,
    )

    meta = f"{case.op} | {case.source} | dist {case.lev_before} -> {case.lev_after}"
    draw.text((PAD, y0 + _px(46)), meta, fill=(203, 213, 225), font=font)

    kmeta = f"k={case.k_insert}  d={case.d_delete}"
    kw = draw.textlength(kmeta, font=font)
    draw.text((width - PAD - kw, y0 + _px(46)), kmeta, fill=(150, 156, 168), font=font)


def _render_row(
    width: int,
    height: int,
    label_title: str,
    label_sub: str,
    accent: tuple[int, int, int],
    parts: Sequence[tuple[str, str]],
    pulse: float,
    font: ImageFont.ImageFont,
    font_label: ImageFont.ImageFont,
    font_sub: ImageFont.ImageFont,
) -> Image.Image:
    img = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(img)
    _draw_row_label(draw, font_label, font_sub, 0, label_title, label_sub, accent)
    max_w = width - 2 * PAD
    lines = _layout_styled(draw, font, parts, max_w)
    _draw_styled_lines(draw, font, lines, PAD, ROW_LABEL_H, pulse)
    return img


def _build_anim_sequence(disp: DisplayText) -> list[AnimFrame]:
    left, right = disp.left, disp.right
    sel = disp.selected
    ins = disp.after
    frames: list[AnimFrame] = []

    for t in range(8):
        frames.append(
            AnimFrame(
                [
                    (left, "context"),
                    (sel, "select"),
                    (right, "context"),
                ],
                pulse=float(t),
            )
        )

    steps = max(1, min(len(ins), MAX_INSERT_STEPS))
    for i in range(1, steps + 1):
        n = int(len(ins) * i / steps)
        frames.append(
            AnimFrame(
                [
                    (left, "context"),
                    (sel, "select"),
                    (ins[:n], "insert"),
                    (right, "context"),
                ]
            )
        )

    del_steps = max(1, min(len(sel), MAX_DELETE_STEPS)) if sel else 1
    for i in range(del_steps + 1):
        remain = sel[i:] if sel else ""
        frames.append(
            AnimFrame(
                [
                    (left, "context"),
                    (remain, "select"),
                    (ins, "insert"),
                    (right, "context"),
                ]
            )
        )

    for _ in range(10):
        frames.append(
            AnimFrame(
                [
                    (left, "context"),
                    (ins, "insert"),
                    (right, "context"),
                ]
            )
        )
    return frames


def _static_draft_parts(disp: DisplayText) -> list[tuple[str, str]]:
    return [
        (disp.left, "context"),
        (disp.selected, "draft_bad"),
        (disp.right, "context"),
    ]


def _static_edit_parts(disp: DisplayText) -> list[tuple[str, str]]:
    parts: list[tuple[str, str]] = [(disp.left, "context")]
    if disp.selected:
        parts.append((disp.selected, "removed"))
    if disp.after:
        parts.append((disp.after, "added"))
    parts.append((disp.right, "context"))
    return parts


def _static_gold_parts(disp: DisplayText) -> list[tuple[str, str]]:
    return [
        (disp.left, "context"),
        (disp.gold, "gold"),
        (disp.right, "context"),
    ]


def _deletion_gold_parts(disp: DisplayText) -> list[tuple[str, str]]:
    """Gold repair for a pure-deletion corruption: strike through the
    corrupted span with nothing put back in its place. There's no separate
    "gold text" to render for these (the correct repair removes the span
    entirely), but showing it struck through -- like the removed half of the
    MODEL EDIT panel -- makes that explicit instead of leaving the panel
    looking blank/broken.
    """
    return [
        (disp.left, "context"),
        (disp.selected, "removed"),
        (disp.right, "context"),
    ]


def _empty_gold_parts(case: GalleryCase) -> list[tuple[str, str]]:
    if case.op == "none":
        return [("(no corruption in this window — draft already matches gold)", "muted")]
    return [("(no separate gold snippet in gallery window)", "muted")]


def build_metadata(case: GalleryCase, filename: str) -> CaseMetadata:
    verdict, desc, reason = classify_case(case)
    return CaseMetadata(
        filename=filename,
        case_index=case.index,
        op=case.op,
        outcome=case.outcome,
        source=case.source,
        dataset=case.dataset,
        section=case.section,
        verdict=verdict,
        description=desc,
        reason=reason,
        k_insert=case.k_insert,
        d_delete=case.d_delete,
        lev_before=case.lev_before,
        lev_after=case.lev_after,
        before_middle=case.before_middle,
        after_middle=case.after_middle,
        gold_middle=case.gold_middle,
    )


def _composite_frame(
    case: GalleryCase,
    verdict: str,
    anim: AnimFrame,
    disp: DisplayText,
    font: ImageFont.ImageFont,
    font_label: ImageFont.ImageFont,
    font_bold: ImageFont.ImageFont,
    quad_heights: tuple[int, int],
    show_gold: bool,
    font_sub: ImageFont.ImageFont,
) -> Image.Image:
    theme = VERDICT_THEME[verdict]
    row1_h, row2_h = quad_heights
    total_h = HEADER_H + PAD + row1_h + GRID_GAP + row2_h + PAD
    qw = _quad_width()
    canvas = Image.new("RGB", (CANVAS_W, total_h), PAPER_DEEP)
    draw = ImageDraw.Draw(canvas)
    _draw_header(draw, font_label, font_bold, case, verdict, 0, CANVAS_W)

    if show_gold:
        gold_parts = _static_gold_parts(disp)
        gold_accent = (13, 148, 136)
    elif case.op == "delete" and disp.selected:
        gold_parts = _deletion_gold_parts(disp)
        gold_accent = (13, 148, 136)
    else:
        gold_parts = _empty_gold_parts(case)
        gold_accent = (148, 163, 184)

    quads = [
        (PAD, HEADER_H + PAD, "LIVE", "edit playback", theme["accent"], anim.parts, anim.pulse, row1_h),
        (
            PAD + qw + GRID_GAP,
            HEADER_H + PAD,
            "DRAFT",
            "corrupted span",
            (251, 146, 60),
            _static_draft_parts(disp),
            0.0,
            row1_h,
        ),
        (
            PAD,
            HEADER_H + PAD + row1_h + GRID_GAP,
            "MODEL EDIT",
            "removed / added",
            (34, 197, 94),
            _static_edit_parts(disp),
            0.0,
            row2_h,
        ),
        (
            PAD + qw + GRID_GAP,
            HEADER_H + PAD + row1_h + GRID_GAP,
            "GOLD",
            "expected repair",
            gold_accent,
            gold_parts,
            0.0,
            row2_h,
        ),
    ]

    for x, y, title, sub, accent, parts, pulse, h in quads:
        row_img = _render_row(qw, h, title, sub, accent, parts, pulse, font, font_label, font_sub)
        canvas.paste(row_img, (x, y))

    return canvas


def render_case_gif(
    case: GalleryCase,
    out_path: Path,
    fps: int = 8,
    scale: float | None = None,
) -> None:
    if scale is not None:
        set_render_scale(scale)
        _layout_px()
    font = _pick_font(FONT_SIZE, mono=True)
    font_label = _pick_font(LABEL_SIZE, bold=True, mono=False)
    font_sub = _pick_font(LABEL_SIZE, bold=False, mono=False)
    font_bold = _pick_font(HEADER_FONT_SIZE, bold=True, mono=False)
    verdict, _, _ = classify_case(case)
    disp = _prepare_display(case)
    anim_seq = _build_anim_sequence(disp)

    probe = Image.new("RGB", (4, 4))
    draw = ImageDraw.Draw(probe)
    max_w = _quad_width() - 2 * PAD

    live_lines = max(_count_lines(draw, font, f.parts, max_w) for f in anim_seq)
    draft_lines = _count_lines(draw, font, _static_draft_parts(disp), max_w)
    edit_lines = _count_lines(draw, font, _static_edit_parts(disp), max_w)
    if disp.show_gold_row:
        gold_lines = _count_lines(draw, font, _static_gold_parts(disp), max_w)
    elif case.op == "delete" and disp.selected:
        gold_lines = _count_lines(draw, font, _deletion_gold_parts(disp), max_w)
    else:
        gold_lines = 1

    row1_h = max(
        _row_panel_height(live_lines, font),
        _row_panel_height(draft_lines, font),
        MIN_QUAD_H,
    )
    row2_h = max(
        _row_panel_height(edit_lines, font),
        _row_panel_height(gold_lines, font),
        MIN_QUAD_H,
    )
    quad_heights = (row1_h, row2_h)

    frames = [
        _composite_frame(
            case,
            verdict,
            anim,
            disp,
            font,
            font_label,
            font_bold,
            quad_heights,
            disp.show_gold_row,
            font_sub,
        )
        for anim in anim_seq
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration_ms = int(1000 / fps)
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
