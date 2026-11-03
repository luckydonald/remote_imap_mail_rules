import { inject, provide, type InjectionKey } from "vue";
import type { Store } from "./store";

export const STORE: InjectionKey<Store> = Symbol("store");
/** Whether `Var`s can be used here, which is true inside the content of a template. */
export const ALLOW_VARS: InjectionKey<boolean> = Symbol("allow-vars");

export function provideStore(store: Store): void {
  provide(STORE, store);
}

export function useStore(): Store {
  const store = inject(STORE);
  if (!store) throw new Error("no store provided");
  return store;
}
