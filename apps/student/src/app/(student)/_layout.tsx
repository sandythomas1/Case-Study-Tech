import { Tabs } from "expo-router";
export default function StudentLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false }}>
      <Tabs.Screen name="index" options={{ title: "Library" }} />
      <Tabs.Screen name="history" options={{ title: "History" }} />
      <Tabs.Screen name="account" options={{ title: "Account" }} />
      <Tabs.Screen name="preparation" options={{ href: null }} />
      <Tabs.Screen name="session" options={{ href: null }} />
      <Tabs.Screen name="report" options={{ href: null }} />
    </Tabs>
  );
}
