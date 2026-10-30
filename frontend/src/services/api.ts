import axios from 'axios'
import type { AuthUser, DailySalesPrediction, DailySalesPredictionInput, InventoryAnalytics, ModelMetrics, ModelStatus, Product, ProductPageData, Reorder, SalesAnalytics, Summary, Supplier } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1',
  timeout: 15000,
  withCredentials: true,
})

api.interceptors.response.use((response) => response, (error: unknown) => {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    const url = error.config?.url ?? ''
    if (!url.includes('/auth/login') && !url.includes('/auth/me')) {
      window.dispatchEvent(new Event('auth:expired'))
    }
  }
  return Promise.reject(error)
})

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    return typeof detail === 'string' ? detail : error.message
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}

export const isUnauthorizedError = (error: unknown) => axios.isAxiosError(error) && error.response?.status === 401

export const getSummary = () => api.get<Summary>('/dashboard/summary').then((r) => r.data)
export const authLogin = (email: string, password: string) => api.post<{ user: AuthUser }>('/auth/login', { email, password }).then((r) => r.data.user)
export const authLogout = () => api.post<{ logged_out: boolean }>('/auth/logout').then((r) => r.data)
export const getCurrentUser = () => api.get<AuthUser>('/auth/me').then((r) => r.data)
export const getSales = () => api.get<SalesAnalytics>('/analytics/sales').then((r) => r.data)
export const getInventoryAnalytics = () => api.get<InventoryAnalytics>('/analytics/inventory').then((r) => r.data)
export const getReorders = () => api.get<Reorder[]>('/reorders').then((r) => r.data)
export const getProducts = (params: Record<string, string | number | undefined> = {}) => api.get<ProductPageData>('/products', { params }).then((r) => r.data)
export const getAllProducts = () => api.get<ProductPageData>('/products', { params: { page_size: 100 } }).then((r) => r.data.items)
export const getSuppliers = (search?: string) => api.get<Supplier[]>('/suppliers', { params: { search } }).then((r) => r.data)
export const getModelStatus = () => api.get<ModelStatus>('/model/status').then((r) => r.data)
export const getModelMetrics = () => api.get<ModelMetrics>('/model/metrics').then((r) => r.data)
export const predictDailySales = (data: DailySalesPredictionInput) => api.post<DailySalesPrediction>('/model/predict', data).then((r) => r.data)
export const getTransactions = () => api.get<{ id: number; product_id: string; quantity_delta: number; reason: string; created_at: string }[]>('/transactions').then((r) => r.data)
export const createProduct = (data: Omit<Product, 'updated_at'>) => api.post<Product>('/products', data).then((r) => r.data)
export const updateProduct = (id: string, data: Omit<Product, 'updated_at'>) => api.put<Product>(`/products/${id}`, data).then((r) => r.data)
export const deleteProduct = (id: string) => api.delete(`/products/${id}`)
export const adjustStock = (id: string, quantity_delta: number, reason: string) => api.post(`/products/${id}/stock-adjustments`, { quantity_delta, reason })
export const saveSupplier = (data: Supplier, editing: boolean) => api[editing ? 'put' : 'post'](editing ? `/suppliers/${data.supplier_id}` : '/suppliers', data).then((r) => r.data)
export const createPurchaseOrder = (supplier_id: string, product_id: string, quantity: number) => api.post('/purchase-orders', { supplier_id, items: [{ product_id, quantity }] })
export const getForecast = (id: string, horizon_days: number) => api.get(`/forecasts/${id}`, { params: { horizon_days } }).then((r) => r.data)
export const getSettings = () => api.get<{ safety_stock_rate: number; replenishment_horizon_days: number }>('/settings').then((r) => r.data)
export const putSettings = (data: { safety_stock_rate: number; replenishment_horizon_days: number }) => api.put('/settings', data).then((r) => r.data)
export const previewImport = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/imports/preview', form).then((r) => r.data)
}
export const confirmImport = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/imports/confirm', form).then((r) => r.data)
}
export const inventoryExportUrl = `${api.defaults.baseURL}/exports/inventory.csv`