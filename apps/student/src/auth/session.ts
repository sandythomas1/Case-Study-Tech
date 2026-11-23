import { isDeletionPending, isUnauthorized } from "./errors";

export type TokenStore = {
  read(): Promise<string | null>;
  write(value: string): Promise<void>;
  clear(): Promise<void>;
};
export type Transport = (
  path: string,
  method: "GET" | "POST",
  body?: unknown,
  token?: string,
) => Promise<unknown>;
export type SessionState =
  | {
      status: "anonymous" | "loading" | "error";
      error?: string;
      notice?: string;
    }
  | { status: "authenticated"; uid: string };
const messages = {
  signInFailed: "We couldn't sign you in. Please try again in a moment.",
  beingDeleted: "This account is being deleted, so you can't sign in to it.",
  expired: "Your sign-in expired. Please sign in again.",
  notDeleted:
    "Your sign-in expired, so your account was not deleted. Sign in again to request deletion.",
  unconfirmed:
    "We couldn't confirm your deletion request because your sign-in ended. If you can still sign in, please request deletion again.",
  deletionReceived:
    "We received your request to delete your account. Your account and saved scores will be permanently deleted within 30 days.",
};

// What the student sees after a session ends without them signing out.
function endedBy(error: unknown, notice: string): SessionState {
  return isDeletionPending(error)
    ? { status: "error", error: messages.beingDeleted }
    : { status: "anonymous", notice };
}

// A refresh failure that signed the student out; `generation` is the signed-out one.
class SessionExpired extends Error {
  constructor(readonly generation: number) {
    super("Sign in again.");
  }
}

export class Session {
  private snapshot: SessionState = { status: "anonymous" };
  private generation = 0;
  private bundle?: { id: string; refresh: string; expires: number };
  private listeners = new Set<() => void>();
  private persistence = Promise.resolve();
  private refreshing?: Promise<string>;
  constructor(
    private api: Transport,
    private store: TokenStore,
  ) {}
  get state() {
    return this.snapshot;
  }
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private update(state: SessionState) {
    this.snapshot = state;
    this.listeners.forEach((listener) => listener());
  }
  private persist(action: () => Promise<void>) {
    this.persistence = this.persistence.catch(() => undefined).then(action);
    return this.persistence;
  }
  // Signs out, then explains why, unless a newer sign-in started meanwhile.
  private async end(reason: SessionState) {
    const ended = this.generation + 1;
    await this.signOut();
    if (ended === this.generation) this.update(reason);
    return ended;
  }
  private async accept(value: unknown, generation: number) {
    if (generation !== this.generation) return;
    if (!value || typeof value !== "object") throw new Error("Invalid session");
    const t = value as Record<string, unknown>;
    if (
      typeof t.id_token !== "string" ||
      !t.id_token ||
      typeof t.refresh_token !== "string" ||
      !t.refresh_token ||
      typeof t.expires_in !== "number" ||
      t.expires_in <= 0 ||
      t.expires_in > 3600
    )
      throw new Error("Invalid session");
    const me = await this.api("/v1/me", "GET", undefined, t.id_token);
    if (
      !me ||
      typeof me !== "object" ||
      !("uid" in me) ||
      typeof me.uid !== "string" ||
      !me.uid
    )
      throw new Error("Invalid session");
    if (generation !== this.generation) return;
    const refresh = t.refresh_token;
    await this.persist(async () => {
      if (generation === this.generation) await this.store.write(refresh);
    });
    if (generation !== this.generation) return;
    this.bundle = {
      id: t.id_token,
      refresh,
      expires: Date.now() + t.expires_in * 1000,
    };
    this.update({ status: "authenticated", uid: me.uid });
  }
  async signIn(credential: string) {
    const generation = ++this.generation;
    this.bundle = undefined;
    this.update({ status: "loading" });
    try {
      await this.accept(
        await this.api("/v1/auth/google", "POST", { credential }),
        generation,
      );
    } catch (error) {
      if (generation === this.generation) {
        await this.persist(() => this.store.clear());
        if (generation === this.generation)
          this.update({
            status: "error",
            error: isDeletionPending(error)
              ? messages.beingDeleted
              : messages.signInFailed,
          });
      }
    }
  }
  async signOut() {
    ++this.generation;
    this.bundle = undefined;
    this.refreshing = undefined;
    this.update({ status: "anonymous" });
    await this.persist(() => this.store.clear());
  }
  async accessToken(): Promise<string> {
    if (this.state.status !== "authenticated" || !this.bundle)
      throw new Error("Signed out");
    if (this.bundle.expires > Date.now() + 60000) return this.bundle.id;
    if (!this.refreshing) {
      const generation = this.generation;
      const refresh = this.bundle.refresh;
      this.refreshing = (async () => {
        try {
          await this.accept(
            await this.api("/v1/auth/refresh", "POST", {
              refresh_token: refresh,
            }),
            generation,
          );
          if (generation !== this.generation || !this.bundle)
            throw new Error("Session ended");
          return this.bundle.id;
        } catch (error) {
          if (generation === this.generation) {
            const ended = await this.end(endedBy(error, messages.expired));
            if (!isDeletionPending(error)) throw new SessionExpired(ended);
          }
          throw new Error("Sign in again.", { cause: error });
        } finally {
          if (generation === this.generation) this.refreshing = undefined;
        }
      })();
    }
    return this.refreshing;
  }
  async deleteAccount(confirmed: boolean) {
    if (!confirmed) throw new Error("Confirmation required");
    const generation = this.generation;
    let token: string;
    try {
      token = await this.accessToken();
    } catch (error) {
      // The request was never sent, so nothing was deleted.
      if (
        error instanceof SessionExpired &&
        error.generation === this.generation
      )
        this.update({ status: "anonymous", notice: messages.notDeleted });
      throw error;
    }
    if (generation !== this.generation) throw new Error("Session ended");
    let result: unknown;
    try {
      result = await this.api(
        "/v1/account/deletion",
        "POST",
        { confirmation: "DELETE" },
        token,
      );
    } catch (error) {
      // An accepted request disables and revokes the account, so a 401 here
      // can follow a request whose 202 was lost. Say only what is known.
      if (isUnauthorized(error) && generation === this.generation)
        await this.end({ status: "anonymous", notice: messages.unconfirmed });
      throw error;
    }
    if (
      !result ||
      typeof result !== "object" ||
      !("accepted" in result) ||
      result.accepted !== true
    )
      throw new Error("Deletion was not accepted");
    if (generation !== this.generation) return;
    await this.end({ status: "anonymous", notice: messages.deletionReceived });
  }
  async restore() {
    const generation = ++this.generation;
    let saved = false;
    try {
      const refresh = await this.store.read();
      if (!refresh || generation !== this.generation) return;
      saved = true;
      this.update({ status: "loading" });
      await this.accept(
        await this.api("/v1/auth/refresh", "POST", { refresh_token: refresh }),
        generation,
      );
    } catch (error) {
      if (generation !== this.generation) return;
      if (saved) await this.end(endedBy(error, messages.expired));
      else await this.signOut();
    }
  }
}
