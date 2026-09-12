import { Composition } from "remotion";
import { MainTransitionVideo } from "./main-transition-video";
import { previewProps } from "./preview-props";

const SimpleTest: React.FC = () => {
  return (
    <div style={{ backgroundColor: 'white', color: 'black', fontSize: 48, padding: 40 }}>
      <div>Hello World</div>
    </div>
  );
};

// Super simple test component
const SimpleTextTest: React.FC = () => {
  return (
    <div style={{ 
      backgroundColor: '#ffffff', 
      width: '100%', 
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: 48,
      color: '#000000'
    }}>
      Test Text
    </div>
  );
};

const defaultFps = parseInt(process.env.TRANSITION_VIDEO_FPS as string) || 24;
const defaultWidth = parseInt(process.env.TRANSITION_VIDEO_WIDTH as string) || 1080;
const defaultHeight = parseInt(process.env.TRANSITION_VIDEO_HEIGHT as string) || 1920;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SimpleTest"
        component={SimpleTest}
        durationInFrames={150}
        fps={defaultFps}
        width={defaultWidth}
        height={defaultHeight}
      />
      <Composition
        id="SimpleTextTest"
        component={SimpleTextTest}
        durationInFrames={150}
        fps={defaultFps}
        width={defaultWidth}
        height={defaultHeight}
      />
      <Composition
        id="MainVideoTransition"
        component={MainTransitionVideo}
        durationInFrames={150}
        fps={defaultFps}
        width={defaultWidth}
        height={defaultHeight}
        defaultProps={previewProps}
      />
    </>
  );
};