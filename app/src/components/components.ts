import { shallowReactive } from "vue";
import { object, type ObjectPage } from "@/data";
import { memoRequest } from "@/data/memo";

const pages = shallowReactive(new Map<string, ObjectPage>());

/** A team component's page. */
export const loadComponent = memoRequest((id: string) =>
  object(id).then((page) => {
    pages.set(id, page);
    return page;
  }),
);

/** The page when loaded; reading it in a render starts the load and re-renders when it arrives. */
export function component(id: string): ObjectPage | undefined {
  if (!pages.has(id)) loadComponent(id).catch(() => {});
  return pages.get(id);
}
