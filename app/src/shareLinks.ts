import type { Router } from "vue-router";

/** A share link's hash is `#team=<code>`: open the team and show it in the builder. */
export function openShareLinks(router: Router, receive: (code: string) => unknown): void {
  router.addRoute({
    path: "/team=:code",
    redirect: (to) => {
      receive(to.params.code as string);
      return "/build";
    },
  });
}
