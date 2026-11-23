import { ApiError, DELETION_PENDING } from "./errors";
import type { Transport } from "./session";
export { ApiError } from "./errors";

// Reads a 403 body only to recognize the pending-deletion code.
async function refusalCode(response: Response) {
  try {
    const body: unknown = await response.json();
    return body &&
      typeof body === "object" &&
      "detail" in body &&
      body.detail === DELETION_PENDING
      ? DELETION_PENDING
      : undefined;
  } catch {
    return undefined;
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
    if (!response.ok)
      throw new ApiError(
        response.status,
        response.status === 403 ? await refusalCode(response) : undefined,
      );
    return response.json() as Promise<unknown>;
  };
}
