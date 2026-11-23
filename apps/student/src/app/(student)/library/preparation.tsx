import { PreviewLink, PreviewScreen } from '../../../components/PreviewScreen';

export default function Preparation() {
  return (
    <PreviewScreen title="Preparation" actions={<>
      <PreviewLink href="/library/session">Preview Session</PreviewLink>
      <PreviewLink href="/library" replace>Back to Library</PreviewLink>
    </>}>
      This is where you will prepare for a practice session. Preparation materials are not available in this preview.
    </PreviewScreen>
  );
}
