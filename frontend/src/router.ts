import {
  createRouter,
  createWebHashHistory,
  type RouteLocationRaw,
  type RouteRecordRaw,
  type Router,
  type RouterHistory,
} from 'vue-router'
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
  { path: '/mail', name: 'mail', component: empty, meta: { screen: 'mail' } },
  { path: '/:rest(.*)*', redirect: { name: 'rules-yaml' } },
]

/** A hash history works with any static hosting, the server needs no fallback route. */
export function createAppRouter(history: RouterHistory = createWebHashHistory()): Router {
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
