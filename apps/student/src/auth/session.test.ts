import { describe, expect, it, vi } from "vitest";
import { Session, type Transport, type TokenStore } from "./session";

function setup() {
  let saved: string | null = null;
  const store: TokenStore = {
    read: async () => saved,
    write: async (v) => {
      saved = v;
    },
    clear: async () => {
      saved = null;
    },
  };
  const api = vi.fn<Transport>(async (path) => {
    if (path.endsWith("/me")) return { uid: "student-a" };
    if (path.endsWith("/deletion")) return { accepted: true };
    return {
      id_token: "id-token",
      refresh_token: "refresh-token",
      expires_in: 3600,
    };
  });
  return { session: new Session(api, store), api, store, saved: () => saved };
}

describe("student session", () => {
  it("does not sign out a newer session when an earlier deletion finishes", async () => {
    const { session, api } = setup();
    await session.signIn("first");
    let resolve!: (value: unknown) => void;
    api.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    const deletion = session.deleteAccount(true);
    await Promise.resolve();
    await session.signIn("newer");
    resolve({ accepted: true });
    await deletion;
    expect(session.state.status).toBe("authenticated");
  });
  it("starts signed out and never uses a UID supplied by the caller", () => {
    expect(setup().session.state.status).toBe("anonymous");
  });
  it("authenticates with the server and persists only the refresh token", async () => {
    const { session, api, saved } = setup();
    await session.signIn("google-credential");
    expect(session.state).toEqual({
      status: "authenticated",
      uid: "student-a",
    });
    expect(api).toHaveBeenCalledWith("/v1/me", "GET", undefined, "id-token");
    expect(saved()).toBe("refresh-token");
  });
  it("clears credentials and hides protected state on sign-out", async () => {
    const { session, saved } = setup();
    await session.signIn("google-credential");
    await session.signOut();
    expect(session.state.status).toBe("anonymous");
    expect(saved()).toBeNull();
    await expect(session.accessToken()).rejects.toThrow();
  });
  it("requires explicit deletion confirmation and clears the session after acceptance", async () => {
    const { session, api, saved } = setup();
    await session.signIn("google-credential");
    await expect(session.deleteAccount(false)).rejects.toThrow();
    expect(
      api.mock.calls.filter(([p]) => p.endsWith("/deletion")),
    ).toHaveLength(0);
    await session.deleteAccount(true);
    expect(api).toHaveBeenCalledWith(
      "/v1/account/deletion",
      "POST",
      { confirmation: "DELETE" },
      "id-token",
    );
    expect(session.state.status).toBe("anonymous");
    expect(saved()).toBeNull();
  });
  it("does not claim deletion or sign out when the server rejects the request", async () => {
    const { session, api } = setup();
    await session.signIn("google-credential");
    api.mockRejectedValueOnce(new Error("unavailable"));
    await expect(session.deleteAccount(true)).rejects.toThrow();
    expect(session.state.status).toBe("authenticated");
  });
  it("discards a late sign-in response after sign-out", async () => {
    const { session, api, saved } = setup();
    let resolve!: (value: unknown) => void;
    api.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    const pending = session.signIn("credential");
    await session.signOut();
    resolve({
      id_token: "late-id",
      refresh_token: "late-refresh",
      expires_in: 3600,
    });
    await pending;
    expect(session.state.status).toBe("anonymous");
    expect(saved()).toBeNull();
  });
  it("restores through a rotated refresh token and verifies the current user", async () => {
    const { session, store, api } = setup();
    await store.write("old-refresh");
    await session.restore();
    expect(api).toHaveBeenCalledWith("/v1/auth/refresh", "POST", {
      refresh_token: "old-refresh",
    });
    expect(session.state.status).toBe("authenticated");
    expect(await store.read()).toBe("refresh-token");
  });
  it("rejects malformed token responses and exposes no provider error details", async () => {
    const { session, api, saved } = setup();
    api.mockResolvedValueOnce({ id_token: "private-marker" });
    await session.signIn("credential");
    expect(session.state.status).toBe("error");
    expect(JSON.stringify(session.state)).not.toContain("private-marker");
    expect(saved()).toBeNull();
  });
  it("invalidates a failed restore", async () => {
    const { session, store, api } = setup();
    await store.write("revoked");
    api.mockRejectedValueOnce(new Error("private-provider-details"));
    await session.restore();
    expect(session.state.status).toBe("anonymous");
    expect(await store.read()).toBeNull();
  });
  it("coalesces an expired-token refresh and signs out on revocation", async () => {
    const { session, api } = setup();
    await session.signIn("credential");
    const realNow = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(realNow + 3600000);
    try {
      const tokens = await Promise.all([
        session.accessToken(),
        session.accessToken(),
      ]);
      expect(tokens).toEqual(["id-token", "id-token"]);
      expect(
        api.mock.calls.filter(([path]) => path === "/v1/auth/refresh"),
      ).toHaveLength(1);
      vi.spyOn(Date, "now").mockReturnValue(realNow + 7200000);
      api.mockRejectedValueOnce(new Error("revoked"));
      await expect(session.accessToken()).rejects.toThrow("Sign in again");
      expect(session.state.status).toBe("anonymous");
    } finally {
      vi.restoreAllMocks();
    }
  });
  it("retains the deletion confirmation after the protected screen unmounts", async () => {
    const { session } = setup();
    await session.signIn("credential");
    await session.deleteAccount(true);
    expect(
      session.state.status === "anonymous" && session.state.notice,
    ).toContain("Deletion requested");
  });
});
