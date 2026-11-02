<script setup>
import { orderStatusClass, orderStatusLabel } from '../utils/format'

defineProps({
  order: { type: Object, required: true },
})
</script>

<template>
  <header class="order-head">
    <div>
      <h2>{{ order.order_no }}</h2>
      <div class="order-meta">
        <span>Order date <strong>{{ order.order_date_display }}</strong></span>
        <span>Company <strong>{{ order.company }}</strong></span>
        <span>
          Lines <strong>{{ order.counts.lines }}</strong>
          · Units <strong>{{ order.totals.unit_count }}</strong>
        </span>
      </div>
    </div>
    <span class="status-pill" :class="orderStatusClass(order.status)">
      {{ orderStatusLabel(order.status) }}
    </span>
  </header>

  <div class="panel-body">
    <div class="info-grid">
      <section class="info-card">
        <h4>Customer</h4>
        <dl>
          <dt>Name</dt>
          <dd>{{ order.customer.name }}</dd>
          <dt>Phone</dt>
          <dd>{{ order.customer.phone }}</dd>
          <dt>Email</dt>
          <dd>{{ order.customer.email }}</dd>
        </dl>
      </section>

      <section class="info-card">
        <h4>Shipping address</h4>
        <dl>
          <dt>Street</dt>
          <dd>{{ order.shipping_address.line1 }}</dd>
          <dt>Suburb</dt>
          <dd>{{ order.shipping_address.suburb }}</dd>
          <dt>State</dt>
          <dd>{{ order.shipping_address.state }} {{ order.shipping_address.postcode }}</dd>
          <dt>Country</dt>
          <dd>{{ order.shipping_address.country || 'AU' }}</dd>
        </dl>
      </section>

      <section v-if="order.test_order_purpose" class="info-card">
        <h4>Why this test order exists</h4>
        <p class="tiny" style="margin: 0">{{ order.test_order_purpose }}</p>
      </section>
    </div>
  </div>
</template>
