import { Session } from "./session";
import { tokenStore } from "./tokenStore";
import { createTransport } from "./transport";
const apiUrl = process.env.EXPO_PUBLIC_API_URL;
export const session = new Session(
  apiUrl
    ? createTransport(apiUrl, __DEV__)
    : async () => {
        throw new Error("Sign-in unavailable");
      },
  tokenStore,
);
