import { Tabs } from 'expo-router';
import { Text } from 'react-native';

export default function StudentLayout() {
  return (
    <Tabs screenOptions={{
      headerShown: false,
      tabBarActiveTintColor: '#173e70',
      tabBarInactiveTintColor: '#34445b',
      tabBarActiveBackgroundColor: '#e7effa',
      tabBarIconStyle: { display: 'none' },
      tabBarItemStyle: { minHeight: 56 },
      tabBarStyle: { height: 'auto', minHeight: 64 },
      tabBarLabel: ({ children, focused, color }) => (
        <Text style={{ color, fontSize: 14, padding: 8, textAlign: 'center', fontWeight: focused ? '700' : '400', textDecorationLine: focused ? 'underline' : 'none' }}>{children}</Text>
      ),
    }}>
      <Tabs.Screen name="library" options={{ title: 'Library', tabBarAccessibilityLabel: 'Library' }} />
      <Tabs.Screen name="history" options={{ title: 'Score history', tabBarAccessibilityLabel: 'Score history' }} />
      <Tabs.Screen name="account" options={{ title: 'Account', tabBarAccessibilityLabel: 'Account' }} />
    </Tabs>
  );
}
