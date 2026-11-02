<script setup>
import { money, orderStatusClass, orderStatusLabel } from '../utils/format'

defineProps({
  orders: { type: Array, default: () => [] },
  selected: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

defineEmits(['select'])
</script>

<template>
  <aside class="panel order-list" aria-label="Orders">
    <div class="panel-head">
      <h2>Orders</h2>
      <span class="tiny">{{ orders.length }} total</span>
    </div>

    <div v-if="loading" class="order-items">
      <div v-for="n in 3" :key="n" class="skeleton skeleton-row" />
    </div>

    <div v-else-if="!orders.length" class="state-block">
      <h3>No orders</h3>
      <p class="tiny">data/orders.json did not return any orders.</p>
    </div>

    <div v-else class="order-items">
      <button
        v-for="order in orders"
        :key="order.order_no"
        type="button"
        class="order-item"
        :class="{ active: order.order_no === selected }"
        :aria-current="order.order_no === selected ? 'true' : undefined"
        @click="$emit('select', order.order_no)"
      >
        <span class="order-no">{{ order.order_no }}</span>
        <span class="order-sub">
          <span>{{ order.order_date_display }}</span>
          <span class="status-pill" :class="orderStatusClass(order.status)">
            {{ orderStatusLabel(order.status) }}
          </span>
        </span>
        <span class="order-sub">
          <span>{{ order.customer_name }}</span>
          <span>{{ order.suburb }} {{ order.state }}</span>
        </span>
        <span class="order-amount">{{ money(order.totals.total) }}</span>
        <span v-if="order.warning_count" class="warn-flag">
          {{ order.warning_count }} warning{{ order.warning_count > 1 ? 's' : '' }}
        </span>
      </button>
    </div>
  </aside>
</template>
