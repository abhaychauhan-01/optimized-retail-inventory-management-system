import { useCallback } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import PageHeader from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { getInventoryAnalytics, getSales } from '../services/api'
import { useAsyncData } from '../hooks/useAsyncData'

const fmt = new Intl.NumberFormat('en-US')

export default function AnalyticsPage() {
  const load = useCallback(async () => {
    const [sales, inventory] = await Promise.all([getSales(), getInventoryAnalytics()])
    return { sales, inventory }
  }, [])
  const { data, loading, error, retry } = useAsyncData(load)
  const sales = data?.sales ?? null
  const inventory = data?.inventory ?? null

  return <>
    <PageHeader title="Sales analytics" description="Explore recorded sales values and current inventory distribution." />
    {error ? <ErrorState message={error} retry={retry} /> : loading || !sales || !inventory ? <LoadingState /> : <>
      <div className="analytics-summary"><div><span>Observation dates</span><strong>{sales.timeline.length}</strong></div><div><span>Recorded observation units</span><strong>{fmt.format(sales.timeline.reduce((sum, item) => sum + item.recorded_sales_units, 0))}</strong></div><div><span>Source observation rows</span><strong>{fmt.format(sales.timeline.reduce((sum, item) => sum + item.observation_rows, 0))}</strong></div></div>
      <section className="panel chart-panel"><div className="panel-heading"><div><h2>Recorded values by date</h2><p>Sum of the observed `daily_sales` field for rows on each date</p></div></div>{sales.timeline.length ? <div className="chart-wrap chart-large"><ResponsiveContainer width="100%" height="100%"><BarChart data={sales.timeline} margin={{ top: 8, right: 20, left: -12, bottom: 4 }}><CartesianGrid vertical={false} stroke="#e9eeeb" /><XAxis dataKey="date" tickFormatter={(value: string) => value.slice(5)} tickLine={false} axisLine={false} tick={{ fill: '#78817c', fontSize: 11 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#78817c', fontSize: 11 }} /><Tooltip formatter={(value) => [`${fmt.format(Number(value))} units`, 'Recorded sales']} /><Bar dataKey="recorded_sales_units" fill="#287c73" radius={[2, 2, 0, 0]} maxBarSize={32} /></BarChart></ResponsiveContainer></div> : <EmptyState title="No dated sales data" detail="Import valid dated observations to populate this analysis." />}</section>
      <div className="dashboard-grid analytics-grid"><section className="panel"><div className="panel-heading"><div><h2>Category inventory</h2><p>Current SKU and stock totals</p></div></div><div className="table-scroll"><table><thead><tr><th>Category</th><th>Products</th><th>Stock units</th><th>Low stock</th></tr></thead><tbody>{inventory.categories.map((row) => <tr key={row.category}><td><strong>{row.category}</strong></td><td>{fmt.format(row.products)}</td><td>{fmt.format(row.stock_units)}</td><td>{fmt.format(row.low_stock)}</td></tr>)}</tbody></table></div></section><section className="panel"><div className="panel-heading"><div><h2>Top recorded sales values</h2><p>Sum across available source observations per product</p></div></div>{sales.top_products.length ? <div className="rank-list">{sales.top_products.map((item, index) => <div key={item.product_id}><span className="rank-number">{String(index + 1).padStart(2, '0')}</span><strong>{item.product_id}</strong><span>{fmt.format(item.recorded_sales_units)} units</span></div>)}</div> : <EmptyState title="No product observations" detail="Import dated records to populate rankings." />}</section></div>
    </>}
  </>
}