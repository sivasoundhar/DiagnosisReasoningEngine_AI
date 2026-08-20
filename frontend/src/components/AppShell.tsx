import type { ReactNode } from 'react'
import { Activity, BarChart3, Brain, ClipboardList, History, Info, Library, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AppView } from '@/lib/views'

interface AppShellProps {
  children: ReactNode
  activeView: AppView
  onNavigate: (view: AppView) => void
}

/** Full nav from the reference sidebar mockup (UIS.png). Every item is a real page. */
const NAV_ITEMS: { view: AppView; label: string; icon: typeof Brain }[] = [
  { view: 'analyze', label: 'Analyze Patient', icon: Brain },
  { view: 'history', label: 'Patient History', icon: History },
  { view: 'library', label: 'Case Library', icon: Library },
  { view: 'analytics', label: 'Analytics', icon: BarChart3 },
  { view: 'settings', label: 'Settings', icon: Settings },
  { view: 'about', label: 'About', icon: Info },
]

/**
 * Sidebar-nav shell (Light Modern reference: indigo accents, left sidebar,
 * collapses to a top bar on small screens).
 */
export function AppShell({ children, activeView, onNavigate }: AppShellProps) {
  return (
    <div className="flex min-h-screen w-full flex-col bg-background lg:flex-row">
      <aside className="flex shrink-0 flex-col border-b border-sidebar-border bg-sidebar print:hidden lg:w-64 lg:border-r lg:border-b-0">
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
            <Brain className="size-5 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="truncate font-heading text-sm font-semibold text-sidebar-foreground">
              Diagnosis Reasoning Engine
            </p>
            <p className="truncate text-xs text-muted-foreground">
              AI-Powered Clinical Decision Support
            </p>
          </div>
        </div>

        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:overflow-visible lg:pb-0">
          {NAV_ITEMS.map(({ view, label, icon: Icon }) => {
            const active = view === activeView
            return (
              <button
                key={label}
                type="button"
                onClick={() => onNavigate(view)}
                className={cn(
                  'flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  active
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                <Icon className="size-4" />
                <span className="whitespace-nowrap">{label}</span>
              </button>
            )
          })}
        </nav>

        <div className="mt-auto hidden px-5 py-4 lg:block">
          <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2.5 text-xs text-muted-foreground">
            <Activity className="size-3.5 text-emerald-600" />
            <span className="font-medium text-foreground">All Systems Operational</span>
          </div>
          <p className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <ClipboardList className="size-3" />
            Powered by LangGraph + FastAPI
          </p>
        </div>
      </aside>

      <main className="min-w-0 flex-1">{children}</main>
    </div>
  )
}
