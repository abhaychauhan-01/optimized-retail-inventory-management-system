import { useCallback, useState } from 'react'
import { ShoppingCart } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { errorMessage, createPurchaseOrder, getReorders, getSuppliers } from '../services/api'
import type { Reorder } from '../types'
import { useAsyncData } from '../hooks/useAsyncData'

export default function ReordersPage() {
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const [ordering, setOrdering] = useState('')

  const load = useCallback(async () => {
    const [items, suppliers] = await Promise.all([getReorders(), getSuppliers()])
    return { items, suppliers }
  }, [])
  const { data, loading, error, retry } = useAsyncData(load)
  const items = data?.items ?? []
  const suppliers = data?.suppliers ?? []
  const pageError = actionError || error

  const order = async (item: Reorder) => {
    const supplier = item.supplier_id ?? suppliers.find((entry) => entry.lead_days === item.lead_days)?.supplier_id
    if (!supplier) { setActionError(`No supplier is assigned to ${item.product_id}. Assign one in Inventory before creating an order.`); return }
    if (item.recommended_quantity < 1) { setActionError('The recommended quantity is zero; no order was created.'); return }
    setOrdering(item.product_id); setActionError('')
    try { await createPurchaseOrder(supplier, item.product_id, item.recommended_quantity); setNotice(`Purchase order created for ${item.product_id}.`); retry() }
    catch (reason) { setActionError(errorMessage(reason)) } finally { setOrdering('') }
  }

  return <>
    <PageHeader title="Replenishment" description="Prioritized review of products at or below their calculated reorder point." />
    {notice ? <div className="feedback success-feedback" role="status">{notice}<button onClick={() => setNotice('')}>Dismiss</button></div> : null}
    {pageError ? <ErrorState message={pageError} retry={() => { setActionError(''); retry() }} /> : null}
    <section className="panel table-panel">{loading ? <LoadingState label="Calculating replenishment" /> : items.length ? <div className="table-scroll"><table><thead><tr><th>Product</th><th>On hand</th><th>Lead demand</th><th>Safety stock</th><th>Reorder point</th><th>Target</th><th>Order qty</th><th>Supplier</th><th></th></tr></thead><tbody>{items.map((item) => <tr key={item.product_id}><td><strong className="sku-link">{item.product_id}</strong><span className="table-sub">{item.category}</span></td><td>{item.stock_qty}</td><td>{item.expected_lead_demand}</td><td>{item.safety_stock}</td><td><strong>{item.reorder_point}</strong></td><td>{item.target_stock}</td><td><strong>{item.recommended_quantity}</strong></td><td>{item.supplier_id ?? 'Unassigned'}</td><td><button className="button button-small button-secondary" disabled={!item.supplier_id || item.recommended_quantity < 1 || ordering === item.product_id} onClick={() => void order(item)} title={!item.supplier_id ? 'Assign a supplier in Inventory first' : 'Create a purchase order'}><ShoppingCart size={14} />{ordering === item.product_id ? 'Creating…' : 'Create PO'}</button></td></tr>)}</tbody></table></div> : <EmptyState title="No products need replenishment" detail="Recommendations appear when on-hand stock is at or below the calculated reorder point." />}</section>
  </>
}