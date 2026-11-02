#!/usr/bin/env python3
"""Deterministic half-width → full-width parenthesis normalization for Chinese text.

Why this exists: the PDF text layer printed Chinese parentheticals as 「（…）」,
but the PaddleOCR merge (`merge_guide_ocr.py` → page_extract) emits half-width
「( … )」 for table cells and some paragraphs (e.g. ``規則式方法\\n( Rule-based )``,
``虛無假設 (B) 我們``).  The published guide applies this rule as the final
publication pass in ``export_guide_outline_data.py`` so every upstream exact
matcher (Track A repairs, publication overlays, formula attachment) still sees
the unchanged source text.

Rule (user decision 2026-11-01):
* convert a *paired* ``(`` … ``)`` on one line to 「（」…「）」 only when the
  context is Chinese: the inside contains CJK, or a CJK character/punctuation
  is adjacent outside (whitespace and ``<br>`` between them are allowed);
* never touch Latin/math/code contexts: ``f(x)``, ``TF(t, d)``, ``(x, y)``,
  ``(p < 0.05)``, math alphanumerics, Greek, LaTeX (``$…$``, ``\\(…\\)``),
  inline code, Markdown links ``[a](b)``, unpaired parentheses;
* ``$…$`` spans *inside* a pair are opaque (2026-11-01 review): the pair is
  Chinese when its plain inner text has CJK (``(拒絕 $ H_0 $ | $ H_0 $為真)``),
  or when it holds only math and Chinese text directly precedes it
  (``錯誤 ( $ \\beta $)``); ``( $ a $ = 0.05 )`` and ``P($A$)`` stay;
* whitespace just inside a converted pair is trimmed (``( Rule-based )`` →
  ``（Rule-based）``);
* 2026-11-02 review (page image 初級 guide1 3-27): the book sets no space
  between Chinese text and a full-width parenthesis, so horizontal spaces
  between a CJK character and a converted pair are dropped on either side
  (``檢定 (test)`` → ``檢定（test）``), except for enumerator labels (one
  letter or a 1–2 digit number: ``假設 (B) 我們`` keeps its option spacing);
* a spaced function application (``T=T (X)``) stays Latin unless Chinese text
  directly follows it on the same line (``以 T=T (X) 表之`` →
  ``以 T=T（X）表之``); it then also loses the spaces around the pair.

The function is pure and idempotent: ``normalize(normalize(s)) == normalize(s)``.
"""

from __future__ import annotations

import re
from typing import Any

_CJK_CORE = (
    '㐀-䶿'      # CJK Extension A
    '一-鿿'      # CJK Unified Ideographs
    '豈-﫿'      # CJK Compatibility Ideographs (e.g. 「數」U+F969)
    '぀-ヿ'      # Hiragana / Katakana
    '\U00020000-\U0002ffff'
)
CJK_CORE_RE = re.compile(f'[{_CJK_CORE}]')
# Outside context also accepts CJK punctuation and full-width forms (「：」「。」「）」).
CJK_CONTEXT_RE = re.compile(f'[{_CJK_CORE}　-〿＀-￯]')

PAIR_RE = re.compile(r'\(([^()\n]*)\)')
PROTECTED_SPAN_RES = (
    re.compile(r'```.*?```', re.S),
    re.compile(r'\$\$.*?\$\$', re.S),
    re.compile(r'\$[^$\n]+\$'),
    re.compile(r'\\\(.*?\\\)', re.S),
    re.compile(r'\\\[.*?\\\]', re.S),
    re.compile(r'`[^`\n]*`'),
)
BR_TAG_RE = re.compile(r'<br\s*/?>', re.I)
IDENTIFIER_CHAR_RE = re.compile(r'[A-Za-z0-9_.Ͱ-Ͽ\U0001d400-\U0001d7ff]')
MATH_INNER_RE = re.compile(
    r'[=+*/^_<>|~\\$`{}\[\]≤≥≠≈∑∏∫√∞∂∇±×÷·∙−⋯Ͱ-Ͽ\U0001d400-\U0001d7ff]'
)
TUPLE_INNER_RE = re.compile(r'^\s*[A-Za-z0-9]+\s*(?:,\s*[A-Za-z0-9]+\s*)+$')
SINGLE_LOWER_RE = re.compile(r'^\s*[a-z]\s*$')
QUOTE_RE = re.compile(r'["\'“”‘’]')
SHORT_TOKEN_RE = re.compile(r'^\s*[A-Za-z0-9]{1,3}\s*$')
HSPACE = ' \t　'


