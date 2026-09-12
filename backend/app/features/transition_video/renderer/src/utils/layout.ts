/**
 * Layout utilities for transition video generation
 * Handles diagonal drift positioning and accent word detection
 */

export interface DriftConfig {
  avgStepPct: number;      // Average drift per word (percentage of width)
  jitterPct: number;       // Random jitter amount (±percentage)
  safeLeftPct: number;     // Left margin (percentage)
  safeRightPct: number;    // Right margin (percentage)
  seed: number;            // Random seed for reproducible layouts
}

export interface AccentConfig {
  mode: 'none' | 'longestWord' | 'manual';
  accentColor: string;
  accentScale: number;
}

export interface WordInfo {
  text: string;
  startTime: number;
  widthPx?: number;
  centerPct?: number;   // Horizontal center position (percentage)
  isAccent?: boolean;   // Whether this word should be accented
  debugOffset?: number; // Debug: the offset value that was selected for this word
  topPercent?: number;  // Vertical position (percentage)
}

export interface LayoutConfig {
  mode: 'centered' | 'diagonalDrift' | 'relativeOffsets' | 'relativeToCenterOffsets';
  avgStepPct: number;
  jitterPct: number;
  safeLeftPct: number;
  safeRightPct: number;
  accent: 'none' | 'longestWord' | 'manual';
  accentColor: string;
  accentScale: number;
  accentBold: boolean;
  startTopPct: number;
  lineHeight: number;
  centerAtPct?: number; // When set, positions the text block so its center is at this percentage from top (ignores startTopPct)
  /**
   * Array of offsets (in percentage points) to apply relative to either:
   * - For 'relativeOffsets' mode: relative to the previous word's position
   * - For 'relativeToCenterOffsets' mode: relative to the center of the screen (50%)
   * 
   * Positive values move the word right, negative left. These offsets will be 
   * clamped by safeLeftPct / safeRightPct.
   */
  relativeOffsets?: number[];
}

/**
 * Simple deterministic random number generator (Mulberry32)
 * Ensures reproducible layouts across renders
 */
function mulberry32(a: number) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Apply diagonal drift positioning to words
 */
export function applyDiagonalDrift(
  words: WordInfo[],
  config: DriftConfig
): WordInfo[] {
  let x = 50; // Start at center (50%)
  const rand = mulberry32(config.seed);

  return words.map((word, index) => {
    if (index > 0) {
      // Calculate drift for this word
      const drift = config.avgStepPct + (rand() * 2 - 1) * config.jitterPct;
      x += drift;
    }

    // Clamp to safe boundaries
    x = Math.min(config.safeRightPct, Math.max(config.safeLeftPct, x));

    return {
      ...word,
      centerPct: x
    };
  });
}

/**
 * Apply centered positioning to words (evenly spaced vertically)
 */
export function applyCenteredLayout(words: WordInfo[]): WordInfo[] {
  return words.map(word => ({
    ...word,
    centerPct: 50 // Always centered horizontally
  }));
}

/**
 * Detect and mark accent words based on configuration
 */
export function applyAccentDetection(
  words: WordInfo[],
  config: AccentConfig
): WordInfo[] {
  if (config.mode === 'none') {
    return words.map(word => ({ ...word, isAccent: false }));
  }

  if (config.mode === 'longestWord') {
    // Find the longest word by character count
    let longestIndex = 0;
    let longestLength = 0;

    words.forEach((word, index) => {
      if (word.text.length > longestLength) {
        longestLength = word.text.length;
        longestIndex = index;
      }
    });

    return words.map((word, index) => ({
      ...word,
      isAccent: index === longestIndex
    }));
  }

  if (config.mode === 'manual') {
    // For manual mode, look for words wrapped in {{accent}} tags
    // This would be handled at the text preprocessing level
    return words.map(word => ({
      ...word,
      isAccent: word.text.includes('{{accent}}') || word.text.includes('{{/accent}}')
    }));
  }

  return words;
}

