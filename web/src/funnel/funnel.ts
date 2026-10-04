export type FunnelStep = 'product_viewed' | 'added_to_cart' | 'checkout_started' | 'order_paid'

export const FUNNEL_ORDER: FunnelStep[] = [
  'product_viewed',
  'added_to_cart',
  'checkout_started',
  'order_paid',
]

export interface FunnelEvent {
  step: FunnelStep
  productId?: string
  orderId?: string
  at: number
}

export interface FunnelSink {
  send(event: FunnelEvent): void
}

export class InMemorySink implements FunnelSink {
  readonly events: FunnelEvent[] = []
  send(event: FunnelEvent) { this.events.push(event) }
}

export class Funnel {
  constructor(private readonly sink: FunnelSink, private readonly now: () => number = Date.now) {}

  track(step: FunnelStep, payload: { productId?: string; orderId?: string } = {}) {
    this.sink.send({ step, ...payload, at: this.now() })
  }
}

export function conversion(events: FunnelEvent[]): { step: FunnelStep; count: number; ofPrevious: number }[] {
  // TODO шаг 14: посчитать воронку - сколько дошло до каждого шага и какая это
  // доля от предыдущего. Осторожно с шагом, до которого не дошёл никто.
  return []
}