def _spaced_identifier_before(text: str, index: int) -> bool:
    """True when ``(`` follows a Latin identifier across horizontal spaces only."""
    cursor = index
    while cursor > 0 and text[cursor - 1] in HSPACE:
        cursor -= 1
    return cursor > 0 and bool(IDENTIFIER_CHAR_RE.match(text[cursor - 1]))


def _protected_mask(text: str) -> list[bool]:
    mask = [False] * len(text)
    for pattern in PROTECTED_SPAN_RES:
        for match in pattern.finditer(text):
            for index in range(match.start(), match.end()):
                mask[index] = True
    return mask


def _previous_context_char(text: str, index: int) -> str:
    """Nearest non-whitespace char before ``index`` (``<br>`` counts as space)."""
    cursor = index
    while cursor > 0:
        char = text[cursor - 1]
        if char.isspace():
            cursor -= 1
            continue
        if char == '>':
            start = text.rfind('<', 0, cursor)
            if start != -1 and BR_TAG_RE.fullmatch(text[start:cursor]):
                cursor = start
                continue
        return char
    return ''


def _next_context_char(text: str, index: int) -> str:
    """Nearest non-whitespace char at/after ``index`` (``<br>`` counts as space)."""
    cursor = index
    while cursor < len(text):
        char = text[cursor]
        if char.isspace():
            cursor += 1
            continue
        if char == '<':
            match = BR_TAG_RE.match(text, cursor)
            if match:
                cursor = match.end()
                continue
        return char
    return ''


FUNCTION = 'function'
ENUMERATOR_RE = re.compile(r'^\s*(?:[A-Za-z]|\d{1,2})\s*$')


def _next_inline_char(text: str, index: int) -> str:
    """Next char at/after ``index`` skipping horizontal spaces only."""
    cursor = index
    while cursor < len(text) and text[cursor] in HSPACE:
        cursor += 1
    return text[cursor] if cursor < len(text) else ''


def _inner_is_math_or_code(inner: str) -> bool:
    stripped = inner.strip()
    return (
        not stripped
        or bool(MATH_INNER_RE.search(stripped))
        or bool(TUPLE_INNER_RE.match(stripped))
        or bool(SINGLE_LOWER_RE.match(stripped))
    )


