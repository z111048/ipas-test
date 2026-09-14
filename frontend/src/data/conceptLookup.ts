/**
 * `/concepts?c=` 的解析（LP-210C）。
 *
 * 網址參數在 LP-210C 之前放的是中文名稱，之後放詞彙表的穩定 id。兩種都要能解析到同一概念，
 * 解析順序是**嚴格分段**的：id → 目前正式名稱 → 帳本裡的舊正式名稱（previousNames）。
 * 三段不能合成一次 `find`：兩個概念互換名字時，排在前面那個的 previousNames 會蓋過排在後面
 * 那個的正式名稱，舊連結就會指到錯的概念（topic-id-migration.md §9.2 列的情境）。
 *
 * 相容期：維護者於 2026-09-14 裁決「保留一段時間」，到期日 **2026-12-31**（topic-id-migration.md §10.4，
 * 日期只寫在那一節與這裡）。到期後刪掉 `resolveByLegacyName`、讓 `resolveConcept` 只剩 id 那一段，
 * 並依 §10.4 調整 tests/test_routes.py 與 tests/frontend_checks/concept_lookup_check.cjs 的預期。
 *
 * 這個檔刻意不含 JSX、不 import 任何東西：tests/frontend_checks/concept_lookup_check.cjs 會轉譯後直接執行它。
 */

export interface ConceptIdentity {
  /** 詞彙表的穩定 id（`topic-<8 hex>`） */
  id: string
  /** 目前的正式名稱 */
  name: string
  /** id 指派帳本裡的舊正式名稱 */
  previousNames: string[]
}

/** 舊形式：目前正式名稱優先，其次才是任何概念的舊名稱。 */
export function resolveByLegacyName<T extends ConceptIdentity>(concepts: readonly T[], value: string): T | null {
  const current = concepts.find((concept) => concept.name === value)
  if (current) return current
  return concepts.find((concept) => concept.previousNames.includes(value)) ?? null
}

/**
 * `?c=` 的值 → 概念。空值回 null；id 命中優先於任何名稱。
 * 回傳值的 `id` 與參數不同時，呼叫端應把網址改寫成 id 形式。
 */
export function resolveConcept<T extends ConceptIdentity>(concepts: readonly T[], requested: string): T | null {
  if (!requested) return null
  return concepts.find((concept) => concept.id === requested) ?? resolveByLegacyName(concepts, requested)
}
