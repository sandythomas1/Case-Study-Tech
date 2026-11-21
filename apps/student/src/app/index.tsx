import { PreviewLink, PreviewScreen } from '../components/PreviewScreen';

export default function Welcome() {
  return (
    <PreviewScreen title="Welcome" actions={<PreviewLink href="/sign-in">Sign in to explore</PreviewLink>}>
      Explore the planned counseling practice screens.
    </PreviewScreen>
  );
}
