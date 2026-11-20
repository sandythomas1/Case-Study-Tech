import { PreviewLink, PreviewScreen } from '../components/PreviewScreen';

export default function Welcome() {
  return (
    <PreviewScreen title="Welcome" actions={<PreviewLink href="/library">Explore the preview</PreviewLink>}>
      Welcome to Case-Study-Tech. Explore the planned counseling practice screens.
    </PreviewScreen>
  );
}
