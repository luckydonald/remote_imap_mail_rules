import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { h } from 'vue'

vi.mock('@luckylu.cy/sync-todo-overlay/vue', () => ({
  default: { render: () => h('div', { 'data-overlay': '' }) },
}))

const url = 'https://todos.example.test'
const token = 'example-embed-key'

function mockConfig(body: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(body))),
  )
}

beforeEach(() => vi.resetModules())
afterEach(() => vi.unstubAllGlobals())

it.each([
  [
    { url, token },
    { url, token },
  ],
  [{ url, token: null }, { url }],
  [{ token }, { token }],
  [{ url: null, token: null }, {}],
  [{ url: '', token: '' }, {}],
])('passes only configured props from %j', async (todo_overlay, expected) => {
  mockConfig({ todo_overlay })
  const { default: TodoOverlay } = await import('@/components/TodoOverlay.vue')
  const wrapper = mount(TodoOverlay)
  await vi.dynamicImportSettled()
  await flushPromises()

  expect(wrapper.get('[data-overlay]').attributes()).toEqual({ 'data-overlay': '', ...expected })
  wrapper.unmount()
})

it.each([
  { todo_overlay: null },
  {},
  { todo_overlay: { url: 123, token } },
  { todo_overlay: { url, token: false } },
  { todo_overlay: [] },
  null,
])('keeps the overlay unmounted for %j', async (body) => {
  mockConfig(body)
  const { default: TodoOverlay } = await import('@/components/TodoOverlay.vue')
  const wrapper = mount(TodoOverlay)
  await flushPromises()
  expect(wrapper.find('[data-overlay]').exists()).toBe(false)
  wrapper.unmount()
})

it('has no configuration when the request fails', async () => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')))
  const { fetchTodoOverlayConfig } = await import('@/model/client-config')
  expect(await fetchTodoOverlayConfig()).toBeNull()
})

it('shares a single request with Sentry', async () => {
  const sentry = { dsn: 'https://key@errors.example.test/1', release: 'abc', traces_sample_rate: 0 }
  mockConfig({ sentry, todo_overlay: { url, token } })
  const { fetchTodoOverlayConfig } = await import('@/model/client-config')
  const { fetchSentryConfig } = await import('@/sentry')
  expect(await Promise.all([fetchTodoOverlayConfig(), fetchSentryConfig()])).toEqual([
    { url, token },
    sentry,
  ])
  expect(fetch).toHaveBeenCalledTimes(1)
})
