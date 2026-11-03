<script setup lang="ts">
import { computed } from "vue";
import ActionsEditor from "./ActionsEditor.vue";
import ConditionNode from "./ConditionNode.vue";
import FieldValue from "./FieldValue.vue";
import LocationsEditor from "./LocationsEditor.vue";
import { useStore } from "@/model/context";
import type { Rule } from "@/model/types";

const props = defineProps<{ rule: Rule; index: number }>();
const store = useStore();

const problems = computed(() => store.problems.value.filter((problem) => problem.rule === props.index));

function actions() {
  props.rule.actions ??= [];
  return props.rule.actions;
}
</script>

<template>
  <section class="rule-editor">
    <ul v-if="problems.length > 0" class="problems">
      <li v-for="(problem, i) in problems" :key="i"><code>{{ problem.path }}</code> {{ problem.message }}</li>
    </ul>
    <div class="row">
      <input v-model="rule.name" class="title" placeholder="Rule name" aria-label="Rule name" />
      <FieldValue v-model="rule.enabled" :fallback="true">
        <label class="check"><input v-model="rule.enabled" type="checkbox" /> enabled</label>
      </FieldValue>
    </div>
    <h3>Where</h3>
    <LocationsEditor :locations="rule.locations" />
    <h3>When</h3>
    <ConditionNode v-model="rule.when" />
    <h3>Then</h3>
    <ActionsEditor :actions="actions()" />
  </section>
</template>
