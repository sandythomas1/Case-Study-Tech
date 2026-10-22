import {
  GoogleSignin,
  isSuccessResponse,
} from "@react-native-google-signin/google-signin";
import { Button } from "react-native";
type Props = {
  onCredential(credential: string): void;
  onError(): void;
  disabled: boolean;
};
export function GoogleButton({ onCredential, onError, disabled }: Props) {
  async function signIn() {
    try {
      const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
      if (!webClientId) throw new Error("Configuration unavailable");
      GoogleSignin.configure({
        webClientId,
        iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
        offlineAccess: false,
      });
      await GoogleSignin.hasPlayServices();
      const response = await GoogleSignin.signIn();
      if (isSuccessResponse(response) && response.data.idToken)
        onCredential(response.data.idToken);
    } catch {
      onError();
    }
  }
  return (
    <Button
      title="Continue with Google"
      disabled={disabled}
      onPress={() => {
        void signIn();
      }}
    />
  );
}
export async function signOutGoogle() {
  await GoogleSignin.signOut();
}
