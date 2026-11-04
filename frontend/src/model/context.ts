import type { InjectionKey } from 'vue'

/** Whether `Var`s can be used here, which is true inside the content of a template. */
export const ALLOW_VARS: InjectionKey<boolean> = Symbol('allow-vars')
