<script setup>
/**
 * Neutral product-image placeholder.
 *
 * The brief explicitly allows a generated or neutral placeholder instead of real
 * product photography, so this renders a labelled medicine-bottle glyph and states
 * the assumption in the caption / README.
 */
defineProps({
  index: { type: Number, required: true },
  label: { type: String, default: '' },
  missing: { type: Boolean, default: false },
})
</script>

<template>
  <div
    class="product-thumb"
    :class="{ missing }"
    role="img"
    :aria-label="`Placeholder image for Product ${index}${label ? ` (${label})` : ''}`"
  >
    <svg viewBox="0 0 32 40" aria-hidden="true" focusable="false">
      <rect x="10" y="1" width="12" height="6" rx="2" fill="#b9d4df" stroke="#34647c" stroke-width="1.6" />
      <rect
        x="5"
        y="7"
        width="22"
        height="31"
        rx="4"
        fill="#edf8fb"
        stroke="#34647c"
        stroke-width="1.8"
      />
      <rect x="9" y="16" width="14" height="10" rx="2" fill="#ffffff" stroke="#7fb0c4" stroke-width="1" />
      <text x="16" y="23.6" text-anchor="middle" font-size="7.5" font-weight="700" fill="#1f6570">
        Rx
      </text>
    </svg>
    <span class="thumb-label">Product {{ index }}</span>
  </div>
</template>