def _should_convert(text: str, start: int, end: int, inner: str, mask: list[bool]) -> bool | str:
    before = text[start - 1] if start > 0 else ''
    if before in {'\\', ']'}:
        return False  # LaTeX \( … \) or a Markdown link target
    # Protected spans inside the pair (``$ H_0 $``) are opaque: judge the
    # context on the plain text around them (2026-11-01 review: 「(拒絕 $ H_0 $
    # | $ H_0 $為真)」 and 「錯誤 ( $ \\beta $)」 are Chinese parentheticals).
    inner_plain = ''.join(
        char for offset, char in enumerate(inner, start=start + 1) if not mask[offset]
    )
    has_math_span = len(inner_plain) != len(inner)
    if '$' in inner_plain or '\\' in inner_plain or '`' in inner_plain:
        return False  # unbalanced/partial math or code: never guess
    attached_identifier = bool(before) and bool(IDENTIFIER_CHAR_RE.match(before))
    if has_math_span:
        if CJK_CORE_RE.search(inner_plain):
            return not attached_identifier
        if inner_plain.strip(HSPACE) or attached_identifier:
            return False  # ( $ a $ = 0.05 ), P($A$): math context
        # A bare math gloss is Chinese only when Chinese text precedes it.
        previous_char = _previous_context_char(text, start)
        return bool(previous_char and CJK_CORE_RE.match(previous_char))
    if CJK_CORE_RE.search(inner):
        # print("你好") is code even with CJK inside.
        return not (attached_identifier and QUOTE_RE.search(inner))
    if attached_identifier or _inner_is_math_or_code(inner):
        return False  # f(x), TF(t, d), (x, y), (p < 0.05), (𝑘)
    if SHORT_TOKEN_RE.match(inner) and _spaced_identifier_before(text, start):
        # T=T (X), P (A): a spaced function application stays Latin unless
        # Chinese text directly follows it (「以 T=T (X) 表之」 is printed
        # 「T=T（X）表之」, 初級 guide1 3-27).
        next_char = _next_inline_char(text, end)
        return FUNCTION if next_char and CJK_CORE_RE.match(next_char) else False
    previous_char = _previous_context_char(text, start)
    next_char = _next_context_char(text, end)
    return bool(
        (previous_char and CJK_CONTEXT_RE.match(previous_char))
        or (next_char and CJK_CONTEXT_RE.match(next_char))
    )


def _normalize_once(text: str) -> str:
    mask = _protected_mask(text)
    pieces: list[str] = []
    cursor = 0
    for match in PAIR_RE.finditer(text):
        start, end = match.start(), match.end()
        if mask[start] or mask[end - 1]:
            continue
        inner = match.group(1)
        mode = _should_convert(text, start, end, inner, mask)
        if not mode:
            continue
        trim_outside = mode == FUNCTION or not ENUMERATOR_RE.match(inner)
        before = text[cursor:start]
        trimmed = before.rstrip(HSPACE)
        if trim_outside and trimmed != before and (
            mode == FUNCTION or (trimmed and CJK_CORE_RE.match(trimmed[-1]))
        ):
            before = trimmed
        pieces.append(before)
        pieces.append('（' + inner.strip(HSPACE) + '）')
        cursor = end
        after = _next_inline_char(text, end)
        if trim_outside and text[end:end + 1] in tuple(HSPACE) and after and (
            mode == FUNCTION or CJK_CORE_RE.match(after)
        ):
            while cursor < len(text) and text[cursor] in HSPACE:
                cursor += 1
    if not pieces:
        return text
    pieces.append(text[cursor:])
    return ''.join(pieces)


def normalize_cjk_parentheses(text: str) -> str:
    """Return ``text`` with Chinese-context half-width parentheses made full-width.

    Iterates to a fixpoint so that a conversion that creates new CJK context
    (``(1)(B)``) or exposes an enclosing pair is applied in the same call; this
    makes the function idempotent.
    """
    if not isinstance(text, str) or '(' not in text:
        return text
    current = text
    for _ in range(64):
        updated = _normalize_once(current)
        if updated == current:
            return current
        current = updated
    raise RuntimeError('CJK parenthesis normalization did not converge')


TEXT_FIELDS = ('text', 'title')


def normalize_block_parentheses(block: dict[str, Any]) -> dict[str, Any]:
    """Normalize the reader-visible text fields of one published guide block.

    Only ``text``, ``title`` and table ``rows`` are rewritten.  ``anchor``
    (stable URL), ``formulas`` (LaTeX), ``alt`` (Track A source-fidelity
    signature) and provenance fields are left untouched.  ``html`` is derived
    from ``rows`` by the caller.
    """
    result = dict(block)
    for field in TEXT_FIELDS:
        value = result.get(field)
        if isinstance(value, str):
            result[field] = normalize_cjk_parentheses(value)
    rows = result.get('rows')
    if isinstance(rows, list):
        result['rows'] = [
            [normalize_cjk_parentheses(cell) if isinstance(cell, str) else cell for cell in row]
            if isinstance(row, list) else row
            for row in rows
        ]
    return result
