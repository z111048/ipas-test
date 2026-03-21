interface FreqBarProps {
  frequency: '高' | '中' | '低'
}

const LEVEL = { '高': 3, '中': 2, '低': 1 } as const

export default function FreqBar({ frequency }: FreqBarProps) {
  const filled = LEVEL[frequency] ?? 1
  return (
    <span className="inline-flex items-center gap-1">
      {[1, 2, 3].map((n) => (
        <span
          key={n}
          className={`inline-block w-3 h-3 rounded-full border ${n <= filled ? 'bg-accent border-accent' : 'bg-transparent border-border'}`}
        />
      ))}
      <span className="ml-1 text-[0.82rem] text-text-light">{frequency}</span>
    </span>
  )
}