/**
 * Apply randomly selected offsets relative to center (50%). Each word's 
 * horizontal position is calculated by taking the center position (50%) and 
 * adding a randomly selected offset from the `relativeOffsets` array. Safe 
 * boundaries are enforced by checking the actual left and right edges of words.
 */
export function applyRelativeToCenterOffsets(
  words: WordInfo[],
  offsets: number[] | undefined,
  safeLeftPct: number,
  safeRightPct: number,
  fontSize: number = 48,
  fontFamily: string = "Times New Roman, serif",
  seed: number = 12345,
  frameWidth: number
): WordInfo[] {
  
  if (!offsets || offsets.length === 0) {
    // Fallback to centered if no offsets supplied
    return applyCenteredLayout(words);
  }

  const result: WordInfo[] = [];
  let lastOffsetIndex = -1; // Track the last selected offset to avoid repeats
  
  // Create deterministic random number generator
  const rand = mulberry32(seed);
  
  // Create canvas for accurate text measurement with safety checks
  let canvas: HTMLCanvasElement | null = null;
  let ctx: CanvasRenderingContext2D | null = null;
  
  try {
    if (typeof document !== 'undefined') {
      canvas = document.createElement('canvas');
      ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.font = `${fontSize}px ${fontFamily}`;
      }
    }
  } catch (error) {
    console.warn('Canvas context creation failed, using fallback measurements:', error);
  }
  
  const getWordWidthPct = (text: string): number => {
    if (ctx) {
      try {
        const widthPx = ctx.measureText(text).width;
        return (widthPx / frameWidth) * 100 * 1.2; // 20% buffer for safety
      } catch (error) {
        console.warn('Canvas measureText failed, using fallback:', error);
      }
    }
    // Fallback: estimate based on character count
    const avgCharWidth = fontSize * 0.6; // Rough estimate
    const widthPx = text.length * avgCharWidth;
    return (widthPx / frameWidth) * 100 * 1.2; // 20% buffer for safety
  };

  words.forEach((word, index) => {
    let selectedOffset;
    let currentX;
    
    if (index === 0) {
      // First word should always be exactly centered (no offset)
      selectedOffset = undefined;
      currentX = 50;
    } else {
      // Randomly select an offset from the array, avoiding the last selection
      let randomIndex;
      if (offsets.length === 1) {
        randomIndex = 0;
      } else {
        do {
          randomIndex = Math.floor(rand() * offsets.length);
        } while (randomIndex === lastOffsetIndex);
      }
      
      selectedOffset = offsets[randomIndex];
      lastOffsetIndex = randomIndex;
      currentX = 50 + selectedOffset; // Always relative to center (50%)
    }

    // Calculate actual word edges using measured width
    const wordWidthPct = getWordWidthPct(word.text);
    const leftEdge = currentX - (wordWidthPct / 2);
    const rightEdge = currentX + (wordWidthPct / 2);

    // Clamp based on word edges, not center
    if (leftEdge < safeLeftPct) {
      currentX = safeLeftPct + (wordWidthPct / 2);
    } else if (rightEdge > safeRightPct) {
      currentX = safeRightPct - (wordWidthPct / 2);
    }

    result.push({ 
      ...word, 
      centerPct: currentX, 
      debugOffset: selectedOffset 
    });
  });

  return result;
}

/**
 * Calculate the total height of a text block in percentage points
 */
export function calculateTextBlockHeight(
  wordCount: number,
  lineHeight: number,
  fontSize: number,
  frameHeight: number
): number {
  if (wordCount === 0) return 0;
  
  // Each line takes up fontSize * lineHeight pixels
  const lineHeightPx = fontSize * lineHeight;
  const lineHeightPct = (lineHeightPx / frameHeight) * 100;
  
  // Total height = height of all lines (wordCount - 1 gaps between lines + 1 line height)
  // This gives us the span from top of first line to bottom of last line
  const totalHeightPct = (wordCount - 1) * lineHeightPct + lineHeightPct;
  
  return totalHeightPct;
}

/**
 * Calculate vertical positions for words based on line height
 * Uses startTopPct and lineHeight multiplier for precise control
 * If centerAtPct is set, calculates startTopPct to center the text block at the specified percentage
 */
