import { useEffect, useRef } from "react";
import { Text } from "react-native";
type GoogleId = {
  initialize(options: {
    client_id: string;
    callback(response: { credential: string }): void;
  }): void;
  renderButton(
    element: HTMLElement,
    options: Record<string, string | number>,
  ): void;
  disableAutoSelect(): void;
};
declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } };
  }
}
type Props = {
  onCredential(credential: string): void;
  onError(): void;
  disabled: boolean;
};
export function GoogleButton({ onCredential, onError, disabled }: Props) {
  const element = useRef<HTMLDivElement>(null);
  const configured = !!process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
  useEffect(() => {
    if (!configured) return;
    let active = true;
    const initialize = () => {
      if (!active || !element.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID!,
        callback: (response) => {
          if (active) onCredential(response.credential);
        },
      });
      window.google.accounts.id.renderButton(element.current, {
        type: "standard",
        theme: "outline",
        size: "large",
        text: "continue_with",
        width: 280,
      });
    };
    let script = document.querySelector<HTMLScriptElement>(
      "script[data-cst-google]",
    );
    if (!script) {
      script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.dataset.cstGoogle = "true";
      document.head.append(script);
    }
    script.addEventListener("load", initialize);
    script.addEventListener("error", onError);
    initialize();
    return () => {
      active = false;
      script?.removeEventListener("load", initialize);
      script?.removeEventListener("error", onError);
    };
  }, [configured, onCredential, onError]);
  if (!configured)
    return (
      <Text accessibilityRole="alert">
        Google sign-in is not available yet. Please try again later.
      </Text>
    );
  return (
    <div
      ref={element}
      aria-disabled={disabled}
      style={{
        pointerEvents: disabled ? "none" : "auto",
        opacity: disabled ? 0.6 : 1,
      }}
    />
  );
}
export async function signOutGoogle() {
  window.google?.accounts.id.disableAutoSelect();
}
