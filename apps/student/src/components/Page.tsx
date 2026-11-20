import { useState, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export const colors = {
  background: '#f7f9fc',
  heading: '#17263c',
  body: '#34445b',
  accent: '#214f88',
  accentPressed: '#17375e',
  noticeBackground: '#e7effa',
  noticeBorder: '#245691',
  danger: '#9b2626',
  dangerPressed: '#741c1c',
  surface: '#ffffff',
};

export function PageFrame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right', 'bottom']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.content}>
          <Text style={styles.brand}>Case-Study-Tech</Text>
          <Text accessibilityRole="header" style={styles.title}>{title}</Text>
          {children}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

export function BodyText({ children }: { children: ReactNode }) {
  return <Text style={styles.body}>{children}</Text>;
}

export function AlertText({ children }: { children: ReactNode }) {
  return <Text accessibilityRole="alert" accessibilityLiveRegion="assertive" style={styles.alert}>{children}</Text>;
}

type ActionButtonProps = {
  label: string;
  onPress(): void;
  disabled?: boolean;
  tone?: 'primary' | 'danger' | 'quiet';
};

export function ActionButton({ label, onPress, disabled = false, tone = 'primary' }: ActionButtonProps) {
  const [focused, setFocused] = useState(false);
  const [pressed, setPressed] = useState(false);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onPressIn={() => setPressed(true)}
      onPressOut={() => setPressed(false)}
      style={[
        styles.button,
        styles[tone],
        pressed && pressedStyles[tone],
        focused && styles.focused,
        disabled && styles.disabled,
      ]}
    >
      <Text style={[styles.buttonText, tone === 'quiet' && styles.quietText]}>{label}</Text>
    </Pressable>
  );
}

export const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  scroll: { flexGrow: 1, padding: 24 },
  content: { width: '100%', maxWidth: 680, alignSelf: 'center', gap: 24, paddingVertical: 16 },
  brand: { color: colors.body, fontSize: 16, fontWeight: '600' },
  title: { color: colors.heading, fontSize: 32, fontWeight: '700' },
  body: { color: colors.body, fontSize: 18, lineHeight: 28 },
  alert: { color: colors.danger, fontSize: 18, lineHeight: 28, fontWeight: '600' },
  actions: { gap: 16, alignItems: 'flex-start' },
  button: { minHeight: 48, maxWidth: '100%', justifyContent: 'center', borderWidth: 3, borderColor: 'transparent', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 12 },
  primary: { backgroundColor: colors.accent },
  danger: { backgroundColor: colors.danger },
  quiet: { backgroundColor: colors.surface, borderColor: colors.accent },
  focused: { borderColor: colors.surface, outlineColor: colors.heading, outlineWidth: 3, outlineStyle: 'solid' },
  disabled: { opacity: 0.6 },
  buttonText: { color: colors.surface, fontSize: 17, fontWeight: '600' },
  quietText: { color: colors.accent },
});

const pressedStyles = StyleSheet.create({
  primary: { backgroundColor: colors.accentPressed },
  danger: { backgroundColor: colors.dangerPressed },
  quiet: { backgroundColor: colors.noticeBackground },
});
