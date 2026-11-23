import * as SecureStore from "expo-secure-store";
import type { TokenStore } from "./session";
const key = "cst.refresh-token";
export const tokenStore: TokenStore = {
  read: () => SecureStore.getItemAsync(key),
  write: (value) =>
    SecureStore.setItemAsync(key, value, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    }),
  clear: () => SecureStore.deleteItemAsync(key),
};
