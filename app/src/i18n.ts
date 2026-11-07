import { createI18n } from "vue-i18n";

type Messages = Record<string, unknown>;

/** Each file of a locale folder holds the messages of its own top-level namespaces. */
function collect(modules: Record<string, { default: Messages }>): Messages {
  return Object.assign({}, ...Object.values(modules).map((module) => module.default));
}

const en = collect(import.meta.glob("@/locales/en/*.ts", { eager: true }));
const zhCN = collect(import.meta.glob("@/locales/zh-CN/*.ts", { eager: true }));

export const LOCALES = { en: "English", "zh-CN": "简体中文" } as const;
export type Locale = keyof typeof LOCALES;

const STORAGE_KEY = "siralim-planner.locale";

function chosen(): Locale | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored && stored in LOCALES ? (stored as Locale) : null;
  } catch {
    return null;
  }
}

function detect(): Locale {
  return /^zh/i.test(navigator.languages?.[0] ?? navigator.language) ? "zh-CN" : "en";
}

export const locale: Locale = chosen() ?? detect();

/** The data pack and every label are loaded once per page, so a change reloads the page. */
export function setLocale(next: Locale): void {
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // The choice then applies to this visit only through the reload below.
  }
  location.reload();
}

export const i18n = createI18n<[Messages], Locale, false>({
  legacy: false,
  locale,
  fallbackLocale: "en",
  messages: { en, "zh-CN": zhCN },
});

/** A class's name in the page language; the data names classes in English. */
export function className(name: string): string {
  return i18n.global.te(`classes.${name}`) ? i18n.global.t(`classes.${name}`) : name;
}

/** A stat's name in the page language; the data names stats in English. */
export function statName(name: string): string {
  const key = `reference.stats.${name.toLowerCase()}`;
  return i18n.global.te(key) ? i18n.global.t(key) : name;
}

/** For code outside components; the locale never changes without a reload. */
export const t = i18n.global.t;
