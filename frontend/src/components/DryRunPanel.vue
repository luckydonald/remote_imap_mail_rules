<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import MailSpinner from './MailSpinner.vue'
import { useStore } from '@/model/context'
import {
  describeStep,
  dryRun,
  runNow,
  type AffectedMail,
  mergeSummary,
  type DryRunCursor,
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

/** What the pages so far add up to. */
interface Totals {
  actionsEnabled: boolean
  inspected: number
  affected: number
  summary: SummaryRow[]
  mails: AffectedMail[]
  errors: string[]
  next: DryRunCursor | null
}

const result = ref<Totals | null>(null)
/** Counts the runs, so the pages of an outdated run are dropped. */
let generation = 0
const ran = ref<RunResult | null>(null)
const error = ref('')
const loading = ref(false)
const confirming = ref(false)
const only = ref<SummaryRow | null>(null)
/** Keep fetching the next page until the end. */
const autoLoad = ref(false)

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

/**
 * Fetches pages until one brings new affected mails, or there are no more.
 * A page without any is not worth a click, so the next one is requested right away.
 */
async function fetchPages(first: boolean): Promise<void> {
  const mine = ++generation
  loading.value = true
  error.value = ''
  try {
    let cursor = first ? null : (result.value?.next ?? null)
    for (;;) {
      const page = await dryRun(props.rule.name, store.yaml.value, cursor)
      if (mine !== generation) return
      const before = first && cursor === null ? null : result.value
      result.value = {
        actionsEnabled: page.actions_enabled,
        inspected: (before?.inspected ?? 0) + page.inspected,
        affected: (before?.affected ?? 0) + page.affected,
        summary: mergeSummary(before?.summary ?? [], page.summary),
        mails: [...(before?.mails ?? []), ...page.mails],
        errors: [...(before?.errors ?? []), ...page.errors],
        next: page.next,
      }
      if (page.next === null || (page.mails.length > 0 && !autoLoad.value)) return
      cursor = page.next
    }
  } catch (e) {
    if (mine !== generation) return
    error.value = describeError(e)
  } finally {
    if (mine === generation) loading.value = false
  }
}

watch(autoLoad, (on) => {
  if (on && result.value?.next && !loading.value) void loadMore()
})

async function start(): Promise<void> {
  ran.value = null
  confirming.value = false
  only.value = null
  result.value = null
  await fetchPages(true)
}

function loadMore(): Promise<void> {
  return fetchPages(false)
}

async function apply(): Promise<void> {
  confirming.value = false
  loading.value = true
  error.value = ''
  try {
    ran.value = await runNow(props.rule.name)
  } catch (e) {
    error.value = describeError(e)
    loading.value = false
    return
  }
  result.value = null
  only.value = null
  await fetchPages(true)
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
      <label class="auto-load" title="Keep loading the next page until the end">
        <input v-model="autoLoad" type="checkbox" /> Load all pages
      </label>
    </div>
    <MailSpinner v-if="loading" label="Looking at the mails…" />
    <p v-if="result && blocked" class="hint blocked">{{ blocked }}</p>
    <p v-if="confirming" class="confirm">
      Apply {{ result?.next ? 'at least ' : '' }}{{ plannedCount }} changes to
      {{ result?.affected }} mails{{
        result?.next ? ' (not all looked at yet; the rule is applied to all)' : ''
      }}
      for real?
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
        Looked at {{ result.inspected }} mails{{ result.next ? ' so far' : '' }},
        {{ result.affected }} would be affected{{
          noopCount ? `, ${noopCount} steps change nothing` : ''
        }}.
      </p>
      <p v-if="result.summary.length === 0 && !result.next && !loading" class="hint empty">
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
      <button
        v-if="result.next"
        type="button"
        class="load-more"
        :disabled="loading"
        @click="loadMore"
      >
        Load more…
      </button>
    </template>
  </section>
</template>
