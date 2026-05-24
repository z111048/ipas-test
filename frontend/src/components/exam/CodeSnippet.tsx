import type React from 'react'

const PYTHON_KEYWORDS = new Set([
  'False',
  'None',
  'True',
  'and',
  'as',
  'class',
  'def',
  'else',
  'for',
  'from',
  'if',
  'import',
  'in',
  'is',
  'lambda',
  'not',
  'or',
  'return',
  'while',
  'with',
])

const TOKEN_RE = /("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#.*|\b\d+(?:\.\d+)?\b|\b[A-Za-z_][A-Za-z0-9_]*\b)/g

function tokenClass(token: string, language?: string) {
  if (token.startsWith('#')) return 'text-[#6a737d] italic'
  if (
    (token.startsWith('"') && token.endsWith('"')) ||
    (token.startsWith("'") && token.endsWith("'"))
  ) {
    return 'text-[#0a7f4f]'
  }
  if (/^\d/.test(token)) return 'text-[#8a4baf]'
  if (language === 'python' && PYTHON_KEYWORDS.has(token)) return 'text-[#b42318] font-semibold'
  if (/^[A-Z][A-Za-z0-9_]*$/.test(token)) return 'text-[#075985]'
  return ''
}

function highlightLine(line: string, language?: string) {
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  for (const match of line.matchAll(TOKEN_RE)) {
    const token = match[0]
    const index = match.index ?? 0
    if (index > lastIndex) parts.push(line.slice(lastIndex, index))
    const className = tokenClass(token, language)
    parts.push(
      <span key={`${index}-${token}`} className={className || undefined}>
        {token}
      </span>,
    )
    lastIndex = index + token.length
  }
  if (lastIndex < line.length) parts.push(line.slice(lastIndex))
  return parts
}

interface CodeSnippetProps {
  code: string
  language?: string
}

export default function CodeSnippet({ code, language }: CodeSnippetProps) {
  return (
    <pre className="max-h-[360px] overflow-auto whitespace-pre px-3 pb-3 font-mono text-[0.78rem] leading-relaxed text-[#1f2937]">
      <code>
        {code.split('\n').map((line, index) => (
          <span key={index} className="block min-h-[1.15rem]">
            {highlightLine(line, language)}
          </span>
        ))}
      </code>
    </pre>
  )
}
