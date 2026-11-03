<script setup lang="ts">
import { inject } from "vue";
import { ALLOW_VARS } from "@/model/context";
import { isVar } from "@/model/types";

const props = defineProps<{ modelValue: unknown; fallback: unknown }>();
const emit = defineEmits<{ "update:modelValue": [value: unknown] }>();
const allowVars = inject(ALLOW_VARS, false);

function toggle(): void {
  emit("update:modelValue", isVar(props.modelValue) ? props.fallback : { var: "" });
}

function rename(event: Event): void {
  emit("update:modelValue", { var: (event.target as HTMLInputElement).value });
}
</script>

<template>
  <span class="field-value">
    <template v-if="isVar(modelValue)">
      <span class="badge">!var</span>
      <input class="var-name" :value="modelValue.var" placeholder="variable name" @input="rename" />
    </template>
    <slot v-else />
    <button v-if="allowVars" type="button" class="ghost" :title="isVar(modelValue) ? 'Use a fixed value' : 'Use a template variable'" @click="toggle">
      {{ isVar(modelValue) ? "value" : "var" }}
    </button>
  </span>
</template>
