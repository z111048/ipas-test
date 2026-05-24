const viteBase = import.meta.env.BASE_URL || '/'

function inferredPathBase() {
  if (typeof window === 'undefined') return ''
  const firstSegment = window.location.pathname.split('/').filter(Boolean)[0]
  return firstSegment ? `/${firstSegment}` : ''
}

export function publicAsset(path: string) {
  const cleanPath = path.replace(/^\/+/, '')
  const configuredBase = viteBase.replace(/\/$/, '')
  const base = configuredBase && configuredBase !== '/' ? configuredBase : inferredPathBase()
  return base ? `${base}/${cleanPath}` : `/${cleanPath}`
}
