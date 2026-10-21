import type { TokenStore } from "./session";
// Web credentials live only in memory. No localStorage, cookies or IndexedDB.
let refresh: string | null = null;
export const tokenStore: TokenStore = {
  read: async () => refresh,
  write: async (value) => {
    refresh = value;
  },
  clear: async () => {
    refresh = null;
  },
};
