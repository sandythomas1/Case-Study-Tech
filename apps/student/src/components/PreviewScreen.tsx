import { Link, type Href } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { BodyText, PageFrame, styles as pageStyles } from './Page';

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
    <PageFrame title={title}>
      <View style={styles.notice}>
        <Text style={styles.noticeTitle}>Navigation preview</Text>
        <BodyText>Explore the planned screens. Practice and scores are not available in this preview.</BodyText>
      </View>
      <BodyText>{children}</BodyText>
      {actions && <View style={pageStyles.actions}>{actions}</View>}
    </PageFrame>
  );
}

const styles = StyleSheet.create({
  notice: { backgroundColor: '#e7effa', borderLeftWidth: 4, borderLeftColor: '#245691', padding: 20, gap: 10 },
  noticeTitle: { color: '#17263c', fontSize: 18, fontWeight: '700' },
  link: { minHeight: 48, maxWidth: '100%', justifyContent: 'center', borderWidth: 3, borderColor: 'transparent', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#214f88' },
  focused: { borderColor: '#ffffff', outlineColor: '#17263c', outlineWidth: 3, outlineStyle: 'solid' },
  pressed: { backgroundColor: '#17375e' },
  linkText: { color: '#ffffff', fontSize: 17, fontWeight: '600', textDecorationLine: 'underline' },
});