export function calculateVerticalPositions(
  words: WordInfo[],
  startTopPct: number,
  lineHeight: number,
  fontSize: number,
  frameHeight: number,
  centerAtPct?: number
): WordInfo[] {
  let effectiveStartTopPct = startTopPct;
  
  // If centerAtPct is specified, calculate the start position to center the text block at that percentage
  if (centerAtPct !== undefined && words.length > 0) {
    const totalHeight = calculateTextBlockHeight(words.length, lineHeight, fontSize, frameHeight);
    // Position the text block so its center is at centerAtPct: centerAtPct - (totalHeight / 2)
    effectiveStartTopPct = centerAtPct - (totalHeight / 2);
  }
  
  return words.map((word, index) => {
    // Calculate position based on line height multiplier
    // Convert font size * line height to percentage of frame height
    const lineHeightPx = fontSize * lineHeight;
    const lineHeightPct = (lineHeightPx / frameHeight) * 100;
    
    const topPercent = effectiveStartTopPct + (index * lineHeightPct);
    
    return {
      ...word,
      topPercent
    };
  });
}

/**
 * Apply randomly selected relative offsets. The first word is
 * always centered (50%). Every subsequent word's horizontal position is
 * calculated by taking the previous word's position and adding a randomly
 * selected offset from the `relativeOffsets` array. Safe boundaries are enforced by
 * checking the actual left and right edges of words using precise text measurement.
 */
export function applyRelativeOffsets(
  words: WordInfo[],
  offsets: number[] | undefined,
  safeLeftPct: number,
  safeRightPct: number,
  fontSize: number = 48,
  fontFamily: string = "Times New Roman, serif",
  seed: number = 12345,
  frameWidth: number
): WordInfo[] {
  if (!offsets || offsets.length === 0) {
    // Fallback to centered if no offsets supplied
    return applyCenteredLayout(words);
  }

  const result: WordInfo[] = [];
  let currentX = 50; // first word centered
  let lastOffsetIndex = -1; // Track the last selected offset to avoid repeats
  
  // Create deterministic random number generator
  const rand = mulberry32(seed);
  
  // Create canvas for accurate text measurement with safety checks
  let canvas: HTMLCanvasElement | null = null;
  let ctx: CanvasRenderingContext2D | null = null;
  
  try {
    if (typeof document !== 'undefined') {
      canvas = document.createElement('canvas');
      ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.font = `${fontSize}px ${fontFamily}`;
      }
    }
  } catch (error) {
    console.warn('Canvas context creation failed, using fallback measurements:', error);
  }
  
  const getWordWidthPct = (text: string): number => {
    if (ctx) {
      try {
        const widthPx = ctx.measureText(text).width;
        return (widthPx / frameWidth) * 100 * 1.2; // 20% buffer for safety
      } catch (error) {
        console.warn('Canvas measureText failed, using fallback:', error);
      }
    }
    // Fallback: estimate based on character count
    const avgCharWidth = fontSize * 0.6; // Rough estimate
    const widthPx = text.length * avgCharWidth;
    return (widthPx / frameWidth) * 100 * 1.2; // 20% buffer for safety
  };

  words.forEach((word, index) => {
    const wordWidthPct = getWordWidthPct(word.text);
    
    if (index === 0) {
      // First word – center, but still check boundaries
      const leftEdge = currentX - (wordWidthPct / 2);
      const rightEdge = currentX + (wordWidthPct / 2);
      
      if (leftEdge < safeLeftPct) {
        currentX = safeLeftPct + (wordWidthPct / 2);
      } else if (rightEdge > safeRightPct) {
        currentX = safeRightPct - (wordWidthPct / 2);
      }
      
      result.push({ ...word, centerPct: currentX, debugOffset: undefined });
      return;
    }

    // Randomly select an offset from the array, avoiding the last selection
    let randomIndex;
    if (offsets.length === 1) {
      // If only one offset, we have no choice but to use it
      randomIndex = 0;
    } else {
      // Keep selecting until we get a different index than the last one
      do {
        randomIndex = Math.floor(rand() * offsets.length);
      } while (randomIndex === lastOffsetIndex);
    }
    
    const offset = offsets[randomIndex];
    lastOffsetIndex = randomIndex;
    currentX += offset;

    // Calculate actual word edges using measured width
    const leftEdge = currentX - (wordWidthPct / 2);
    const rightEdge = currentX + (wordWidthPct / 2);

    // Clamp based on word edges, not center
    if (leftEdge < safeLeftPct) {
      currentX = safeLeftPct + (wordWidthPct / 2);
    } else if (rightEdge > safeRightPct) {
      currentX = safeRightPct - (wordWidthPct / 2);
    }

    result.push({ ...word, centerPct: currentX, debugOffset: offset });
  });

  return result;
}

