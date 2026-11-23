import { PreviewLink, PreviewScreen } from '../../../components/PreviewScreen';

export default function Report() {
  return (
    <PreviewScreen title="Report" actions={<>
      <PreviewLink href="/library" replace>Return to Library</PreviewLink>
      <PreviewLink href="/library/session" replace>Back to Session</PreviewLink>
    </>}>
      This is where you will review feedback after a practice session. Feedback and scores are not available in this preview.
    </PreviewScreen>
  );
}
