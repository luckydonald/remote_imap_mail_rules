import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MailPreview from '@/components/MailPreview.vue'
import type { Detail } from '@/model/mail-api'

const detail = (subject: string) =>
  ({
    subject,
    sender: { name: 'Sender', address: 's@example.com' },
    to: [{ name: 'Me', address: 'me@example.com' }],
    date: '2026-10-01T08:30:00Z',
  }) as unknown as Detail

describe('MailPreview', () => {
  it('shows subject, sender, recipient and date', () => {
    const text = mount(MailPreview, { props: { detail: detail('Hello') } }).text()
    expect(text).toContain('Hello')
    expect(text).toContain('Sender <s@example.com>')
    expect(text).toContain('Me <me@example.com>')
  })
  it('names a mail without subject', () => {
    expect(mount(MailPreview, { props: { detail: detail('') } }).text()).toContain('(no subject)')
  })
})
