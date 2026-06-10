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
      onClick={handleCopy}
      className="text-xs px-2 py-0.5 rounded bg-white/70 hover:bg-white border border-gray-200 text-gray-500 transition-colors"
      aria-label="複製程式碼"
    >
      {copied ? '已複製 ✓' : '複製'}
    </button>
  )
}

function MarkdownCell({ cell }: { cell: ColabCell }) {
  return (
    <div className="prose prose-sm max-w-none text-gray-700 py-2">
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
      <div
        className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-100 cursor-pointer select-none"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-gray-400 font-mono text-xs shrink-0">
            [{index + 1}]
          </span>
          {cell.title && (
            <span className="text-sm font-medium text-gray-700 truncate">
              {cell.title}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {open && <CopyButton code={cell.content} />}
          <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
        </div>
      </div>

      {open && (
        <>
          {/* Explanation */}
          {cell.explanation && (
            <div className="px-4 py-2 bg-blue-50 border-b border-blue-100 text-sm text-blue-800">
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
                fontSize: '0.8rem',
                background: '#fafafa',
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
      <button
        className="w-full flex items-center justify-between px-4 py-3 bg-emerald-50 hover:bg-emerald-100 transition-colors text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">⚗️</span>
          <span className="font-semibold text-emerald-800">實作練習</span>
          <span className="text-xs text-emerald-600 bg-emerald-100 px-2 py-0.5 rounded-full">
            {notebook.cells.filter((c) => c.type === 'code').length} 個程式碼範例
          </span>
          {notebook.status === 'warn' && (
            <span className="text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
              ⚠ 部分內容待審查
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <a
            href={notebook.colab_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-xs font-medium px-3 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-500 text-white transition-colors flex items-center gap-1.5"
          >
            <img
              src="https://colab.research.google.com/assets/colab-badge.svg"
              alt="Open in Colab"
              className="h-4"
              loading="lazy"
            />
          </a>
          <span className="text-emerald-600 text-sm">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

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
