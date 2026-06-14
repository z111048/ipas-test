"""Question duplicate detection helpers for generated exam data."""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher
from typing import Any

DEFAULT_SIMILARITY_THRESHOLD = 0.80


def normalize_question_text(value: str) -> str:
    normalized = unicodedata.normalize('NFKC', value).lower()
    chars = []
    for char in normalized:
        if char.isspace():
            continue
        if unicodedata.category(char).startswith('P'):
            continue
        chars.append(char)
    return ''.join(chars)


def question_similarity(left: str, right: str) -> float:
    left_norm = normalize_question_text(left)
    right_norm = normalize_question_text(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def find_similar_question_pairs(
    questions: list[dict[str, Any]],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[tuple[int, int, float, dict[str, Any], dict[str, Any]]]:
    pairs = []
    normalized = [
        (index, question, normalize_question_text(str(question.get('question') or '')))
        for index, question in enumerate(questions)
    ]
    for left_pos, (left_index, left_question, left_text) in enumerate(normalized):
        if not left_text:
            continue
        for right_index, right_question, right_text in normalized[left_pos + 1:]:
            if not right_text:
                continue
            ratio = 1.0 if left_text == right_text else SequenceMatcher(None, left_text, right_text).ratio()
            if ratio >= threshold:
                pairs.append((left_index, right_index, ratio, left_question, right_question))
    return pairs


def find_similar_question_pairs_between(
    current_questions: list[dict[str, Any]],
    previous_questions: list[dict[str, Any]],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[tuple[int, int, float, dict[str, Any], dict[str, Any]]]:
    pairs = []
    previous = [
        (index, question, normalize_question_text(str(question.get('question') or '')))
        for index, question in enumerate(previous_questions)
    ]
    current = [
        (index, question, normalize_question_text(str(question.get('question') or '')))
        for index, question in enumerate(current_questions)
    ]
    for current_index, current_question, current_text in current:
        if not current_text:
            continue
        for previous_index, previous_question, previous_text in previous:
            if not previous_text:
                continue
            ratio = 1.0 if current_text == previous_text else SequenceMatcher(None, current_text, previous_text).ratio()
            if ratio >= threshold:
                pairs.append((current_index, previous_index, ratio, current_question, previous_question))
    return pairs


def question_label(question: dict[str, Any], fallback_index: int) -> str:
    question_id = question.get('id')
    return question_id if isinstance(question_id, str) and question_id else f'questions[{fallback_index}]'
