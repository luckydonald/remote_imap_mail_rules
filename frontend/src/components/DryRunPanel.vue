<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useStore } from '@/model/context'
import {
  describeStep,
  dryRun,
  runNow,
  type AffectedMail,
  type DryRunResult,
  type RunResult,
  type SummaryRow,
} from '@/model/dry-run'
import { describeError } from '@/model/http'
import { useMailStore } from '@/model/mail-store'
import { locationOfMail } from '@/router'
import type { Rule } from '@/model/types'

const props = defineProps<{ rule: Rule }>()
const store = useStore()
const mail = useMailStore()

const result = ref<DryRunResult | null>(null)
const ran = ref<RunResult | null>(null)
const error = ref('')
const loading = ref(false)
const confirming = ref(false)
const only = ref<SummaryRow | null>(null)

const planned = computed(() =>
  (result.value?.summary ?? []).filter((row) => row.status === 'planned'),
)
const plannedCount = computed(() => planned.value.reduce((sum, row) => sum + row.count, 0))
const noopCount = computed(() =>
  (result.value?.summary ?? [])
    .filter((row) => row.status === 'noop')
    .reduce((sum, row) => sum + row.count, 0),
)

/** Why "Run now" is not offered, `''` when it is. */
const blocked = computed(() => {
  if (!mail.actionsEnabled)
    return 'The server is currently not applying rules (ACTIONS_ENABLED is off). This is a dry run only.'
  if (store.dirty.value) return 'Save the rule first, "Run now" works on the saved rules.'
  return ''
})

function matches(row: SummaryRow | null, affected: AffectedMail): boolean {
  if (row === null) return true
  return affected.rounds
    .filter((round) => round.rule === props.rule.name)
    .some((round) =>
      round.steps.some(
        (step) =>
          step.type === row.type &&
          step.status === row.status &&
          (step.args.folder ?? null) === row.folder &&
          (step.args.keyword ?? null) === row.keyword &&
          step.reason === row.reason,
      ),
    )
}

const shown = computed(() => (result.value?.mails ?? []).filter((m) => matches(only.value, m)))

function rowLabel(row: SummaryRow): string {
  return describeStep({
    type: row.type,
    status: row.status,
    reason: row.reason,
    args: { folder: row.folder ?? undefined, keyword: row.keyword ?? undefined },
  })
}

function sameRow(a: SummaryRow | null, b: SummaryRow): boolean {
  return a !== null && rowLabel(a) === rowLabel(b) && a.status === b.status
}

function sender(m: AffectedMail): string {
  return m.sender.name || m.sender.address
}

async function start(): Promise<void> {
  loading.value = true
  error.value = ''
  ran.value = null
  confirming.value = false
  only.value = null
  try {
    result.value = await dryRun(props.rule.name, store.yaml.value)
  } catch (e) {
    result.value = null
    error.value = describeError(e)
  } finally {
    loading.value = false
  }
}

async function apply(): Promise<void> {
  confirming.value = false
  loading.value = true
  error.value = ''
  try {
    ran.value = await runNow(props.rule.name)
    result.value = await dryRun(props.rule.name, store.yaml.value)
  } catch (e) {
    error.value = describeError(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="dry-run">
    <h3>Dry run</h3>
    <div class="row">
      <button type="button" :disabled="loading || !rule.name" @click="start">
        {{ result ? 'Run the dry run again' : 'Dry run' }}
      </button>
      <button
        v-if="result"
        type="button"
        class="run-now"
        :disabled="loading || blocked !== '' || plannedCount === 0"
        :title="blocked"
        @click="confirming = true"
      >
        Run now
      </button>
      <span v-if="loading" class="hint">Looking at the mails…</span>
    </div>
    <p v-if="result && blocked" class="hint blocked">{{ blocked }}</p>
    <p v-if="confirming" class="confirm">
      Apply {{ plannedCount }} changes to {{ result?.affected }} mails for real?
      <button type="button" class="confirm-run" @click="apply">Apply</button>
      <button type="button" class="ghost" @click="confirming = false">Cancel</button>
    </p>
    <p v-if="error" class="message error">{{ error }}</p>
    <p v-if="ran" class="notice-run">
      Applied to {{ ran.applied }} mails ({{
        Object.entries(ran.steps)
          .map(([status, count]) => `${count} ${status}`)
          .join(', ') || 'nothing to do'
      }}).
    </p>
    <ul v-if="ran?.errors.length" class="problems">
      <li v-for="(e, i) in ran.errors" :key="i">{{ e }}</li>
    </ul>
    <template v-if="result">
      <ul v-if="result.errors.length" class="problems">
        <li v-for="(e, i) in result.errors" :key="i">{{ e }}</li>
      </ul>
      <p class="totals">
        Looked at {{ result.inspected }} mails, {{ result.affected }} would be affected{{
          noopCount ? `, ${noopCount} steps change nothing` : ''
        }}.
      </p>
      <p v-if="result.truncated" class="hint">
        Stopped early, only the newest mails were looked at.
      </p>
      <p v-if="result.summary.length === 0" class="hint empty">
        This rule would do nothing right now.
      </p>
      <table v-else class="summary">
        <tbody>
          <tr
            v-for="row in result.summary"
            :key="`${row.type}-${row.status}-${row.folder}-${row.keyword}-${row.reason}`"
            :class="{ active: sameRow(only, row), muted: row.status !== 'planned' }"
            @click="only = sameRow(only, row) ? null : row"
          >
            <td class="count">{{ row.count }}×</td>
            <td>{{ rowLabel(row) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="only" class="hint">
        Showing {{ shown.length }} mails for "{{ rowLabel(only) }}".
        <button type="button" class="ghost" @click="only = null">Show all</button>
      </p>
      <p v-if="result.listed < result.affected && !only" class="hint">
        The list shows the first {{ result.listed }} of {{ result.affected }} mails.
      </p>
      <ul class="affected">
        <li v-for="m in shown" :key="`${m.account_id}-${m.folder}-${m.uid}`">
          <RouterLink
            :to="locationOfMail({ accountId: m.account_id, folder: m.folder, uid: m.uid })"
            class="subject"
            >{{ m.subject || '(no subject)' }}</RouterLink
          >
          <span class="from">{{ sender(m) }} · {{ m.folder }}</span>
          <ol class="chain">
            <li v-for="(round, i) in m.rounds" :key="i" :class="{ own: round.rule === rule.name }">
              <strong>{{ round.rule }}:</strong>
              {{ round.steps.map(describeStep).join(', ') || 'nothing' }}
            </li>
          </ol>
        </li>
      </ul>
    </template>
  </section>
</template>
