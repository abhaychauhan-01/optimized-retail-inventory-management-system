import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Activity, Boxes, ChartNoAxesCombined, ClipboardList, Gauge, LogOut, Settings2, Truck, WandSparkles } from 'lucide-react'
import { useAuth } from '../context/useAuth'
import { errorMessage } from '../services/api'

const navigation = [
  { label: 'Overview', to: '/', icon: Gauge },
  { label: 'Inventory', to: '/inventory', icon: Boxes },
  { label: 'Replenishment', to: '/reorders', icon: ClipboardList },
  { label: 'Suppliers', to: '/suppliers', icon: Truck },
  { label: 'Sales analytics', to: '/analytics', icon: ChartNoAxesCombined },
  { label: 'Demand estimate', to: '/forecast', icon: Activity },
  { label: 'Model performance', to: '/model', icon: WandSparkles },
  { label: 'Data & settings', to: '/settings', icon: Settings2 },
]

const titles: Record<string, string> = {
  '/': 'Operational overview',
  '/inventory': 'Inventory',
  '/reorders': 'Replenishment',
  '/suppliers': 'Suppliers',
  '/analytics': 'Sales analytics',
  '/forecast': 'Demand estimate',
  '/model': 'Model performance',
  '/settings': 'Data & settings',
}

export default function AppLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const [logoutError, setLogoutError] = useState('')
  const currentTitle = titles[location.pathname] ?? 'Inventory'

  async function handleSignOut() {
    setLogoutError('')
    try {
      await signOut()
      navigate('/login', { replace: true })
    } catch (reason) {
      setLogoutError(errorMessage(reason))
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><Boxes size={19} strokeWidth={2.2} /></div>
          <div><strong>Stockroom</strong><span>RETAIL OPERATIONS</span></div>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map(({ label, to, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="status-dot" />
          <div><strong>Local workspace</strong><span>SQLite · connected</span></div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-crumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>{currentTitle}</strong></div>
          <div className="topbar-right"><span className="dataset-tag"><span className="dataset-dot" /> Official dataset</span><span className="auth-user-email">{user?.email}</span><div className="avatar" aria-label={`Signed in as ${user?.email ?? 'user'}`}>{user?.email.slice(0, 2).toUpperCase() ?? 'US'}</div><button className="icon-button" type="button" title="Sign out" aria-label="Sign out" onClick={() => { void handleSignOut() }}><LogOut size={16} /></button>{logoutError ? <span className="auth-inline-error" role="alert">{logoutError}</span> : null}</div>
        </header>
        <main className="page-content"><Outlet /></main>
        <footer className="app-footer"><span>Stockroom Inventory</span><span>HCLTech Career Shaper · Project 21</span></footer>
      </div>
    </div>
  )
}