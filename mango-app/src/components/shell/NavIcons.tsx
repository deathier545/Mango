import type { ReactNode, SVGProps } from 'react'
import type { AppZone } from '../../types/ui'

type IconProps = SVGProps<SVGSVGElement>

function IconBase({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width={20} height={20} fill="none" stroke="currentColor" strokeWidth={1.75} {...props}>
      {children}
    </svg>
  )
}

export function IconCommand(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4 6h16M4 12h10M4 18h14" strokeLinecap="round" />
    </IconBase>
  )
}

export function IconSmart(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" strokeLinejoin="round" />
      <path d="M5 19h14" strokeLinecap="round" />
    </IconBase>
  )
}

export function IconDiagnostics(props: IconProps) {
  return (
    <IconBase {...props}>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M8 14l3-3 2 2 5-6" strokeLinecap="round" strokeLinejoin="round" />
    </IconBase>
  )
}

export function IconConfig(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="12" cy="12" r="3" />
      <path
        d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
        strokeLinecap="round"
      />
    </IconBase>
  )
}

const ZONE_ICONS: Record<AppZone, (props: IconProps) => ReactNode> = {
  command: IconCommand,
  intelligence: IconSmart,
  diagnostics: IconDiagnostics,
  config: IconConfig,
}

export function ZoneIcon({ zone, ...props }: IconProps & { zone: AppZone }) {
  const Cmp = ZONE_ICONS[zone]
  return <Cmp {...props} />
}
