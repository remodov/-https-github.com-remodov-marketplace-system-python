export interface Product {
  id: string
  title: string
  price: string
  sellerId: string
  currency?: string
}

export interface OrderScreen {
  orderId: string
  status: string
  total: string
  paymentStatus: string
  items: { productId: string; title: string; quantity: number; price: string }[]
}

export interface OrderLine {
  productId: string
  sellerId: string
  quantity: number
}

const API = import.meta.env?.VITE_API_URL ?? ''
const CUSTOMER_TOKEN = import.meta.env?.VITE_CUSTOMER_TOKEN ?? 'customer.00000000-0000-0000-0000-000000000001'

const DEMO_ADDRESS = { country: 'RU', city: 'Москва', street: 'Примерная, 10', postalCode: '101000' }

function authorized(headers: Record<string, string> = {}): Record<string, string> {
  return { Authorization: 'Bearer ' + CUSTOMER_TOKEN, ...headers }
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error('Запрос не удался: ' + response.status)
  }
  return response.json() as Promise<T>
}

export async function loadCatalog(): Promise<Product[]> {
  const page = await json<{ items: Product[] }>(await fetch(API + '/api/v1/products'))
  return page.items
}

export async function createOrder(items: OrderLine[], idempotencyKey: string): Promise<{ id: string }> {
  return json<{ id: string }>(await fetch(API + '/api/v1/orders', {
    method: 'POST',
    headers: authorized({ 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey }),
    body: JSON.stringify({ items, shippingAddress: DEMO_ADDRESS }),
  }))
}

export async function loadOrderScreen(orderId: string): Promise<OrderScreen> {
  return json<OrderScreen>(await fetch(API + '/api/v1/screens/order/' + orderId, { headers: authorized() }))
}
