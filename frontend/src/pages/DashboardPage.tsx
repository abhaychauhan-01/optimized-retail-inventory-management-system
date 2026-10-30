import { useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDownRight, ArrowRight, Boxes, CircleAlert, PackageCheck, RefreshCw, ShoppingCart } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import PageHeader from '../components/PageHeader'
import MetricTile from '../components/MetricTile'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { getInventoryAnalytics, getReorders, getSales, getSummary, getTransactions } from '../services/api'
import { useAsyncData } from '../hooks/useAsyncData'

const number = new Intl.NumberFormat('en-US')
const palette = ['#287c73', '#d2a24b', '#c65d4b']

export default function DashboardPage() {
  const load = useCallback(async () => {
    const [summary, inventory, sales, reorders, transactions] = await Promise.all([getSummary(), getInventoryAnalytics(), getSales(), getReorders(), getTransactions()])
    return { summary, inventory, sales, reorders, transactions }
  }, [])
  const { data, loading, error, retry } = useAsyncData(load)
  const summary = data?.summary ?? null
  const inventory = data?.inventory ?? null
  const sales = data?.sales ?? null
  const reorders = data?.reorders ?? []
  const transactions = data?.transactions ?? []
  const pieData = inventory ? [{ name: 'Healthy', value: inventory.status.healthy }, { name: 'Low', value: inventory.status.low }, { name: 'Out of stock', value: inventory.status.out }] : []

  return <>
    <PageHeader title="Operational overview" description="A clear view of current stock exposure and recorded activity." action={<button className="button button-secondary" onClick={retry}><RefreshCw size={15} /> Refresh</button>} />
    {error ? <ErrorState message={error} retry={retry} /> : loading || !summary || !inventory || !sales ? <LoadingState /> : <>
      <div className="metric-grid">
        <MetricTile label="Products tracked" value={number.format(summary.total_products)} note="Distinct product IDs" icon={Boxes} />
        <MetricTile label="Units on hand" value={number.format(summary.total_stock_units)} note="Current seeded inventory" icon={PackageCheck} tone="blue" />
        <MetricTile label="At or below threshold" value={number.format(summary.low_stock_products)} note="Includes out-of-stock items" icon={ArrowDownRight} tone="amber" />
        <MetricTile label="Out of stock" value={number.format(summary.out_of_stock_products)} note="Requires immediate review" icon={CircleAlert} tone="red" />
      </div>
      <div className="dashboard-grid">
        <section className="panel trend-panel">
          <div className="panel-heading"><div><h2>Recorded sales observations</h2><p>Sum of source `daily_sales` values by observation date</p></div><span className="mini-label">{summary.observation_dates} dates</span></div>
          {sales.timeline.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={sales.timeline} margin={{ top: 8, right: 14, left: -18, bottom: 0 }}><defs><linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#287c73" stopOpacity={0.19} /><stop offset="100%" stopColor="#287c73" stopOpacity={0.01} /></linearGradient></defs><CartesianGrid vertical={false} stroke="#e9eeeb" /><XAxis dataKey="date" tickFormatter={(value: string) => value.slice(5)} tickLine={false} axisLine={false} tick={{ fill: '#78817c', fontSize: 11 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#78817c', fontSize: 11 }} /><Tooltip labelFormatter={(value) => `Date: ${value}`} formatter={(value) => [`${number.format(Number(value))} units`, 'Recorded sales']} /><Area type="monotone" dataKey="recorded_sales_units" stroke="#287c73" strokeWidth={2} fill="url(#salesFill)" activeDot={{ r: 4 }} /></AreaChart></ResponsiveContainer></div> : <EmptyState title="No dated sales observations" detail="Import dated observations to see this chart." />}
        </section>
        <section className="panel status-panel">
          <div className="panel-heading"><div><h2>Stock status</h2><p>Compared with each product threshold</p></div><Link to="/inventory" className="icon-link" aria-label="View inventory"><ArrowRight size={17} /></Link></div>
          <div className="status-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={pieData} dataKey="value" nameKey="name" innerRadius={56} outerRadius={76} paddingAngle={3} stroke="none">{pieData.map((entry, index) => <Cell key={entry.name} fill={palette[index]} />)}</Pie><Tooltip formatter={(value) => [number.format(Number(value)), 'Products']} /></PieChart></ResponsiveContainer><div className="donut-center"><strong>{number.format(summary.total_products)}</strong><span>SKUs</span></div></div>
          <div className="legend-list">{pieData.map((item, index) => <div key={item.name}><span className="legend-key" style={{ backgroundColor: palette[index] }} />{item.name}<strong>{number.format(item.value)}</strong></div>)}</div>
        </section>
        <section className="panel table-panel">
          <div className="panel-heading"><div><h2>Replenishment queue</h2><p>Model-estimated demand with configurable policy · review before ordering</p></div><Link to="/reorders" className="inline-link">View all <ArrowRight size={14} /></Link></div>
          {reorders.length ? <div className="table-scroll"><table><thead><tr><th>Product</th><th>On hand</th><th>Reorder point</th><th>Suggested order</th><th>Status</th></tr></thead><tbody>{reorders.slice(0, 6).map((item) => <tr key={item.product_id}><td><Link className="sku-link" to={`/inventory?search=${item.product_id}`}>{item.product_id}</Link><span className="table-sub">{item.category}</span></td><td>{number.format(item.stock_qty)}</td><td>{number.format(item.reorder_point)}</td><td><strong>{number.format(item.recommended_quantity)}</strong> units</td><td><span className={`status-label ${item.stock_qty === 0 ? 'status-out' : 'status-low'}`}>{item.stock_qty === 0 ? 'Out of stock' : 'Reorder'}</span></td></tr>)}</tbody></table></div> : <EmptyState title="No replenishment items" detail="Products below the calculated point will appear here." />}
        </section>
        <section className="panel activity-panel">
          <div className="panel-heading"><div><h2>Recent stock movements</h2><p>Manually adjusted or received inventory</p></div><ShoppingCart size={17} className="muted-icon" /></div>
          {transactions.length ? <div className="activity-list">{transactions.slice(0, 5).map((item) => <div className="activity-row" key={item.id}><span className={`movement-mark ${item.quantity_delta > 0 ? 'movement-in' : 'movement-out'}`}>{item.quantity_delta > 0 ? '+' : ''}{item.quantity_delta}</span><div><strong>{item.product_id}</strong><span>{item.reason}</span></div><time>{new Date(item.created_at).toLocaleDateString()}</time></div>)}</div> : <EmptyState title="No movements recorded" detail="Stock adjustments and receipts will be listed here." />}
        </section>
      </div>
    </>}
  </>
}