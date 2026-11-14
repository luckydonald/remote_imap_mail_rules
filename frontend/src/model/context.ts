import type { InjectionKey } from 'vue'

/** Whether `Var`s can be used here, which is true inside the content of a template. */
export const ALLOW_VARS: InjectionKey<boolean> = Symbol('allow-vars')

/** Name of the template whose content is being edited, if any: a use inside it may not lead back to it. */
export const CURRENT_TEMPLATE: InjectionKey<string> = Symbol('current-template')
