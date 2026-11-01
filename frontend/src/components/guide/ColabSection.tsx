import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import type { ColabNotebook, ColabCell } from '../../types'

interface Props {
  notebook: ColabNotebook
}

function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation()
        handleCopy()
      }}
      className="btn-outline btn-sm"
      aria-label="複製程式碼"
    >
      {copied ? '已複製 ✓' : '複製'}
    </button>
  )
}

function MarkdownCell({ cell }: { cell: ColabCell }) {
  return (
    <div className="prose max-w-none text-body text-app-text py-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
      >
        {cell.content}
      </ReactMarkdown>
    </div>
  )
}

function CodeCell({ cell, index }: { cell: ColabCell; index: number }) {
  const [open, setOpen] = useState(true)

  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden bg-white">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 px-3 py-1 bg-unanswered-soft border-b border-border">
        <button
          type="button"
          className="flex min-h-11 min-w-0 flex-1 items-center gap-2 text-left md:min-h-9"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          <span className="text-text-light font-mono text-caption shrink-0">
            [{index + 1}]
          </span>
          {cell.title && (
            <span className="text-ui font-medium text-app-text truncate">
              {cell.title}
            </span>
          )}
          <span className="ml-auto text-text-light text-caption" aria-hidden="true">{open ? '▲' : '▼'}</span>
        </button>
        {open && <CopyButton code={cell.content} />}
      </div>

      {open && (
        <>
          {/* Explanation */}
          {cell.explanation && (
            <div className="px-4 py-2 bg-answered-soft border-b border-answered-line text-ui text-answered">
              💡 {cell.explanation}
            </div>
          )}

          {/* Code */}
          <div className="overflow-x-auto text-sm">
            <SyntaxHighlighter
              language="python"
              style={oneLight}
              customStyle={{
                margin: 0,
                borderRadius: 0,
                fontSize: '0.875rem',
                background: 'var(--color-unanswered-soft)',
                padding: '1rem',
              }}
              showLineNumbers
              wrapLongLines={false}
            >
              {cell.content}
            </SyntaxHighlighter>
          </div>
        </>
      )}
    </div>
  )
}

export default function ColabSection({ notebook }: Props) {
  const [expanded, setExpanded] = useState(false)

  let codeIndex = 0

  return (
    <div className="mt-8 border border-emerald-200 rounded-xl overflow-hidden">
      {/* Section header */}
      <div className="flex items-center gap-2 bg-emerald-50 pr-3">
        <button
          type="button"
          className="flex min-h-11 flex-1 items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-emerald-100"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-lg" aria-hidden="true">⚗️</span>
            <span className="font-semibold text-emerald-800">實作練習</span>
            <span className="badge badge-correct">
              {notebook.cells.filter((c) => c.type === 'code').length} 個程式碼範例
            </span>
            {notebook.status === 'warn' && (
              <span className="badge badge-warning">
                ⚠ 部分內容待審查
              </span>
            )}
          </span>
          <span className="text-emerald-700 text-ui" aria-hidden="true">{expanded ? '▲' : '▼'}</span>
        </button>
        <a
          href={notebook.colab_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-lg px-2 transition-colors hover:bg-white md:min-h-9"
        >
          <img
            src="https://colab.research.google.com/assets/colab-badge.svg"
            alt="在 Colab 開啟"
            className="h-4"
            loading="lazy"
          />
        </a>
      </div>

      {/* Content */}
      {expanded && (
        <div className="p-4 space-y-4 bg-white">
          {notebook.cells.map((cell, i) => {
            if (cell.type === 'markdown') {
              return <MarkdownCell key={i} cell={cell} />
            }
            const idx = codeIndex++
            return <CodeCell key={i} cell={cell} index={idx} />
          })}
        </div>
      )}
    </div>
  )
}
