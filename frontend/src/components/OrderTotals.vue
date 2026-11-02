<script setup>
import { computed } from 'vue'
import { money } from '../utils/format'

const props = defineProps({
  order: { type: Object, required: true },
})

const totals = computed(() => props.order.totals)
const estimate = computed(() => props.order.shipment_estimate)
const gstPercent = computed(() => Math.round((totals.value.gst_rate ?? 0.1) * 100))
</script>

<template>
  <div class="totals-layout">
    <section>
      <h3 style="font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.1em; color: #5b6b78; margin-bottom: 10px">
        Shipment fee estimate
      </h3>

      <div
        v-for="group in estimate.groups"
        :key="group.tracking_ref || group.provider"
        class="ship-group"
        :class="{ unsupported: !group.chargeable }"
      >
        <div class="ship-head">
          <strong>{{ group.tracking_ref || 'Unassigned' }} · {{ group.carrier_name || group.provider }}</strong>
          <span class="mono" style="font-weight: 700">{{ money(group.fee) }}</span>
        </div>

        <div v-if="group.chargeable" class="ship-components">
          <span>Billable weight <b>{{ group.billable_weight_kg }} kg</b></span>
          <span>Base fee <b>{{ money(group.components.base_fee) }}</b></span>
          <span>Extra weight <b>{{ money(group.components.extra_weight_fee) }}</b></span>
          <span>Interstate <b>{{ money(group.components.interstate_surcharge) }}</b></span>
          <span>Remote postcode <b>{{ money(group.components.remote_surcharge) }}</b></span>
          <span>Units <b>{{ group.unit_count }}</b></span>
        </div>

        <p class="ship-reason">{{ group.reason }}</p>
      </div>

      <p class="tiny" style="margin-top: 10px">
        {{ estimate.description }}
        Dispatched from {{ estimate.origin.suburb }} {{ estimate.origin.state }}
        {{ estimate.origin.postcode }} to {{ estimate.destination.suburb || 'the destination' }}
        {{ estimate.destination.state }} {{ estimate.destination.postcode }}.
      </p>
    </section>

    <section>
      <h3 style="font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.1em; color: #5b6b78; margin-bottom: 10px">
        Order totals
      </h3>
      <div class="summary">
        <div class="summary-row">
          <span>Subtotal (ex GST)</span>
          <span>{{ money(totals.subtotal_ex_gst) }}</span>
        </div>
        <div class="summary-row">
          <span>GST ({{ gstPercent }}%)</span>
          <span>{{ money(totals.gst) }}</span>
        </div>
        <div class="summary-row">
          <span>Shipment Fee</span>
          <span>{{ money(totals.shipment_fee) }}</span>
        </div>
        <div class="summary-row total">
          <span>Total</span>
          <span>{{ money(totals.total) }}</span>
        </div>
        <p class="summary-note">
          RRP includes GST, so each ex-GST unit price is RRP ÷ 1.10 and the line subtotal is
          rounded to cents. All amounts are in AUD.
        </p>
      </div>
    </section>
  </div>
</template>
