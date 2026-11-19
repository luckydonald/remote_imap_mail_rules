import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import TimeInput from '@/components/condition/TimeInput.vue'
import { ALLOW_VARS } from '@/model/context'

it('emits independent template variables and retains a value variable across kind changes', async () => {
  const wrapper = mount(TimeInput, {
    props: { modelValue: { relative: true, value: '7d' } },
    global: { provide: { [ALLOW_VARS]: true } },
  })
  const kind = wrapper.findAll('.field-value')[0]!
  const value = wrapper.findAll('.field-value')[1]!

  await value.get('button').trigger('click')
  expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([{ relative: true, value: { var: 'value' } }])
  await wrapper.setProps({ modelValue: { relative: true, value: { var: 'value' } } })
  await kind.get('select').setValue('absolute')
  expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([{ relative: false, value: { var: 'value' } }])

  await wrapper.setProps({ modelValue: { relative: false, value: { var: 'cutoff' } } })
  await kind.get('button').trigger('click')
  expect(wrapper.emitted('update:modelValue')?.[2]).toEqual([{ relative: { var: 'relative' }, value: { var: 'cutoff' } }])
})

it('offers a plain text value when a variable chooses the kind', async () => {
  const relative = { var: 'kind' }
  const wrapper = mount(TimeInput, {
    props: { modelValue: { relative, value: '7d' } },
    global: { provide: { [ALLOW_VARS]: true } },
  })
  const input = wrapper.get<HTMLInputElement>('[aria-label="Date value"]')
  expect(input.element.type).toBe('text')
  expect(input.attributes('pattern')).toBeUndefined()
  await input.setValue('2026-11-18T08:54:08Z')
  expect(wrapper.emitted('update:modelValue')).toEqual([
    [{ relative, value: '2026-11-18T08:54:08Z' }],
  ])
})

it('keeps the fixed date controls outside templates', async () => {
  const wrapper = mount(TimeInput, {
    props: { modelValue: { value: '2026-11-18T08:54:08Z' } },
  })
  expect(wrapper.findAll('button')).toHaveLength(0)
  await wrapper.get('input[type=datetime-local]').setValue('2026-11-19T09:00')
  expect(wrapper.emitted('update:modelValue')).toEqual([
    [{ value: '2026-11-19T09:00:00Z' }],
  ])
})
