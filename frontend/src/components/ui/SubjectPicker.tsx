import type { ReactNode } from 'react'
import { resourceLevels } from '../../data/resourceRegistry'
import type { ResourceLevelId } from '../../data/resourceCatalog'
import { formatSubjectLabel } from '../../constants/navLabels'
import Chip, { ChipGroup } from './Chip'

/**
 * Subjects and levels come only from toc_manifest via resourceLevels
 * (CLAUDE.md 不變量 1 — never hard-code subject arrays in pages).
 */
export interface SubjectOption {
  /** Subject id from toc_manifest, e.g. 's1', 'mid-s2'. */
  id: string
  levelId: ResourceLevelId
  /** 「初級」/「中級」 */
  levelLabel: string
  /** 「初級・科目一」 */
  label: string
  /** 「人工智慧基礎概論」 */
  name: string
  /** 「初級・科目一：人工智慧基礎概論」 */
  fullLabel: string
}

export interface LevelOption {
  id: ResourceLevelId
  label: string
}

export function levelOptions(): LevelOption[] {
  return resourceLevels.map((level) => ({ id: level.id, label: level.label }))
}

/** All subjects in manifest order, optionally narrowed by level and/or an id whitelist. */
export function subjectOptions(filter?: {
  levels?: readonly ResourceLevelId[]
  subjectIds?: readonly string[]
}): SubjectOption[] {
  const allowed = filter?.subjectIds ? new Set(filter.subjectIds) : null
  return resourceLevels
    .filter((level) => !filter?.levels || filter.levels.includes(level.id))
    .flatMap((level) =>
      level.subjects
        .filter((subject) => !allowed || allowed.has(subject.id))
        .map((subject) => {
          const parts = formatSubjectLabel(level.label, subject.label)
          return {
            id: subject.id,
            levelId: level.id,
            levelLabel: level.label,
            label: parts.short,
            name: parts.name,
            fullLabel: parts.full,
          }
        }),
    )
}

/** Lookup by subject id (e.g. for headings / result lines). */
export function subjectOptionById(subjectId: string): SubjectOption | undefined {
  return subjectOptions().find((option) => option.id === subjectId)
}

export interface SubjectPickerProps {
  /** Group label (visible above the row unless labelHidden). */
  label?: string
  labelHidden?: boolean
  /** Selected subject id, or the allOption value, or null for none. */
  value: string | null
  /** Button mode: called with the subject id (or allOption.value). */
  onChange?: (subjectId: string) => void
  /** Link mode: when given, chips are <Link>s (state in the URL). */
  hrefFor?: (subjectId: string) => string
  /** Restrict to these levels. */
  levels?: readonly ResourceLevelId[]
  /** Restrict to these subject ids (e.g. subjects that have a guide); order follows the manifest. */
  subjectIds?: readonly string[]
  /** Leading 「全部」 chip, e.g. { value: 'all', label: '全部科目' }. */
  allOption?: { value: string; label: string }
  /** short: 「初級・科目一」 (name in tooltip). full: 「初級・科目一：人工智慧基礎概論」. */
  display?: 'short' | 'full'
  /** Optional trailing count per subject id (and allOption.value). */
  counts?: Record<string, ReactNode>
  /** Subject ids rendered disabled. */
  disabledIds?: readonly string[]
  className?: string
}

/**
 * Single-select subject chip row. Same look on every page: 「初級・科目一」 chips,
 * wraps on desktop, scrolls horizontally on mobile, 44px targets on touch.
 */
export default function SubjectPicker({
  label = '科目',
  labelHidden = false,
  value,
  onChange,
  hrefFor,
  levels,
  subjectIds,
  allOption,
  display = 'short',
  counts,
  disabledIds,
  className = '',
}: SubjectPickerProps) {
  const options = subjectOptions({ levels, subjectIds })
  const disabled = new Set(disabledIds ?? [])

  return (
    <ChipGroup label={label} labelHidden={labelHidden} className={className}>
      {allOption && (
        <Chip
          active={value === allOption.value}
          to={hrefFor?.(allOption.value)}
          onClick={hrefFor ? undefined : () => onChange?.(allOption.value)}
          count={counts?.[allOption.value]}
        >
          {allOption.label}
        </Chip>
      )}
      {options.map((option) => (
        <Chip
          key={option.id}
          active={value === option.id}
          to={hrefFor?.(option.id)}
          onClick={hrefFor ? undefined : () => onChange?.(option.id)}
          disabled={disabled.has(option.id)}
          count={counts?.[option.id]}
          title={display === 'short' ? option.fullLabel : undefined}
        >
          {display === 'full' ? option.fullLabel : option.label}
        </Chip>
      ))}
    </ChipGroup>
  )
}

export interface LevelPickerProps {
  label?: string
  labelHidden?: boolean
  /** Selected level id (「junior」), level label (「初級」) or allOption.value. */
  value: ResourceLevelId | string | null
  /** Called with the level id, or with allOption.value for the 「全部」 chip. */
  onChange?: (levelId: ResourceLevelId | string) => void
  hrefFor?: (levelId: ResourceLevelId | string) => string
  /** Leading 「全部」 chip, e.g. { value: 'all', label: '全部級別' }. */
  allOption?: { value: string; label: string }
  /** Optional trailing count per level id (and allOption.value). */
  counts?: Record<string, ReactNode>
  className?: string
}

/** Level chip row (初級 / 中級) with the same chip style as SubjectPicker. */
export function LevelPicker({
  label = '級別',
  labelHidden = false,
  value,
  onChange,
  hrefFor,
  allOption,
  counts,
  className = '',
}: LevelPickerProps) {
  return (
    <ChipGroup label={label} labelHidden={labelHidden} className={className}>
      {allOption && (
        <Chip
          active={value === allOption.value}
          to={hrefFor?.(allOption.value)}
          onClick={hrefFor ? undefined : () => onChange?.(allOption.value)}
          count={counts?.[allOption.value]}
        >
          {allOption.label}
        </Chip>
      )}
      {levelOptions().map((level) => (
        <Chip
          key={level.id}
          active={value === level.id || value === level.label}
          to={hrefFor?.(level.id)}
          onClick={hrefFor ? undefined : () => onChange?.(level.id)}
          count={counts?.[level.id]}
        >
          {level.label}
        </Chip>
      ))}
    </ChipGroup>
  )
}
