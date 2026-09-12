/**
 * Dynamic props for preview - this file gets updated by the Flask backend
 * when users change style settings in the UI
 */

import { TransitionVideoProps } from './main-transition-video';

// Updated preview props - now using individual words instead of lines
export const previewProps: Omit<TransitionVideoProps, 'fps' | 'width' | 'height'> = {
  "words": [
    "not",
    "to", 
    "overanalyze",
    "competitors",
    "or",
    "get",
    "overwhelmed",
    "by",
    "them."
  ],
  "startTimes": [
    0,
    0.2,
    0.4,
    0.8,
    1.2,
    1.4,
    1.6,
    2.0,
    2.2
  ],
  "duration": 3,
  "style": {
    "fontFamily": "Montserrat",
    "fontSize": 80,
    "fontColor": "#000000",
    "backgroundColor": "#ffffff",
    "fontWeight": "normal",
    "glow": {
      "strengths": [6, 10, 60]
    },
    "layout": {
      "mode": "relativeToCenterOffsets",
      "avgStepPct": 6,
      "jitterPct": 3,
      "safeLeftPct": 30,
      "safeRightPct": 80,
      "accent": "longestWord",
      "accentColor": "#6ab0a1",
      "accentScale": 1.1,
      "accentBold": true,
      "startTopPct": 30,
      "lineHeight": 0.9,
      "relativeOffsets": [-10, 10, -5, 5]
    }
  },
  "layoutSeed": 420
};
