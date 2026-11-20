import { PreviewLink, PreviewScreen } from '../../../components/PreviewScreen';

export default function Session() {
  return (
    <PreviewScreen title="Session" actions={<>
      <PreviewLink href="/library/report">Preview Report</PreviewLink>
      <PreviewLink href="/library/preparation" replace>Back to Preparation</PreviewLink>
    </>}>
      This is where you will practice counseling with a simulated client. Conversations are not available in this preview.
    </PreviewScreen>
  );
}
