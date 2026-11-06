import type { InjectionKey } from "vue";

/** The id of the open dialog's footer, where DialogFooter puts its actions. */
export const DIALOG_FOOTER: InjectionKey<string> = Symbol("dialog footer");

/** The id of the open dialog's head, where content puts actions that apply to the whole dialog. */
export const DIALOG_ACTIONS: InjectionKey<string> = Symbol("dialog actions");