/**
 * Main layout function that applies the specified layout mode
 */
export function applyLayout(
  words: WordInfo[],
  config: LayoutConfig,
  layoutSeed: number,
  fontSize: number,
  fontFamily: string,
  frameWidth: number,
  frameHeight: number
): WordInfo[] {
   let processedWords = [...words];

   // Apply horizontal positioning based on mode
   if (config.mode === 'diagonalDrift') {
     const driftConfig: DriftConfig = {
       avgStepPct: config.avgStepPct,
       jitterPct: config.jitterPct,
       safeLeftPct: config.safeLeftPct,
       safeRightPct: config.safeRightPct,
       seed: layoutSeed
     };
     processedWords = applyDiagonalDrift(processedWords, driftConfig);
     } else if (config.mode === 'relativeOffsets') {
     processedWords = applyRelativeOffsets(
       processedWords,
       config.relativeOffsets,
       config.safeLeftPct,
       config.safeRightPct,
       fontSize,
       fontFamily,
       layoutSeed,
       frameWidth
     );
   } else if (config.mode === 'relativeToCenterOffsets') {
     processedWords = applyRelativeToCenterOffsets(
       processedWords,
       config.relativeOffsets,
       config.safeLeftPct,
       config.safeRightPct,
       fontSize,
       fontFamily,
       layoutSeed,
       frameWidth
     );
   } else {
     processedWords = applyCenteredLayout(processedWords);
   }

   // Apply accent detection
   const accentConfig: AccentConfig = {
     mode: config.accent,
     accentColor: config.accentColor,
     accentScale: config.accentScale
   };
   processedWords = applyAccentDetection(processedWords, accentConfig);

   // Apply vertical positioning
   processedWords = calculateVerticalPositions(
     processedWords, 
     config.startTopPct, 
     config.lineHeight, 
     fontSize,
     frameHeight,
     config.centerAtPct
   );

   return processedWords;
 }

/**
 * Measure text width using canvas context (for more accurate positioning)
 * This is a utility function for when precise measurements are needed
 */
export function measureTextWidth(
  text: string,
  fontFamily: string,
  fontSize: number,
  ctx?: CanvasRenderingContext2D
): number {
  try {
    // Create a temporary canvas if none provided
    const canvas = ctx?.canvas || (typeof document !== 'undefined' ? document.createElement('canvas') : null);
    if (!canvas) {
      // Fallback if no canvas available
      const avgCharWidth = fontSize * 0.6;
      return text.length * avgCharWidth;
    }
    
    const context = ctx || canvas.getContext('2d');
    if (!context) {
      // Fallback if no context available
      const avgCharWidth = fontSize * 0.6;
      return text.length * avgCharWidth;
    }
    
    context.font = `${fontSize}px ${fontFamily}`;
    return context.measureText(text).width * 1.2; // 20% buffer for safety
  } catch (error) {
    console.warn('Canvas measureText failed, using character-based fallback:', error);
    // Fallback: estimate based on character count
    const avgCharWidth = fontSize * 0.6;
    return text.length * avgCharWidth * 1.2; // 20% buffer for safety
  }
}

/**
 * Generate a random layout seed
 * Used when creating new videos to ensure variety
 */
export function generateLayoutSeed(): number {
  return Math.floor(Math.random() * 1000000);
}