export interface Product {
  product_id: string
  category: string
  stock_qty: number
  reorder_level: number
  daily_sales: number
  supplier_id: string | null
  lead_days: number
  unit_cost?: number | null
  updated_at: string
}

export interface ProductPageData {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export interface Supplier {
  supplier_id: string
  contact_name: string | null
  email: string | null
  phone: string | null
  lead_days: number
  products_count?: number
}

export interface Reorder {
  product_id: string
  category: string
  stock_qty: number
  daily_sales: number
  daily_sales_estimate: number
  lead_days: number
  safety_stock: number
  expected_lead_demand: number
  reorder_point: number
  target_stock: number
  recommended_quantity: number
  supplier_id: string | null
  method: string
}

export interface Summary {
  total_products: number
  total_stock_units: number
  low_stock_products: number
  out_of_stock_products: number
  latest_recorded_daily_sales_units: number
  observation_dates: number
  latest_observation_date: string | null
}

export interface SalesAnalytics {
  available: boolean
  source_label: string
  timeline: { date: string; recorded_sales_units: number; observation_rows: number }[]
  top_products: { product_id: string; recorded_sales_units: number }[]
}

export interface InventoryAnalytics {
  products: number
  categories: { category: string; products: number; stock_units: number; low_stock: number }[]
  status: { healthy: number; low: number; out: number }
}

export interface ModelStatus {
  trained_model_available: boolean
  model_name: string | null
  prediction_target: string
  training_timestamp: string | null
  dataset_source: string | null
  dataset_type?: string
  category_options?: string[]
  season_options?: string[]
  message?: string | null
}

export interface ModelMetrics {
  trained_model_available: boolean
  model_name: string
  prediction_target: string
  training_timestamp: string
  dataset_source: string
  dataset_type: string
  mae: number | null
  rmse: number | null
  r2: number | null
  training_observations: number
  evaluation_observations: number
  training_date_range: { start: string; end: string }
  testing_date_range: { start: string; end: string }
  features: string[]
  original_observations: number
  synthetic_observations: number
  total_observations: number
  products: number
  date_min: string
  date_max: string
  duplicate_product_date_excess_rows: number
  duplicate_product_date_participating_rows?: number
  validation_method: string
  synthetic_data_limitation: string
}

export interface DailySalesPredictionInput {
  date: string
  category: string
  season: string
  stock_qty: number
  reorder_level: number
  unit_cost: number
  lead_days: number
}

export interface DailySalesPrediction {
  predicted_daily_sales: number
  model_name: string
  training_timestamp: string
  prediction_target: string
  status: string
}

export interface AuthUser {
  id: number
  email: string
  is_admin: boolean
}