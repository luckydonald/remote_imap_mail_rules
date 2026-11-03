/** Display helpers of the mail browser. */

import { describeLoggedAction } from './dry-run'
import type { Address, Folder, MailEvent } from './mail-api'

const ICONS: Record<string, string> = {
  inbox: '📥',
  sent: '📤',
  drafts: '📝',
  trash: '🗑️',
  junk: '🚫',
  archive: '🗄️',
  flagged: '🚩',
  all: '📚',
}

export function folderIcon(folder: Folder): string {
  return (folder.special_use && ICONS[folder.special_use]) || '📁'
}

/** Indents sub folders by their depth and shows only the last path segment. */
export function folderLabel(folder: Folder): { name: string; depth: number } {
  const parts = folder.delimiter
    ? folder.display_name.split(folder.delimiter)
    : [folder.display_name]
  return { name: parts[parts.length - 1] ?? folder.display_name, depth: parts.length - 1 }
}

export function personLabel(address: Address): string {
  return address.name || address.address || '(unknown)'
}

export function addressList(addresses: Address[]): string {
  return addresses
    .map((item) =>
      item.name && item.address ? `${item.name} <${item.address}>` : personLabel(item),
    )
    .join(', ')
}

/** The time for today's mails, the date otherwise, like Apple Mail's list. */
export function shortDate(iso: string | null, now = new Date()): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const sameDay = date.toDateString() === now.toDateString()
  return sameDay
    ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString([], { year: 'numeric', month: '2-digit', day: '2-digit' })
}

export function fullDate(iso: string | null): string {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString()
}

export function fileSize(bytes: number | null): string {
  if (bytes === null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const FRAME_STYLE =
  'body{font:14px/1.5 -apple-system,system-ui,sans-serif;margin:0;word-wrap:break-word;color:#1d1d1f;background:#fff}' +
  'img{max-width:100%;height:auto}a{color:#0a66d6}blockquote{margin:0 0 0 8px;padding-left:12px;border-left:3px solid #ddd;color:#555}'

/** The sandboxed iframe's document: the server's sanitized HTML with a base style and links that open in a new tab. */
export function frameDocument(html: string): string {
  return `<!doctype html><meta charset="utf-8"><base target="_blank"><style>${FRAME_STYLE}</style><body>${html}</body>`
}

/** One line of the action log, e.g. `Matched the rule "invoices" (new)`. */
export function eventLabel(event: MailEvent): string {
  const rule = event.rule_name ?? '(unnamed rule)'
  const how = typeof event.detail.match_kind === 'string' ? ` (${event.detail.match_kind})` : ''
  switch (event.kind) {
    case 'first_seen':
      return 'First seen'
    case 'rule_match':
      return `Matched the rule "${rule}"${how}`
    case 'action':
      return `${describeLoggedAction(event.detail)} by the rule "${rule}"`
    case 'user_action':
      return 'Changed by you'
  }
}
