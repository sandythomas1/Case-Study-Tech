import { PreviewLink, PreviewScreen } from '../../../components/PreviewScreen';

export default function Library() {
  return (
    <PreviewScreen title="Library" actions={<PreviewLink href="/library/preparation">Preview Preparation</PreviewLink>}>
      This is where you will find counseling practice cases. Cases are not available in this preview.
    </PreviewScreen>
  );
}
