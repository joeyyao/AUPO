<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from './api/client'
import LineItemsTable from './components/LineItemsTable.vue'
import OrderHeader from './components/OrderHeader.vue'
import OrderList from './components/OrderList.vue'
import OrderTotals from './components/OrderTotals.vue'
import TrackingPanel from './components/TrackingPanel.vue'

const orders = ref([])
const ordersLoading = ref(true)
const ordersError = ref('')

const selectedOrderNo = ref('')
const detail = ref(null)
const detailLoading = ref(false)
const detailError = ref('')

const tracking = ref(null)
const trackingLoading = ref(false)
const trackingError = ref('')

const health = ref(null)
const healthError = ref('')

let detailToken = 0
let trackingToken = 0

const auspostState = computed(() => {
  const courier = health.value?.couriers?.auspost
  if (!courier) return { label: 'Checking API…', ok: false }
  if (!courier.live_tracking_enabled) return { label: 'Tracking disabled', ok: false }
  if (!courier.credentials_configured) return { label: 'No credentials', ok: false }
  return { label: 'Australia Post live', ok: true }
})

const hasInvalidLines = computed(
  () => (detail.value?.counts?.invalid_lines || 0) > 0,
)

async function loadHealth() {
  try {
    health.value = await api.health()
    healthError.value = ''
  } catch (error) {
    health.value = null
    healthError.value = error.message
  }
}

async function loadOrders() {
  ordersLoading.value = true
  ordersError.value = ''
  try {
    const data = await api.listOrders()
    orders.value = data.orders || []
    if (orders.value.length && !selectedOrderNo.value) {
      await selectOrder(orders.value[0].order_no)
    }
  } catch (error) {
    ordersError.value = error.message
    orders.value = []
  } finally {
    ordersLoading.value = false
  }
}

async function selectOrder(orderNo) {
  if (detailLoading.value && orderNo === selectedOrderNo.value) return
  selectedOrderNo.value = orderNo
  // clear the previous order immediately so the detail panel never shows stale rows
  detail.value = null
  detailError.value = ''
  tracking.value = null
  trackingError.value = ''
  await Promise.all([loadDetail(orderNo), loadTracking(orderNo)])
}

async function loadDetail(orderNo) {
  const token = ++detailToken
  detailLoading.value = true
  detailError.value = ''
  try {
    const payload = await api.getOrder(orderNo)
    if (token === detailToken) detail.value = payload
  } catch (error) {
    if (token === detailToken) {
      detail.value = null
      detailError.value = error.message
    }
  } finally {
    if (token === detailToken) detailLoading.value = false
  }
}

async function loadTracking(orderNo = selectedOrderNo.value, refresh = false) {
  if (!orderNo) return
  const token = ++trackingToken
  trackingLoading.value = true
  trackingError.value = ''
  try {
    const payload = await api.getTracking(orderNo, { refresh })
    if (token === trackingToken) tracking.value = payload
  } catch (error) {
    if (token === trackingToken) trackingError.value = error.message
  } finally {
    if (token === trackingToken) trackingLoading.value = false
  }
}

function refreshTracking() {
  loadTracking(selectedOrderNo.value, true)
}

onMounted(async () => {
  await Promise.all([loadHealth(), loadOrders()])
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div>
        <p class="eyebrow">Australian pharmacy orders</p>
        <h1>Order Details, Tracking and Shipping Estimate</h1>
        <p class="subtitle">
          SKU matching against product_list · GST-inclusive RRP converted to ex-GST · courier
          tracking with explicit unavailable states
        </p>
      </div>
      <div class="header-meta">
        <span class="chip">
          <span class="chip-dot" :class="{ off: !auspostState.ok }" />
          {{ auspostState.label }}
        </span>
        <span class="chip">
          <span class="chip-dot" :class="{ off: true }" />
          TNT not implemented
        </span>
        <span class="chip">Currency AUD</span>
      </div>
    </header>

    <div class="layout">
      <OrderList
        :orders="orders"
        :selected="selectedOrderNo"
        :loading="ordersLoading"
        @select="selectOrder"
      />

      <main>
        <div v-if="ordersError" class="alert error" role="alert">
          <div>
            <strong>Orders could not be loaded</strong>
            {{ ordersError }}
          </div>
        </div>

        <section v-if="detailLoading && !detail" class="panel">
          <div class="panel-body">
            <div v-for="n in 5" :key="n" class="skeleton skeleton-row" />
          </div>
        </section>

        <div v-else-if="detailError" class="alert error" role="alert">
          <div>
            <strong>This order could not be loaded</strong>
            {{ detailError }}
          </div>
        </div>

        <template v-else-if="detail">
          <div v-if="detail.warnings.length" class="alerts">
            <div class="alert warning" role="status">
              <div>
                <strong>
                  {{ detail.warnings.length }} data issue{{ detail.warnings.length > 1 ? 's' : '' }}
                  found while processing this order
                </strong>
                <ul>
                  <li v-for="warning in detail.warnings" :key="warning">{{ warning }}</li>
                </ul>
              </div>
            </div>
          </div>

          <section class="panel">
            <OrderHeader :order="detail" />
            <LineItemsTable :items="detail.line_items" />
          </section>

          <section class="panel">
            <div class="panel-head">
              <h2>Calculations</h2>
              <span v-if="hasInvalidLines" class="warn-flag">
                {{ detail.counts.invalid_lines }} line(s) excluded
              </span>
              <span v-else class="tiny">
                All {{ detail.counts.lines }} lines priced
              </span>
            </div>
            <div class="panel-body">
              <OrderTotals :order="detail" />
            </div>
          </section>

          <TrackingPanel
            :tracking="tracking"
            :loading="trackingLoading"
            :error="trackingError"
            @refresh="refreshTracking"
          />
        </template>

        <section v-else class="panel">
          <div class="state-block">
            <h3>Select an order</h3>
            <p class="tiny">Choose an order from the list to see its details and tracking.</p>
          </div>
        </section>

        <footer class="app-footer">
          <span>
            Data source: <code>data/orders.json</code> · <code>data/products.json</code> ·
            <code>data/shipments.json</code> · <code>data/shipping_rates.json</code>
          </span>
          <span>
            Product images are neutral placeholders ·
            <span v-if="healthError">API health unavailable: {{ healthError }}</span>
            <span v-else>GST 10% · {{ health?.shipping?.origin_postcode ? `origin ${health.shipping.origin_postcode}` : 'AUD' }}</span>
          </span>
        </footer>
      </main>
    </div>
  </div>
</template>
