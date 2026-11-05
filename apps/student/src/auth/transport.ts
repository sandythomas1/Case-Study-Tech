import type { Transport } from "./session";
export class ApiError extends Error {
  constructor(readonly status: number) {
    super(
      status === 401 ? "Sign in again." : "The request could not be completed.",
    );
  }
}
export function createTransport(base: string, allowLocal = false): Transport {
  const url = new URL(base);
  if (
    (url.protocol !== "https:" &&
      !(
        allowLocal &&
        url.protocol === "http:" &&
        ["localhost", "127.0.0.1"].includes(url.hostname)
      )) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  )
    throw new Error("A secure API address is required.");
  return async (path, method, body, token) => {
    const response = await fetch(
      `${url.toString().replace(/\/$/, "")}${path}`,
      {
        method,
        credentials: "omit",
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      },
    );
    if (!response.ok) throw new ApiError(response.status);
    return response.json() as Promise<unknown>;
  };
}
