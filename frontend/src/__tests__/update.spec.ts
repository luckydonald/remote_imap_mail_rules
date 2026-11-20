import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import UpdateBanner from '@/components/UpdateBanner.vue'
import { setOnline } from '@/model/online'
import { applyUpdate, setUpUpdates, updateAvailable, updateDismissed } from '@/model/update'
import { useStore } from '@/model/store'

type Options = {
  onNeedRefresh?: () => void
  onRegisteredSW?: (url: string, registration: ServiceWorkerRegistration | undefined) => void
}

/** A stand-in for `registerSW` that keeps the callbacks and the `updateSW` it hands out. */
function fakeRegister() {
  const updateSW = vi.fn<(reload?: boolean) => Promise<void>>().mockResolvedValue()
  let options: Options = {}
  const register = vi.fn<(given: Options) => typeof updateSW>((given) => {
    options = given
    return updateSW
  })
  return { register: register as never, updateSW, options: () => options }
}

beforeEach(() => {
  setActivePinia(createPinia())
  updateAvailable.value = false
  updateDismissed.value = false
  sessionStorage.clear()
  setOnline(true)
  vi.useFakeTimers()
})
afterEach(() => vi.useRealTimers())

describe('app updates', () => {
  it('tells when a new version waits and reloads only when asked', async () => {
    const fake = fakeRegister()
    setUpUpdates(fake.register)
    expect(updateAvailable.value).toBe(false)
    fake.options().onNeedRefresh?.()
    expect(updateAvailable.value).toBe(true)
    expect(fake.updateSW).not.toHaveBeenCalled()
    await applyUpdate()
    expect(fake.updateSW).toHaveBeenCalledWith(true)
  })

  it('looks for a new version every hour, when visible again and when the network is back', async () => {
    const fake = fakeRegister()
    const update = vi.fn<() => Promise<void>>().mockResolvedValue()
    setUpUpdates(fake.register, 1000)
    fake.options().onRegisteredSW?.('/sw.js', { update } as unknown as ServiceWorkerRegistration)
    await vi.advanceTimersByTimeAsync(2500)
    expect(update).toHaveBeenCalledTimes(2)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(update).toHaveBeenCalledTimes(3)
    window.dispatchEvent(new Event('online'))
    expect(update).toHaveBeenCalledTimes(4)
  })

  it('does not look while offline, and a failing check is not an error', async () => {
    const fake = fakeRegister()
    const update = vi.fn<() => Promise<void>>().mockRejectedValue(new TypeError('offline'))
    setUpUpdates(fake.register, 1000)
    fake.options().onRegisteredSW?.('/sw.js', { update } as unknown as ServiceWorkerRegistration)
    setOnline(false)
    await vi.advanceTimersByTimeAsync(3000)
    expect(update).not.toHaveBeenCalled()
    setOnline(true)
    await vi.advanceTimersByTimeAsync(1000)
    expect(update).toHaveBeenCalledTimes(1)
  })

  it('the banner offers Reload and Later, and warns about unsaved edits', async () => {
    const fake = fakeRegister()
    setUpUpdates(fake.register)
    const wrapper = mount(UpdateBanner)
    expect(wrapper.find('.update-banner').exists()).toBe(false)
    fake.options().onNeedRefresh?.()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('new version')
    expect(wrapper.text()).not.toContain('Unsaved')
    const store = useStore()
    store.markSaved('rules.yml', undefined, 'rules: []\n# the server text differs')
    await wrapper.vm.$nextTick()
    await wrapper.findAll('button')[0]!.trigger('click')
    expect(fake.updateSW).toHaveBeenCalledWith(true)
    await wrapper.findAll('button')[1]!.trigger('click')
    expect(wrapper.find('.update-banner').exists()).toBe(false)
  })

  it('applies a worker that already waits at page load, once per session', async () => {
    const fake = fakeRegister()
    setUpUpdates(fake.register)
    const waiting = {
      waiting: {},
      update: vi.fn<() => void>(),
    } as unknown as ServiceWorkerRegistration
    fake.options().onRegisteredSW?.('/sw.js', waiting)
    expect(fake.updateSW).toHaveBeenCalledTimes(1)
    // The reload did not clear it: no second automatic apply, the banner stays the way.
    fake.options().onRegisteredSW?.('/sw.js', waiting)
    expect(fake.updateSW).toHaveBeenCalledTimes(1)
    // A load without a waiting worker rearms it.
    fake
      .options()
      .onRegisteredSW?.('/sw.js', {
        update: vi.fn<() => void>(),
      } as unknown as ServiceWorkerRegistration)
    fake.options().onRegisteredSW?.('/sw.js', waiting)
    expect(fake.updateSW).toHaveBeenCalledTimes(2)
  })

  it('remembers Later for the session', async () => {
    const fake = fakeRegister()
    setUpUpdates(fake.register)
    const wrapper = mount(UpdateBanner)
    fake.options().onNeedRefresh?.()
    await wrapper.vm.$nextTick()
    await wrapper.findAll('button')[1]!.trigger('click')
    expect(sessionStorage.getItem('update-later')).toBe('1')
  })
})
