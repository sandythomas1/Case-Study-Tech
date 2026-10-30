import { Link, type Href } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export function PreviewLink({ href, children, replace = false }: { href: Href; children: string; replace?: boolean }) {
  const [focused, setFocused] = useState(false);
  const [pressed, setPressed] = useState(false);
  return (
    <Link href={href} replace={replace} asChild>
      <Pressable
        accessibilityRole="link"
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onPressIn={() => setPressed(true)}
        onPressOut={() => setPressed(false)}
        // Router's asChild slot needs a flattened object rather than a style callback.
        style={StyleSheet.flatten([styles.link, focused && styles.focused, pressed && styles.pressed])}
      >
        <Text style={styles.linkText}>{children}</Text>
      </Pressable>
    </Link>
  );
}

export function PreviewScreen({ title, children, actions }: { title: string; children: string; actions?: ReactNode }) {
  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right', 'bottom']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.content}>
          <Text style={styles.brand}>Case-Study-Tech</Text>
          <Text accessibilityRole="header" style={styles.title}>{title}</Text>
          <View style={styles.notice}>
            <Text style={styles.noticeTitle}>Navigation preview</Text>
            <Text style={styles.body}>Explore the planned screens. Practice, scores, and accounts are not available in this preview.</Text>
          </View>
          <Text style={styles.body}>{children}</Text>
          {actions && <View style={styles.actions}>{actions}</View>}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f7f9fc' },
  scroll: { flexGrow: 1, padding: 24 },
  content: { width: '100%', maxWidth: 680, alignSelf: 'center', gap: 24, paddingVertical: 16 },
  brand: { color: '#34445b', fontSize: 16, fontWeight: '600' },
  title: { color: '#17263c', fontSize: 32, fontWeight: '700' },
  notice: { backgroundColor: '#e7effa', borderLeftWidth: 4, borderLeftColor: '#245691', padding: 20, gap: 10 },
  noticeTitle: { color: '#17263c', fontSize: 18, fontWeight: '700' },
  body: { color: '#34445b', fontSize: 18, lineHeight: 28 },
  actions: { gap: 16, alignItems: 'flex-start' },
  link: { minHeight: 48, maxWidth: '100%', justifyContent: 'center', borderWidth: 3, borderColor: 'transparent', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#214f88' },
  focused: { borderColor: '#ffffff', outlineColor: '#17263c', outlineWidth: 3, outlineStyle: 'solid' },
  pressed: { backgroundColor: '#17375e' },
  linkText: { color: '#ffffff', fontSize: 17, fontWeight: '600', textDecorationLine: 'underline' },
});
