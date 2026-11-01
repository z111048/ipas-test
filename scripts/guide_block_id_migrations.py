#!/usr/bin/env python3
"""Apply the reviewed guide block-id migration table to stored block references.

Background: published guide blocks are numbered ``block-1..N`` per node in
reading order.  A sanctioned Track A rebuild (new OCR text, split giant blocks)
renumbers them, while two committed/pipeline inputs keep the *old* ids:

* Codex exam reference-answer citations (``data/{level}/pipeline/
  exam_reference_answers/*/outputs`` plus ``data/exam_reference_answer_overlays.json``)
* image-unit ``headingBlockId`` (``data/共用/image_units_all_levels.json``)

``scripts/build_guide_block_id_migrations.py`` writes the deterministic table
``data/guide_block_id_migrations.json`` (old→new id per guide/node, with
method exact|normalized|fuzzy|unmapped and ratio, plus question-specific
``auto-citation`` resolutions for unmapped blocks).  Human decisions live in
``data/guide_citation_overrides.json`` (``remap``/``remove`` with a reason)
and are never rewritten by the generator.

Safety contract (fail closed):
* the table's ``to.guideSha256`` must equal the current published content,
  otherwise the table is stale;
* the table applies only to inputs whose digest is recorded in its scope
  (``citationScope`` / ``imageUnitsScope``).  A regenerated input (new ids)
  outside the scope is validated as-is and never remapped twice; an input in
  scope whose digest changed is an error;
* every resulting id must exist in the current content; an unmapped block or
  an unknown id needs an explicit override, otherwise export stops.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTENT_ROOT = ROOT / 'frontend/src/generated/guideContent'
MIGRATIONS_PATH = ROOT / 'data/guide_block_id_migrations.json'
OVERRIDES_PATH = ROOT / 'data/guide_citation_overrides.json'
SCHEMA_VERSION = 1
OVERRIDE_SCHEMA_VERSION = 1
OVERRIDE_ACTIONS = {'remap', 'remove'}
MAX_REPORTED_ERRORS = 40


class BlockIdMigrationError(ValueError):
    """Raised when a stored block reference cannot be resolved safely."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha256_text(value: str) -> str:
    return 'sha256:' + hashlib.sha256(value.encode('utf-8')).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def block_text(block: dict[str, Any]) -> str:
    """Reader-visible identity text of one block (title, text, table cells)."""
    parts = [str(block.get('title') or ''), str(block.get('text') or '')]
    rows = block.get('rows')
    if rows:
        parts.append('\n'.join('\t'.join(str(cell or '') for cell in row) for row in rows))
    items = block.get('items')
    if items:
        parts.append(canonical_json(items))
    return '\n'.join(part for part in parts if part)


_NORMALIZE_STRIP_RE = re.compile(r'[\s•●◦○▪■◆\-]+')


def normalized_block_text(value: str) -> str:
    """NFKC (so 「（」==「(」) and drop whitespace/bullets for tolerant matching."""
    return _NORMALIZE_STRIP_RE.sub('', unicodedata.normalize('NFKC', value or ''))


def node_identity(blocks: list[dict[str, Any]]) -> list[list[Any]]:
    return [[str(block.get('id')), block.get('type'), block_text(block)] for block in blocks]


def guide_content_sha256(nodes: dict[str, list[dict[str, Any]]]) -> str:
    """Digest of the id/type/text identity of every block in one guide."""
    return sha256_text(canonical_json({
        node: node_identity(blocks) for node, blocks in sorted(nodes.items())
    }))


