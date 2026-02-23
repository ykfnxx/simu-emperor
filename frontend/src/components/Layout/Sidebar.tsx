import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Map,
  Users,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useUIStore } from '../../stores/uiStore'

const navItems = [
  { to: '/', label: '龙椅', icon: LayoutDashboard },
  { to: '/provinces', label: '疆域', icon: Map },
  { to: '/agents', label: '百官', icon: Users },
]

export function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  return (
    <aside
      className={`bg-amber-900 text-amber-50 flex flex-col transition-all duration-300 ${
        sidebarCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-amber-800">
        {!sidebarCollapsed && (
          <h1 className="text-lg font-bold">皇帝模拟器</h1>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1 hover:bg-amber-800 rounded"
        >
          {sidebarCollapsed ? (
            <ChevronRight size={20} />
          ) : (
            <ChevronLeft size={20} />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded mb-1 transition-colors ${
                isActive
                  ? 'bg-amber-700 text-white'
                  : 'hover:bg-amber-800 text-amber-200'
              }`
            }
          >
            <Icon size={20} />
            {!sidebarCollapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      {!sidebarCollapsed && (
        <div className="p-4 border-t border-amber-800 text-xs text-amber-400">
          <p>回合制模拟</p>
        </div>
      )}
    </aside>
  )
}
