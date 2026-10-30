import { Navigate, Route, Routes } from 'react-router-dom'
import RequireAuth from './components/RequireAuth'
import AppLayout from './layouts/AppLayout'
import AnalyticsPage from './pages/AnalyticsPage'
import DashboardPage from './pages/DashboardPage'
import ForecastPage from './pages/ForecastPage'
import InventoryPage from './pages/InventoryPage'
import LoginPage from './pages/LoginPage'
import ModelPage from './pages/ModelPage'
import ReordersPage from './pages/ReordersPage'
import SettingsPage from './pages/SettingsPage'
import SuppliersPage from './pages/SuppliersPage'

export default function App() {
  return <Routes><Route path="login" element={<LoginPage />} /><Route element={<RequireAuth />}><Route element={<AppLayout />}><Route index element={<DashboardPage />} /><Route path="inventory" element={<InventoryPage />} /><Route path="reorders" element={<ReordersPage />} /><Route path="suppliers" element={<SuppliersPage />} /><Route path="analytics" element={<AnalyticsPage />} /><Route path="forecast" element={<ForecastPage />} /><Route path="model" element={<ModelPage />} /><Route path="settings" element={<SettingsPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Route></Routes>
}
