import type { RefObject } from 'react'
import type { FeedDisplayItem, FeedFilter, FeedToolItem } from '../../hooks/useUnifiedFeed'
import { UnifiedFeed } from './UnifiedFeed'

type CommandViewProps = {
  items: FeedDisplayItem[]
  feedRef: RefObject<HTMLDivElement | null>
  filter: FeedFilter
  onFilter: (filter: FeedFilter) => void
  onClearTyped: () => void
  onClearAll: () => void
  onScroll: (el: HTMLDivElement) => void
  onToolClick?: (item: FeedToolItem) => void
  running: boolean
  onStart: () => void
  startPending: boolean
}

export function CommandView(props: CommandViewProps) {
  return (
    <div className="zoneView commandView">
      <UnifiedFeed {...props} />
    </div>
  )
}
