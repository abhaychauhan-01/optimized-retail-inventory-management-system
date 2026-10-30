import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Pencil, Plus, Search, Trash2, X } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { errorMessage, adjustStock, createProduct, deleteProduct, getInventoryAnalytics, getProducts, getSuppliers, updateProduct } from '../services/api'
import type { Product } from '../types'
import { useAsyncData } from '../hooks/useAsyncData'

const emptyProduct = { product_id: '', category: '', stock_qty: 0, reorder_level: 0, daily_sales: 0, supplier_id: null as string | null, lead_days: 0, unit_cost: null as number | null }

export default function InventoryPage() {
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('search') ?? '')
  const [category, setCategory] = useState('')
  const [filter, setFilter] = useState('')
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')
  const [modal, setModal] = useState<'create' | 'edit' | 'adjust' | null>(null)
  const [selected, setSelected] = useState<Product | null>(null)
  const [form, setForm] = useState(emptyProduct)
  const [adjustment, setAdjustment] = useState({ quantity_delta: 1, reason: 'Stock count correction' })
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    const [products, analytics, suppliers] = await Promise.all([
      getProducts({ search: query || undefined, category: category || undefined, stock_status: filter || undefined, page, page_size: 12, sort_by: 'product_id', sort_order: 'asc' }),
      getInventoryAnalytics(), getSuppliers(),
    ])
    return { products, categories: analytics.categories.map((item) => item.category), suppliers }
  }, [category, filter, page, query])

  const { data: loaded, loading, error: loadError, retry } = useAsyncData(load)
  const data = loaded?.products ?? null
  const categories = loaded?.categories ?? []
  const suppliers = loaded?.suppliers ?? []
  const pageError = error || loadError
  const openNew = () => { setSelected(null); setForm(emptyProduct); setModal('create') }
  const openEdit = (product: Product) => { setSelected(product); setForm({ product_id: product.product_id, category: product.category, stock_qty: product.stock_qty, reorder_level: product.reorder_level, daily_sales: product.daily_sales, supplier_id: product.supplier_id, lead_days: product.lead_days, unit_cost: product.unit_cost ?? null }); setModal('edit') }
  const closeModal = () => { setModal(null); setSelected(null) }
  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true); setError(''); setNotice('')
    try {
      const payload = { ...form, supplier_id: form.supplier_id || null, unit_cost: form.unit_cost === null ? null : Number(form.unit_cost) }
      if (modal === 'create') await createProduct(payload)
      else if (selected) await updateProduct(selected.product_id, payload)
      setNotice(modal === 'create' ? 'Product created.' : 'Product updated.')
      closeModal(); retry()
    } catch (reason) { setError(errorMessage(reason)) } finally { setSaving(false) }
  }
  const saveAdjustment = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!selected) return
    setSaving(true); setError('')
    try { await adjustStock(selected.product_id, Number(adjustment.quantity_delta), adjustment.reason); setNotice(`Stock updated for ${selected.product_id}.`); closeModal(); retry() }
    catch (reason) { setError(errorMessage(reason)) } finally { setSaving(false) }
  }
  const remove = async (product: Product) => {
    if (!window.confirm(`Delete ${product.product_id}? Products with movement or purchase-order history cannot be deleted.`)) return
    setError(''); setNotice('')
    try { await deleteProduct(product.product_id); setNotice(`${product.product_id} deleted.`); retry() }
    catch (reason) { setError(errorMessage(reason)) }
  }

  return <>
    <PageHeader title="Inventory" description="Search, review, and maintain product stock records." action={<button className="button button-primary" onClick={openNew}><Plus size={16} /> Add product</button>} />
    {notice ? <div className="feedback success-feedback" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss"><X size={15} /></button></div> : null}
    {pageError ? <ErrorState message={pageError} retry={() => { setError(''); retry() }} /> : null}
    <section className="panel inventory-panel">
      <div className="filter-bar">
        <label className="search-field"><Search size={16} /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Search product ID" aria-label="Search product ID" /></label>
        <select value={category} aria-label="Filter by category" onChange={(event) => { setCategory(event.target.value); setPage(1) }}><option value="">All categories</option>{categories.map((item) => <option key={item}>{item}</option>)}</select>
        <select value={filter} aria-label="Filter by stock status" onChange={(event) => { setFilter(event.target.value); setPage(1) }}><option value="">All stock status</option><option value="healthy">Healthy</option><option value="low">Low stock</option><option value="out">Out of stock</option></select>
        <span className="filter-count">{data ? `${data.total} products` : ''}</span>
      </div>
      {loading ? <LoadingState label="Loading inventory" /> : data?.items.length ? <>
        <div className="table-scroll"><table><thead><tr><th>Product</th><th>Category</th><th>On hand</th><th>Reorder level</th><th>Daily sales</th><th>Supplier</th><th>Lead time</th><th aria-label="Actions"></th></tr></thead><tbody>
          {data.items.map((product) => {
            const out = product.stock_qty === 0
            const low = !out && product.stock_qty <= product.reorder_level
            return <tr key={product.product_id}><td><strong className="sku-link">{product.product_id}</strong><span className="table-sub">Updated {new Date(product.updated_at).toLocaleDateString()}</span></td><td>{product.category}</td><td><strong>{product.stock_qty}</strong><span className={`status-label ${out ? 'status-out' : low ? 'status-low' : 'status-healthy'}`}>{out ? 'Out of stock' : low ? 'Low stock' : 'Healthy'}</span></td><td>{product.reorder_level}</td><td>{product.daily_sales.toLocaleString()}</td><td>{product.supplier_id ?? 'Not assigned'}</td><td>{product.lead_days} days</td><td><div className="row-actions"><button className="icon-button" title="Adjust stock" aria-label={`Adjust stock for ${product.product_id}`} onClick={() => { setSelected(product); setAdjustment({ quantity_delta: 1, reason: 'Stock count correction' }); setModal('adjust') }}><Plus size={15} /></button><button className="icon-button" title="Edit product" aria-label={`Edit ${product.product_id}`} onClick={() => openEdit(product)}><Pencil size={15} /></button><button className="icon-button danger-icon" title="Delete product" aria-label={`Delete ${product.product_id}`} onClick={() => void remove(product)}><Trash2 size={15} /></button></div></td></tr>
          })}
        </tbody></table></div>
        <div className="table-footer"><span>Showing {(page - 1) * 12 + 1}–{Math.min(page * 12, data.total)} of {data.total}</span><div><button className="icon-button" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft size={16} /></button><span>Page {page} of {Math.max(1, Math.ceil(data.total / 12))}</span><button className="icon-button" aria-label="Next page" disabled={page >= Math.ceil(data.total / 12)} onClick={() => setPage((value) => value + 1)}><ChevronRight size={16} /></button></div></div>
      </> : !pageError ? <EmptyState title="No products match these filters" detail="Adjust the search or filters, or add a new product." /> : null}
    </section>
    {modal ? <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeModal() }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div className="modal-heading"><div><h2 id="modal-title">{modal === 'create' ? 'Add product' : modal === 'edit' ? `Edit ${selected?.product_id}` : `Adjust ${selected?.product_id}`}</h2><p>{modal === 'adjust' ? 'Record a positive receipt or negative stock correction.' : 'Product details and replenishment inputs.'}</p></div><button className="icon-button" onClick={closeModal} aria-label="Close dialog"><X size={17} /></button></div>
      {modal === 'adjust' ? <form onSubmit={(event) => void saveAdjustment(event)}><div className="form-grid"><label>Quantity change<input type="number" required value={adjustment.quantity_delta} onChange={(event) => setAdjustment({ ...adjustment, quantity_delta: Number(event.target.value) })} /></label><label>Reason<input required minLength={3} maxLength={200} value={adjustment.reason} onChange={(event) => setAdjustment({ ...adjustment, reason: event.target.value })} /></label></div><div className="modal-actions"><button type="button" className="button button-secondary" onClick={closeModal}>Cancel</button><button className="button button-primary" disabled={saving || adjustment.quantity_delta === 0}>{saving ? 'Saving…' : 'Record movement'}</button></div></form> : <form onSubmit={(event) => void save(event)}><div className="form-grid"><label>Product ID<input required maxLength={80} disabled={modal === 'edit'} value={form.product_id} onChange={(event) => setForm({ ...form, product_id: event.target.value.trim() })} /></label><label>Category<input required maxLength={100} value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} /></label><label>Stock on hand<input type="number" min="0" required value={form.stock_qty} onChange={(event) => setForm({ ...form, stock_qty: Number(event.target.value) })} /></label><label>Reorder level<input type="number" min="0" required value={form.reorder_level} onChange={(event) => setForm({ ...form, reorder_level: Number(event.target.value) })} /></label><label>Recorded daily sales<input type="number" min="0" step="0.01" required value={form.daily_sales} onChange={(event) => setForm({ ...form, daily_sales: Number(event.target.value) })} /></label><label>Lead time (days)<input type="number" min="0" required value={form.lead_days} onChange={(event) => setForm({ ...form, lead_days: Number(event.target.value) })} /></label><label>Supplier<select value={form.supplier_id ?? ''} onChange={(event) => setForm({ ...form, supplier_id: event.target.value || null })}><option value="">Not assigned</option>{suppliers.map((supplier) => <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.supplier_id}</option>)}</select></label><label>Unit cost (internal)<input type="number" min="0" step="0.01" value={form.unit_cost ?? ''} onChange={(event) => setForm({ ...form, unit_cost: event.target.value ? Number(event.target.value) : null })} /></label></div><p className="form-helper">Daily sales are recorded source values, not a validated demand forecast.</p><div className="modal-actions"><button type="button" className="button button-secondary" onClick={closeModal}>Cancel</button><button className="button button-primary" disabled={saving}>{saving ? 'Saving…' : 'Save product'}</button></div></form>}</section></div> : null}
  </>
}