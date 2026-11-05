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
    } catch {
      if (generation === this.generation) {
        await this.persist(() => this.store.clear());
        if (generation === this.generation)
          this.update({
            status: "error",
            error: "Sign-in failed. Please try again.",
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
        } catch {
          if (generation === this.generation) await this.signOut();
          throw new Error("Sign in again.");
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
    const token = await this.accessToken();
    if (generation !== this.generation) throw new Error("Session ended");
    const result = await this.api(
      "/v1/account/deletion",
      "POST",
      { confirmation: "DELETE" },
      token,
    );
    if (
      !result ||
      typeof result !== "object" ||
      !("accepted" in result) ||
      result.accepted !== true
    )
      throw new Error("Deletion was not accepted");
    if (generation !== this.generation) return;
    const signedOutGeneration = this.generation + 1;
    await this.signOut();
    if (signedOutGeneration !== this.generation) return;
    this.update({
      status: "anonymous",
      notice:
        "Deletion requested. Your account and scores will be removed within 30 days.",
    });
  }
  async restore() {
    const generation = ++this.generation;
    try {
      const refresh = await this.store.read();
      if (!refresh || generation !== this.generation) return;
      this.update({ status: "loading" });
      await this.accept(
        await this.api("/v1/auth/refresh", "POST", { refresh_token: refresh }),
        generation,
      );
    } catch {
      if (generation === this.generation) await this.signOut();
    }
  }
}