def load_content_tree(content_root: Path) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """``{guideKey: {nodeId: blocks}}`` from a guideContent directory."""
    tree: dict[str, dict[str, list[dict[str, Any]]]] = {}
    if not content_root.is_dir():
        return tree
    for guide_dir in sorted(path for path in content_root.iterdir() if path.is_dir()):
        nodes: dict[str, list[dict[str, Any]]] = {}
        for path in sorted(guide_dir.glob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8'))
            nodes[path.stem] = list(data.get('blocks') or [])
        tree[guide_dir.name] = nodes
    return tree


def reference_answers_digest(answers: dict[str, Any]) -> str:
    """Scope digest of one exam's *pre-migration* published answers."""
    return sha256_text(canonical_json(answers))


def _load_optional_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def validate_table(table: dict[str, Any], path: Path) -> None:
    if table.get('schemaVersion') != SCHEMA_VERSION:
        raise BlockIdMigrationError(f'Unsupported block-id migration schema: {path}')
    for field in ('from', 'to', 'blocks', 'citationScope', 'imageUnitsScope', 'citations'):
        if field not in table:
            raise BlockIdMigrationError(f'Block-id migration table lacks {field!r}: {path}')
    for guide, nodes in table['blocks'].items():
        for node, entries in nodes.items():
            for old_id, entry in entries.items():
                method = entry.get('method')
                if method not in {'exact', 'normalized', 'fuzzy', 'manual', 'unmapped'}:
                    raise BlockIdMigrationError(
                        f'Invalid migration method {method!r}: {guide}/{node}/{old_id}'
                    )
                if (entry.get('new') is None) != (method == 'unmapped'):
                    raise BlockIdMigrationError(
                        f'Migration entry new/method mismatch: {guide}/{node}/{old_id}'
                    )


def validate_overrides(payload: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    if payload.get('schemaVersion') != OVERRIDE_SCHEMA_VERSION:
        raise BlockIdMigrationError(f'Unsupported citation override schema: {path}')
    entries = payload.get('citations')
    if not isinstance(entries, list):
        raise BlockIdMigrationError(f'Citation overrides must contain citations[]: {path}')
    seen: set[tuple[Any, ...]] = set()
    for index, entry in enumerate(entries):
        label = f'{path.name}#citations[{index}]'
        for field in ('level', 'exam', 'questionId', 'guideKey', 'nodeId', 'oldBlockId', 'action', 'reason'):
            if not str(entry.get(field) or '').strip():
                raise BlockIdMigrationError(f'{label}: missing {field}')
        if entry['action'] not in OVERRIDE_ACTIONS:
            raise BlockIdMigrationError(f'{label}: action must be one of {sorted(OVERRIDE_ACTIONS)}')
        new_ids = entry.get('newBlockIds')
        if entry['action'] == 'remap':
            if not isinstance(new_ids, list) or not new_ids or not all(isinstance(x, str) for x in new_ids):
                raise BlockIdMigrationError(f'{label}: remap needs non-empty newBlockIds')
        elif new_ids:
            raise BlockIdMigrationError(f'{label}: remove must not carry newBlockIds')
        citation_index = entry.get('citationIndex')
        if citation_index is not None and (not isinstance(citation_index, int) or citation_index < 0):
            raise BlockIdMigrationError(f'{label}: citationIndex must be a non-negative int')
        key = (
            entry['level'], entry['exam'], entry['questionId'], citation_index,
            entry['guideKey'], entry['nodeId'], entry['oldBlockId'],
        )
        if key in seen:
            raise BlockIdMigrationError(f'{label}: duplicate override')
        seen.add(key)
    return entries


class BlockIdMigration:
    """Loaded migration table + curated overrides bound to one content tree."""

    def __init__(
        self,
        table: dict[str, Any] | None,
        overrides: list[dict[str, Any]],
        content: dict[str, dict[str, list[dict[str, Any]]]],
    ) -> None:
        self.table = table
        self.overrides = overrides
        self.content = content
        self.block_ids: dict[tuple[str, str], set[str]] = {
            (guide, node): {str(block.get('id')) for block in blocks if block.get('id')}
            for guide, nodes in content.items()
            for node, blocks in nodes.items()
        }
        self.used_overrides: set[int] = set()
        self.auto_citations: dict[tuple[Any, ...], dict[str, Any]] = {}
        if table:
            for entry in table.get('citations') or []:
                key = (
                    entry['level'], entry['exam'], entry['questionId'], entry['citationIndex'],
                    entry['guideKey'], entry['nodeId'], entry['oldBlockId'],
                )
                if key in self.auto_citations:
                    raise BlockIdMigrationError(f'Duplicate auto-citation migration: {key}')
                self.auto_citations[key] = entry
            self._check_target_content()

    @classmethod
    def load(
        cls,
        *,
        table_path: Path = MIGRATIONS_PATH,
        overrides_path: Path = OVERRIDES_PATH,
        content_root: Path = DEFAULT_CONTENT_ROOT,
    ) -> 'BlockIdMigration':
        table = _load_optional_json(table_path)
        if table is not None:
            validate_table(table, table_path)
        overrides_payload = _load_optional_json(overrides_path)
        overrides = (
            validate_overrides(overrides_payload, overrides_path)
            if overrides_payload is not None else []
        )
        return cls(table, overrides, load_content_tree(content_root))

    # -- table freshness -------------------------------------------------
    def _check_target_content(self) -> None:
        assert self.table is not None
        expected = self.table['to'].get('guideSha256') or {}
        stale = [
            guide for guide, digest in sorted(expected.items())
            if guide_content_sha256(self.content.get(guide, {})) != digest
        ]
        if stale:
            raise BlockIdMigrationError(
                'Block-id migration table does not describe the current guideContent '
                f'(stale for {stale}); rerun scripts/build_guide_block_id_migrations.py '
                'after export_guide_outline_data.py'
            )

    def _in_scope(self, scope_name: str, scope_key: str, digest: str) -> bool:
        if not self.table:
            return False
        recorded = (self.table.get(scope_name) or {}).get(scope_key)
        if recorded is None:
            return False
        if recorded != digest:
            hint = (
                f'rebuild the table with --exclude-citation-scope {scope_key}'
                if scope_name == 'citationScope'
                else 'regenerate the table from the matching old ref'
            )
            raise BlockIdMigrationError(
                f'{scope_name}[{scope_key}] changed since the block-id migration table was built '
                f'(recorded {recorded}, current {digest}). If this input was regenerated against '
                f'the current content, {hint}; refusing to guess which ids are old'
            )
        return True

    def _block_entry(self, guide: str, node: str, old_id: str) -> dict[str, Any] | None:
        if not self.table:
            return None
        return ((self.table.get('blocks') or {}).get(guide) or {}).get(node, {}).get(old_id)

    def _override_for(
        self, level: str, exam: str, question_id: str, citation_index: int,
        guide: str, node: str, old_id: str,
    ) -> dict[str, Any] | None:
        matches = []
        for index, entry in enumerate(self.overrides):
            if (
                entry['level'] == level and entry['exam'] == exam
                and entry['questionId'] == question_id
                and entry['guideKey'] == guide and entry['nodeId'] == node
                and entry['oldBlockId'] == old_id
                and entry.get('citationIndex') in (None, citation_index)
            ):
                matches.append((entry.get('citationIndex') is None, index, entry))
        if not matches:
            return None
        matches.sort(key=lambda item: (item[0], item[1]))  # specific index wins
        _, index, entry = matches[0]
        self.used_overrides.add(index)
        return entry

    # -- reference answers ----------------------------------------------
    def migrate_reference_answers(
        self, level: str, exam: str, answers: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
        """Return answers whose citation block ids point at the current content."""
        in_scope = self._in_scope(
            'citationScope', f'{level}/{exam}', reference_answers_digest(answers)
        )
        stats = {'remapped': 0, 'removedBlockIds': 0, 'droppedCitations': 0, 'unchanged': 0}
        errors: list[str] = []
        migrated: dict[str, dict[str, Any]] = {}
        for question_id, answer in answers.items():
            new_answer = dict(answer)
            citations_out = []
            for citation_index, citation in enumerate(answer.get('citations') or []):
                source_guide = str(citation.get('guide_key') or '')
                node = str(citation.get('node_id') or '')
                guide = f'{level}-{source_guide}'
                valid = self.block_ids.get((guide, node))
                where = f'{level}/{exam}/{question_id}#citation{citation_index} {guide}/{node}'
                if not citation.get('block_ids'):
                    # Nothing to resolve (also how annotations treat it): keep as-is.
                    citations_out.append(citation)
                    continue
                if valid is None:
                    errors.append(f'{where}: node is not in the current guideContent')
                    continue
                new_ids: list[str] = []
                for old_id in citation.get('block_ids') or []:
                    old_id = str(old_id)
                    resolved = self._resolve_citation_block(
                        level, exam, question_id, citation_index, guide, node, old_id,
                        in_scope, where, errors,
                    )
                    if resolved is None:
                        stats['removedBlockIds'] += 1
                        continue
                    if resolved != [old_id]:
                        stats['remapped'] += 1
                    else:
                        stats['unchanged'] += 1
                    for new_id in resolved:
                        if new_id not in valid:
                            errors.append(
                                f'{where}: {old_id} resolves to {new_id}, which is not in the '
                                'current content (add a remap/remove override)'
                            )
                        elif new_id not in new_ids:
                            new_ids.append(new_id)
                if not new_ids:
                    # Every block id was removed by an override: drop this
                    # citation only; the question's other citations stay.
                    stats['droppedCitations'] += 1
                    continue
                if new_ids != list(citation.get('block_ids') or []):
                    citation = {**citation, 'block_ids': new_ids}
                citations_out.append(citation)
            if 'citations' in answer:
                new_answer['citations'] = citations_out
            migrated[question_id] = new_answer
        self._raise(errors)
        return migrated, stats

    def _resolve_citation_block(
        self, level: str, exam: str, question_id: str, citation_index: int,
        guide: str, node: str, old_id: str, in_scope: bool, where: str, errors: list[str],
    ) -> list[str] | None:
        override = self._override_for(level, exam, question_id, citation_index, guide, node, old_id)
        if override is not None:
            return None if override['action'] == 'remove' else list(override['newBlockIds'])
        if in_scope:
            auto = self.auto_citations.get(
                (level, exam, question_id, citation_index, guide, node, old_id)
            )
            if auto is not None:
                return list(auto['newBlockIds'])
            entry = self._block_entry(guide, node, old_id)
            if entry is not None:
                if entry['new'] is None:
                    errors.append(
                        f'{where}: {old_id} is unmapped in the migration table '
                        '(needs an auto-citation resolution or a remap/remove override)'
                    )
                    return [old_id]
                return [entry['new']]
        return [old_id]

    def check_unused_overrides(self, level: str, exams: Iterable[str]) -> None:
        exam_set = set(exams)
        unused = [
            f"{entry['level']}/{entry['exam']}/{entry['questionId']} {entry['guideKey']}/"
            f"{entry['nodeId']}/{entry['oldBlockId']}"
            for index, entry in enumerate(self.overrides)
            if entry['level'] == level and entry['exam'] in exam_set
            and index not in self.used_overrides
        ]
        self._raise([f'citation override matched nothing (stale?): {item}' for item in unused])

    # -- image units -----------------------------------------------------
    def migrate_heading_block_ids(
        self, units: list[dict[str, Any]], *, scope_key: str, digest: str,
    ) -> tuple[list[dict[str, Any]], int]:
        in_scope = self._in_scope('imageUnitsScope', scope_key, digest)
        errors: list[str] = []
        changed = 0
        result = []
        for unit in units:
            old_id = unit.get('headingBlockId')
            if not old_id:
                result.append(unit)
                continue
            guide = f"{unit.get('level')}-{unit.get('guideKey')}"
            node = str(unit.get('sourceNodeId') or '')
            where = f"image unit {unit.get('id')} {guide}/{node}"
            new_id = str(old_id)
            if in_scope:
                entry = self._block_entry(guide, node, new_id)
                if entry is not None:
                    if entry['new'] is None:
                        errors.append(f'{where}: headingBlockId {old_id} is unmapped')
                    else:
                        new_id = entry['new']
            valid = self.block_ids.get((guide, node))
            if valid is None:
                errors.append(f'{where}: node is not in the current guideContent')
            elif new_id not in valid:
                errors.append(f'{where}: headingBlockId {new_id} is not in the current content')
            if new_id != old_id:
                changed += 1
                unit = {**unit, 'headingBlockId': new_id}
            result.append(unit)
        self._raise(errors)
        return result, changed

    @staticmethod
    def _raise(errors: list[str]) -> None:
        if not errors:
            return
        shown = '\n'.join(f'- {item}' for item in errors[:MAX_REPORTED_ERRORS])
        more = '' if len(errors) <= MAX_REPORTED_ERRORS else f'\n... and {len(errors) - MAX_REPORTED_ERRORS} more'
        raise BlockIdMigrationError(
            f'{len(errors)} unresolved guide block reference(s):\n{shown}{more}'
        )
