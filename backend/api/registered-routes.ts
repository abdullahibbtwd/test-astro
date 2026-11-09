import type { FastifyInstance } from "fastify";

export type RegisteredRoute = { method: string; path: string };

/** Normalize OpenAPI `{id}` and Fastify `:id` to a comparable Fastify form. */
export function normalizeRoutePath(path: string): string {
  return path.replace(/\{([^}]+)\}/g, ":$1");
}

export function routeKey(method: string, path: string): string {
  return `${method.toUpperCase()} ${normalizeRoutePath(path)}`;
}

/**
 * Attach an onRoute collector before other plugins/routes register.
 * Call once at the start of buildLocalApp.
 */
export function attachRouteCollector(app: FastifyInstance): RegisteredRoute[] {
  const routes: RegisteredRoute[] = [];
  app.addHook("onRoute", (opts) => {
    const methods = Array.isArray(opts.method) ? opts.method : [opts.method];
    for (const method of methods) {
      const m = String(method).toUpperCase();
      if (m === "HEAD" || m === "OPTIONS") continue;
      routes.push({ method: m, path: opts.url });
    }
  });
  return routes;
}

export function listRegisteredRouteKeys(routes: RegisteredRoute[]): string[] {
  return [...new Set(routes.map((r) => routeKey(r.method, r.path)))].sort();
}
