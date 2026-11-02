<script setup>
import { money } from '../utils/format'
import ProductPlaceholder from './ProductPlaceholder.vue'

defineProps({
  items: { type: Array, default: () => [] },
})
</script>

<template>
  <div class="table-scroll">
    <table class="lines">
      <caption class="sr-only">
        Line items with RRP, ex-GST unit price and ex-GST line subtotal
      </caption>
      <thead>
        <tr>
          <th scope="col">Product</th>
          <th scope="col">SKU</th>
          <th scope="col" class="num">Qty</th>
          <th scope="col" class="num">RRP (incl. GST)</th>
          <th scope="col" class="num">Ex-GST unit</th>
          <th scope="col" class="num">Line subtotal (ex GST)</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.line_no" :class="{ 'invalid-row': !item.valid }">
          <td>
            <div class="cell-product">
              <ProductPlaceholder
                :index="item.line_no"
                :label="item.sku"
                :missing="!item.product"
              />
              <div class="product-info">
                <div class="product-name">
                  {{ item.product ? item.product.name : 'Unmatched SKU' }}
                </div>
                <p v-if="item.product && item.product.description" class="product-desc">
                  {{ item.product.description }}
                </p>
                <div v-if="item.product" class="tag-row">
                  <span class="tag">{{ item.product.dosage_type || item.product.product_type }}</span>
                  <span v-if="item.product.size" class="tag">Size {{ item.product.size }}</span>
                  <span v-if="item.product.schedule" class="tag">Schedule {{ item.product.schedule }}</span>
                  <span class="tag track">{{ item.tracking_ref || 'No tracking' }}</span>
                  <span v-if="item.product.data_source === 'generated_placeholder'" class="tag placeholder">
                    Placeholder record
                  </span>
                </div>
                <p v-for="issue in item.issues" :key="issue" class="line-issue">⚠ {{ issue }}</p>
              </div>
            </div>
          </td>
          <td class="sku-code">{{ item.sku || '—' }}</td>
          <td class="num">{{ item.quantity ?? '—' }}</td>
          <td class="num">
            <template v-if="item.rrp_incl_gst !== null">
              <div class="price-primary">{{ money(item.rrp_incl_gst) }}</div>
              <div class="price-sub">incl. GST</div>
            </template>
            <span v-else class="muted">—</span>
          </td>
          <td class="num">
            <template v-if="item.ex_gst_unit_price !== null">
              {{ money(item.ex_gst_unit_price) }}
            </template>
            <span v-else class="muted">—</span>
          </td>
          <td class="num">
            <template v-if="item.line_subtotal_ex_gst !== null">
              <div class="price-primary">{{ money(item.line_subtotal_ex_gst) }}</div>
            </template>
            <span v-else class="muted">not calculated</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
