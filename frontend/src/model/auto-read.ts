/** Decides when the mail view marks the open mail read by itself (the admin's `auto_read` setting). */

import type { AutoRead } from './settings-api'

/** How close to the bottom (in pixels) counts as scrolled to the end. */
const SLACK = 8

/** Whether the end of a mail (its bottom edge) is in view, the page's or a scroll column's bottom edge being `viewBottom`; a mail that fits is always at its end. */
export function reachedEnd(endBottom: number, viewBottom: number): boolean {
  return endBottom <= viewBottom + SLACK
}

/** The lowest visible y of `el`: the window's bottom, cut by every ancestor that scrolls or clips (the desktop layout scrolls the page, narrow ones a column). */
export function visibleBottom(el: Element): number {
  let bottom = window.innerHeight
  for (let parent = el.parentElement; parent !== null; parent = parent.parentElement) {
    if (getComputedStyle(parent).overflowY !== 'visible')
      bottom = Math.min(bottom, parent.getBoundingClientRect().bottom)
  }
  return bottom
}

/** Whether a freshly opened mail waits for an automatic read: the setting is on, the server may write and the mail is unread. */
export function wantsAutoRead(mode: AutoRead, seen: boolean, actionsEnabled: boolean): boolean {
  return mode !== 'off' && actionsEnabled && !seen
}

/** Whether the waiting mail is read now: at once for `open`, once the end of the mail was reached for `scrolled`. */
export function autoReadDue(mode: AutoRead, atEnd: boolean): boolean {
  if (mode === 'open') return true
  return mode === 'scrolled' && atEnd
}
