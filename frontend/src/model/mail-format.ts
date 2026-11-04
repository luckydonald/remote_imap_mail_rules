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
  'html{overflow:hidden}body{font:14px/1.5 -apple-system,system-ui,sans-serif;margin:0;word-wrap:break-word;color:#1d1d1f;background:#fff}' +
  'img{max-width:100%;height:auto}a{color:#0a66d6}blockquote{margin:0 0 0 8px;padding-left:12px;border-left:3px solid #ddd;color:#555}'

/** The policy of the mail iframe: nothing loads except our own parts, embedded images and, when allowed, remote images. The server's sanitizer is the first layer, this the second. */
export function framePolicy(remoteImages: boolean): string {
  const images = remoteImages ? "img-src 'self' data: https: http:" : "img-src 'self' data:"
  return `default-src 'none'; ${images}; style-src 'unsafe-inline'`
}

/** The sandboxed iframe's document: the server's sanitized HTML with a base style, a content security policy and links that open in a new tab. */
export function frameDocument(html: string, remoteImages = false): string {
  const policy = framePolicy(remoteImages)
  return `<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${policy}"><base target="_blank"><style>${FRAME_STYLE}</style><body>${html}</body>`
}

const FLAG_ADDED: Record<string, string> = {
  '\\Seen': 'marked it read',
  '\\Flagged': 'flagged it',
  '\\Answered': 'marked it answered',
  '\\Draft': 'marked it as a draft',
  '\\Deleted': 'marked it deleted',
}
const FLAG_REMOVED: Record<string, string> = {
  '\\Seen': 'marked it unread',
  '\\Flagged': 'removed the flag',
  '\\Answered': 'removed the answered mark',
  '\\Draft': 'removed the draft mark',
  '\\Deleted': 'removed the deleted mark',
}

function names(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

/** A `user_action` entry, e.g. `You marked it read`; changes the server saw that no rule made. */
export function describeUserAction(detail: Record<string, unknown>): string {
  if (detail.type === 'gone')
    return 'It left the folder (moved or deleted by you or another client)'
  if (detail.type !== 'flags') return 'Changed by you'
  const parts = [
    ...names(detail.added).map((flag) => FLAG_ADDED[flag] ?? `added the keyword ${flag}`),
    ...names(detail.removed).map((flag) => FLAG_REMOVED[flag] ?? `removed the keyword ${flag}`),
  ]
  return parts.length ? `You ${parts.join(' and ')}` : 'Changed by you'
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
      return describeUserAction(event.detail)
  }
}
