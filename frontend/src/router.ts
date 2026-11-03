import {
  createRouter,
  createWebHistory,
  type RouteLocationRaw,
  type RouteRecordRaw,
  type Router,
  type RouterHistory,
} from 'vue-router'
import type { Place } from '@/model/mail-store'
import type { View } from '@/model/store'

/** The top level screens of the app; a route names the one it shows in `meta.screen`. */
export type Screen = 'rules' | 'accounts' | 'mail'

declare module 'vue-router' {
  interface RouteMeta {
    screen: Screen
  }
}

// The components stay in `AppShell`, which renders the screen the route names.
const empty = { render: () => null }

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: { name: 'rules-yaml' } },
  { path: '/rules', name: 'rules-yaml', component: empty, meta: { screen: 'rules' } },
  {
    path: '/rules/templates',
    name: 'rules-templates',
    component: empty,
    meta: { screen: 'rules' },
  },
  { path: '/rules/:index(\\d+)', name: 'rule', component: empty, meta: { screen: 'rules' } },
  { path: '/accounts', name: 'accounts', component: empty, meta: { screen: 'accounts' } },
  // The mail browser nests account, folder and message. A folder name goes in as one encoded segment.
  {
    path: '/mail',
    name: 'mail',
    component: empty,
    meta: { screen: 'mail' },
    children: [
      {
        path: ':accountId',
        name: 'mail-account',
        component: empty,
        children: [
          {
            path: ':folder',
            name: 'mail-folder',
            component: empty,
            children: [{ path: ':uid(\\d+)', name: 'mail-message', component: empty }],
          },
        ],
      },
    ],
  },
  { path: '/:rest(.*)*', redirect: { name: 'rules-yaml' } },
]

/** Real paths: the server answers unknown paths with `index.html` (`SpaStaticFiles`), the Vite dev server does so too. */
export function createAppRouter(history: RouterHistory = createWebHistory()): Router {
  return createRouter({ history, routes })
}

/** The route of a rule editor view. */
export function locationOfView(view: View): RouteLocationRaw {
  switch (view.kind) {
    case 'rule':
      return { name: 'rule', params: { index: view.index } }
    case 'templates':
      return { name: 'rules-templates' }
    case 'yaml':
      return { name: 'rules-yaml' }
  }
}

/** The editor view a route name stands for, `null` for the other screens. */
export function viewOfRoute(name: unknown, params: Record<string, unknown>): View | null {
  if (name === 'rule') return { kind: 'rule', index: Number(params.index) }
  if (name === 'rules-templates') return { kind: 'templates' }
  if (name === 'rules-yaml') return { kind: 'yaml' }
  return null
}

/** The route of a mail place, as deep as the place goes. */
export function locationOfMail(place: Place): RouteLocationRaw {
  if (place.accountId === null) return { name: 'mail' }
  if (place.folder === null) return { name: 'mail-account', params: { accountId: place.accountId } }
  const params = { accountId: place.accountId, folder: place.folder }
  if (place.uid === null) return { name: 'mail-folder', params }
  return { name: 'mail-message', params: { ...params, uid: place.uid } }
}

/** The mail place of a route; empty parts are `null`. */
export function mailPlaceOfRoute(params: Record<string, unknown>): Place {
  const text = (value: unknown): string | null => (typeof value === 'string' ? value : null)
  const uid = text(params.uid)
  return {
    accountId: text(params.accountId),
    folder: text(params.folder),
    uid: uid === null ? null : Number(uid),
  }
}
