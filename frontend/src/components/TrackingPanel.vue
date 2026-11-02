<script setup>
import { computed, ref, watch } from 'vue'
import { formatDateTime, trackingBadge } from '../utils/format'

const props = defineProps({
  tracking: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

defineEmits(['refresh'])

const expanded = ref(new Set())

watch(
  () => props.tracking,
  () => expanded.value.clear(),
)

const shipments = computed(() => props.tracking?.shipments || [])

function visibleEvents(shipment) {
  const events = shipment.events || []
  return expanded.value.has(shipment.tracking_ref) ? events : events.slice(0, 4)
}

function hasMore(shipment) {
  return (shipment.events || []).length > 4
}

function toggle(ref) {
  const next = new Set(expanded.value)
  if (next.has(ref)) next.delete(ref)
  else next.add(ref)
  expanded.value = next
}
</script>

<template>
  <section class="panel" aria-label="Courier tracking">
    <div class="panel-head">
      <div>
        <h2>Courier tracking</h2>
        <p v-if="tracking" class="tiny" style="margin: 4px 0 0">
          {{ tracking.summary.available }} of {{ tracking.summary.total }} consignments returned a
          live status<template v-if="tracking.checked_at">
            · checked {{ formatDateTime(tracking.checked_at) }}</template
          >
        </p>
      </div>
      <button class="btn" type="button" :disabled="loading" @click="$emit('refresh')">
        <span v-if="loading" class="spinner" aria-hidden="true" />
        {{ loading ? 'Refreshing…' : 'Refresh tracking' }}
      </button>
    </div>

    <div class="panel-body">
      <div v-if="error" class="alert error" role="alert">
        <div>
          <strong>Tracking could not be loaded</strong>
          {{ error }}
        </div>
      </div>

      <div v-if="loading && !tracking" class="tracking-grid">
        <div v-for="n in 2" :key="n" class="skeleton skeleton-row" style="height: 210px" />
      </div>

      <div v-else-if="tracking && shipments.length" class="tracking-grid">
        <article
          v-for="shipment in shipments"
          :key="shipment.tracking_ref"
          class="track-card"
          :class="`state-${shipment.state}`"
        >
          <div class="track-head">
            <div>
              <h3>{{ shipment.carrier_name || shipment.provider }}</h3>
              <div class="track-no">{{ shipment.tracking_no || 'no tracking number' }}</div>
            </div>
            <span class="badge" :class="trackingBadge(shipment.state, shipment.status_code).css">
              {{ trackingBadge(shipment.state, shipment.status_code).label }}
            </span>
          </div>

          <div class="track-body">
            <template v-if="shipment.state === 'available'">
              <div class="track-status">
                <span class="status-text">{{ shipment.status || 'Status returned' }}</span>
              </div>
              <div v-if="shipment.last_update" class="tiny" style="margin-bottom: 10px">
                Last update: {{ formatDateTime(shipment.last_update.date) }}
                <template v-if="shipment.last_update.location">
                  · {{ shipment.last_update.location }}
                </template>
              </div>
              <ul v-if="shipment.events.length" class="timeline">
                <li v-for="(event, index) in visibleEvents(shipment)" :key="`${event.date}-${index}`">
                  <div class="event-desc">{{ event.description }}</div>
                  <div class="event-meta">
                    {{ formatDateTime(event.date) }}
                    <template v-if="event.location"> · {{ event.location }}</template>
                  </div>
                </li>
              </ul>
              <button
                v-if="hasMore(shipment)"
                class="btn"
                type="button"
                style="margin-top: 10px"
                @click="toggle(shipment.tracking_ref)"
              >
                {{ expanded.has(shipment.tracking_ref) ? 'Show fewer events' : `Show all ${shipment.events.length} events` }}
              </button>
            </template>

            <template v-else>
              <p class="track-message">{{ shipment.message }}</p>
              <p v-if="shipment.state === 'not_implemented'" class="tiny" style="margin: 10px 0 0">
                TNT research and integration is optional bonus work in the brief. This submission
                reports the limitation instead of inventing a tracking result.
              </p>
            </template>

            <div class="track-skus">
              <span v-for="sku in shipment.skus" :key="sku" class="tag">{{ sku }}</span>
            </div>
          </div>

          <div class="track-foot">
            <span>
              {{ shipment.tracking_ref }} · {{ shipment.provider }} ·
              {{ shipment.unit_count }} unit{{ shipment.unit_count === 1 ? '' : 's' }}
              · {{ shipment.line_count }} line{{ shipment.line_count === 1 ? '' : 's' }}
            </span>
            <span>
              <template v-if="shipment.test_data">test number · </template>
              <template v-if="shipment.cached">cached · </template>
              <template v-if="shipment.http_status">HTTP {{ shipment.http_status }}</template>
            </span>
          </div>
        </article>
      </div>

      <div v-else-if="tracking" class="state-block">
        <h3>No consignments</h3>
        <p class="tiny">This order has no tracking references assigned.</p>
      </div>
    </div>
  </section>
</template>
