import React, { useMemo, useEffect } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  getInputProps,
} from "remotion";
import { applyLayout, WordInfo, LayoutConfig } from "./utils/layout";
import { loadGoogleFontSync } from "./utils/font-loader";

export interface TransitionVideoProps {
  words: string[];
  startTimes: number[];
  duration: number;
  fps: number;
  width: number;
  height: number;
  style?: {
    fontFamily?: string;
    fontSize?: number;
    fontColor?: string;
    backgroundColor?: string;
    fontWeight?: 'normal' | 'bold';
    glow?: {
      strengths?: number[];  // Array of blur radius for each layer (px). Length determines number of layers.
    };
    layout?: LayoutConfig;
  };
  layoutSeed?: number;
  debug?: boolean; // Add debug mode prop
}

// Accept props from Composition for Remotion Studio while still supporting CLI renders
export const MainTransitionVideo: React.FC<Partial<TransitionVideoProps>> = (
  compositionProps
) => {
  // Try reading props that were injected at render-time (CLI).
  const cliProps = getInputProps();

  // Merge precedence: CLI-passed props (if any) override composition props.
  const props: Partial<TransitionVideoProps> = {
    ...compositionProps,
    ...cliProps,
  };
  const {
    words,
    startTimes,
    duration = 3,
    fps = 24,
    style,
    layoutSeed = 420,
    debug = false, // disable debug by default for now
  } = props;

  // Fallback words/startTimes if missing
  const safeWords = words ?? ["Preview", "Text"];
  const safeStartTimes = startTimes ?? safeWords.map((_, idx) => idx * 0.5);
  const { durationInFrames, width, height } = useVideoConfig();
  
  // Group individual words into lines, then lines into sentences, then sentences into pages
  const wordPages = useMemo(() => {
    // Step 1: Group individual words into lines (6-12 character target)
    const lines = [];
    const lineStartTimes = [];
    
    // First, group words by sentences
    const sentences = [];
    let currentSentenceWords = [];
    let currentSentenceStartTimes = [];
    
    for (let i = 0; i < safeWords.length; i++) {
      const word = safeWords[i];
      const startTime = safeStartTimes[i];
      
      currentSentenceWords.push(word);
      currentSentenceStartTimes.push(startTime);
      
      // Check if this word ends a sentence
      if (word.trim().endsWith('.') || word.trim().endsWith('?') || word.trim().endsWith('!')) {
        sentences.push({
          words: currentSentenceWords.slice(),
          startTimes: currentSentenceStartTimes.slice()
        });
        currentSentenceWords = [];
        currentSentenceStartTimes = [];
      }
    }
    
    // Add any remaining words as a sentence (in case text doesn't end with punctuation)
    if (currentSentenceWords.length > 0) {
      sentences.push({
        words: currentSentenceWords,
        startTimes: currentSentenceStartTimes
      });
    }
    
         // Step 2: Within each sentence, create lines with 6-12 character target
     const allLines = [];
     const allLineStartTimes = [];
     const allLineWords = []; // Track which words belong to each line
     
           for (const sentence of sentences) {
        let currentLine: string[] = [];
        let currentLineLength = 0;
        let currentLineStartTime: number | null = null;
        let currentLineWordTimings: Array<{ text: string; startTime: number }> = [];
       
       for (let i = 0; i < sentence.words.length; i++) {
         const word = sentence.words[i];
         const startTime = sentence.startTimes[i];
         const wordLength = word.length;
         
         // If adding this word would exceed 12 characters, finish current line
         if (currentLine.length > 0 && (currentLineLength + 1 + wordLength > 12)) { // +1 for space
           // Only finish the line if we have at least 6 characters or it's a single long word
           if (currentLineLength >= 6 || currentLine.length === 1) {
             allLines.push(currentLine.join(" "));
             allLineStartTimes.push(currentLineStartTime);
             allLineWords.push(currentLineWordTimings.slice());
             
             // Start new line
             currentLine = [word];
             currentLineLength = wordLength;
             currentLineStartTime = startTime;
             currentLineWordTimings = [{ text: word, startTime }];
           } else {
             // Current line is too short, add this word anyway
             currentLine.push(word);
             currentLineLength += 1 + wordLength; // +1 for space
             currentLineWordTimings.push({ text: word, startTime });
           }
         } else {
           // Add word to current line
           if (currentLine.length === 0) {
             currentLineStartTime = startTime;
           }
           
           currentLine.push(word);
           currentLineWordTimings.push({ text: word, startTime });
           // Add space length if not the first word
           currentLineLength += wordLength + (currentLine.length > 1 ? 1 : 0);
         }
       }
       
       // Add the last line of the sentence
       if (currentLine.length > 0) {
         allLines.push(currentLine.join(" "));
         allLineStartTimes.push(currentLineStartTime);
         allLineWords.push(currentLineWordTimings);
       }
     }
     
     // Step 3: Group lines back into sentences for pagination
    const lineSentences = [];
    let currentSentenceLines = [];
    let currentSentenceLineStartTimes = [];
    let currentSentenceLineWords = [];
    
    for (let i = 0; i < allLines.length; i++) {
      const line = allLines[i];
      const lineStartTime = allLineStartTimes[i];
      const lineWords = allLineWords[i];
      
      currentSentenceLines.push(line);
      currentSentenceLineStartTimes.push(lineStartTime);
      currentSentenceLineWords.push(lineWords);
      
      // Check if this line ends a sentence
      if (line.trim().endsWith('.') || line.trim().endsWith('?') || line.trim().endsWith('!')) {
        lineSentences.push({
          lines: currentSentenceLines.slice(),
          startTimes: currentSentenceLineStartTimes.slice(),
          lineWords: currentSentenceLineWords.slice()
        });
        currentSentenceLines = [];
        currentSentenceLineStartTimes = [];
        currentSentenceLineWords = [];
      }
    }
    
    // Add any remaining lines as a sentence
    if (currentSentenceLines.length > 0) {
      lineSentences.push({
        lines: currentSentenceLines,
        startTimes: currentSentenceLineStartTimes,
        lineWords: currentSentenceLineWords
      });
    }
    
    // Step 4: Create pages within each sentence (3-7 lines per page)
    const allPages = [];
    
    for (const sentence of lineSentences) {
      const sentenceLines = sentence.lines;
      const sentenceStartTimes = sentence.startTimes;
      const sentenceLineWords = sentence.lineWords;
      
      // If sentence has 7 or fewer lines, it's one page
      if (sentenceLines.length <= 7) {
        allPages.push({
          lines: sentenceLines,
          startTimes: sentenceStartTimes,
          lineWords: sentenceLineWords
        });
      } else {
        // Split sentence into multiple pages (3-7 lines each)
        const totalLines = sentenceLines.length;
        const numPages = Math.ceil(totalLines / 7); // Start with max 7 lines per page
        
        // Distribute lines evenly, ensuring each page has 3-7 lines
        const baseWordsPerPage = Math.floor(totalLines / numPages);
        const extraWords = totalLines % numPages;
        
        // Adjust if base would be less than 3
        let actualNumPages = numPages;
        let actualBaseWordsPerPage = baseWordsPerPage;
        
        if (baseWordsPerPage < 3) {
          actualNumPages = Math.ceil(totalLines / 3); // Ensure minimum 3 lines per page
          actualBaseWordsPerPage = Math.floor(totalLines / actualNumPages);
        }
        
        let lineIndex = 0;
        
        for (let pageIndex = 0; pageIndex < actualNumPages; pageIndex++) {
          // Some pages get an extra line for even distribution
          const linesInThisPage = actualBaseWordsPerPage + (pageIndex < extraWords ? 1 : 0);
          
          const pageLines = sentenceLines.slice(lineIndex, lineIndex + linesInThisPage);
          const pageStartTimes = sentenceStartTimes.slice(lineIndex, lineIndex + linesInThisPage);
          const pageLineWords = sentenceLineWords.slice(lineIndex, lineIndex + linesInThisPage);
          
          allPages.push({
            lines: pageLines,
            startTimes: pageStartTimes,
            lineWords: pageLineWords
          });
          
          lineIndex += linesInThisPage;
        }
      }
    }
    
    return allPages;
  }, [safeWords, safeStartTimes]);
  
  // Load Google Fonts based on style
  const loadedFont = useMemo(() => {
    const fontFamily = style?.fontFamily || "Times New Roman, serif";
    
    // Use the font-loader utility to load any supported Google Font
    const loadedFontFamily = loadGoogleFontSync(fontFamily);
    console.log(`Font loading result: ${loadedFontFamily}`);
    return loadedFontFamily;
  }, [style?.fontFamily]);
  
  // Default style values with Google Font support
  const defaultStyle = {
    fontFamily: loadedFont,
    fontSize: 48,
    fontColor: "#000000",
    backgroundColor: "#ffffff",
    fontWeight: "normal" as const,
    glow: {
      strengths: []  // No glow by default
    },
    layout: {
      mode: "centered" as const,
      avgStepPct: 6,
      jitterPct: 3,
      safeLeftPct: 10,
      safeRightPct: 90,
      accent: "longestWord" as const,
      accentColor: "#6AB0A1",
      accentScale: 1.05,
      accentBold: true,
      startTopPct: 30,
      lineHeight: 1.4,
      relativeOffsets: []
    }
  };
  
  // Merge provided style with defaults
  const effectiveStyle = { 
    ...defaultStyle, 
    ...style,
    fontFamily: loadedFont, // Always use the loaded font
    glow: { ...defaultStyle.glow, ...style?.glow }
  };
  const layoutConfig = { ...defaultStyle.layout, ...style?.layout };
  
  // Convert seconds to frames
  const toFrame = (seconds: number) => Math.round(seconds * fps);
  
  // Calculate page timing based on actual word start times
  const pageTimings = useMemo(() => {
    const totalDurationSeconds = durationInFrames / fps;
    
    return wordPages.map((page, pageIndex) => {
      // First page always starts at 0, others start when their first word starts
      const firstWordStartTime = page.lineWords[0]?.[0]?.startTime || 0;
      const pageStartTime = pageIndex === 0 ? 0 : firstWordStartTime;
      
      // Page ends when the next page's first word starts (or video ends)
      const nextPageFirstWordStartTime = pageIndex < wordPages.length - 1 
        ? wordPages[pageIndex + 1].lineWords[0]?.[0]?.startTime || totalDurationSeconds
        : totalDurationSeconds;
      
      return {
        startTime: pageStartTime,
        endTime: nextPageFirstWordStartTime,
        startFrame: Math.round(pageStartTime * fps),
        endFrame: Math.round(nextPageFirstWordStartTime * fps)
      };
    });
  }, [wordPages, durationInFrames, fps]);

  // Process lines with layout algorithm for each page
  const processedPages = useMemo(() => {
    return wordPages.map((page, pageIndex) => {
      const pageStartTime = pageTimings[pageIndex].startTime;
      
      // Create line-level WordInfo objects for layout
      const lineInfos: WordInfo[] = page.lines.map((lineText, lineIndex) => {
        // Use the first word's start time as the line's start time
        const firstWordStartTime = page.lineWords[lineIndex][0]?.startTime || 0;
        const relativeStartTime = pageIndex === 0 
          ? firstWordStartTime 
          : firstWordStartTime - pageStartTime;
        
        return {
          text: lineText,
          startTime: Math.max(0, relativeStartTime)
        };
      });
      
      // Apply layout to lines, not individual words
      const layoutedLines = applyLayout(lineInfos, layoutConfig, layoutSeed + pageIndex, effectiveStyle.fontSize, effectiveStyle.fontFamily, width, height);
      
      // Find the longest word across all words in this page
      let longestWordInfo = { text: '', lineIndex: -1, wordIndex: -1, length: 0 };
      if (layoutConfig.accent === 'longestWord') {
        page.lineWords.forEach((lineWords, lineIdx) => {
          lineWords.forEach((wordData, wordIdx) => {
            if (wordData.text.length > longestWordInfo.length) {
              longestWordInfo = {
                text: wordData.text,
                lineIndex: lineIdx,
                wordIndex: wordIdx,
                length: wordData.text.length
              };
            }
          });
        });
      }
      
      // Process word timings relative to page start
      const processedLineWords = page.lineWords.map(lineWords => 
        lineWords.map(wordData => ({
          ...wordData,
          relativeStartTime: pageIndex === 0 
            ? wordData.startTime 
            : wordData.startTime - pageStartTime
        }))
      );
      
      return {
        layoutedLines, // Line positions from layout algorithm
        lineWords: processedLineWords, // Word data with relative timings
        timing: pageTimings[pageIndex],
        longestWordInfo // Info about which word should be accented
      };
    });
  }, [wordPages, layoutConfig, layoutSeed, effectiveStyle.fontSize, effectiveStyle.fontFamily, pageTimings]);
  
  // Calculate text width using canvas (for debug visualization)
  const measureTextWidth = (text: string, fontSize?: number): number => {
    const fontSizeToUse = fontSize || effectiveStyle.fontSize;
    try {
      if (typeof document !== 'undefined') {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.font = `${fontSizeToUse}px ${effectiveStyle.fontFamily}`;
          return ctx.measureText(text).width * 1.2; // 20% buffer for safety
        }
      }
    } catch (error) {
      console.warn('Canvas measureText failed:', error);
    }
    // Fallback
    return text.length * fontSizeToUse * 0.6 * 1.2; // 20% buffer for safety
  };

  return (
    <AbsoluteFill
      style={{
        backgroundColor: effectiveStyle.backgroundColor,
        fontFamily: effectiveStyle.fontFamily,
        color: effectiveStyle.fontColor,
        fontSize: effectiveStyle.fontSize,
        fontWeight: effectiveStyle.fontWeight,
        padding: 40,
        lineHeight: 1.4,
      }}
    >
      {/* Debug: Safe boundary lines */}
      {debug && (
        <>
          {/* Left safe boundary */}
          <div
            style={{
              position: "absolute",
              left: `${layoutConfig.safeLeftPct}%`,
              top: 0,
              bottom: 0,
              width: 2,
              backgroundColor: "red",
              zIndex: 1000,
              opacity: 0.7,
            }}
          />
          {/* Right safe boundary */}
          <div
            style={{
              position: "absolute",
              left: `${layoutConfig.safeRightPct}%`,
              top: 0,
              bottom: 0,
              width: 2,
              backgroundColor: "red",
              zIndex: 1000,
              opacity: 0.7,
            }}
          />
          {/* Center line */}
          <div
            style={{
              position: "absolute",
              left: "50%",
              top: 0,
              bottom: 0,
              width: 1,
              backgroundColor: "blue",
              zIndex: 999,
              opacity: 0.5,
            }}
          />
        </>
      )}

      {processedPages.map((page, pageIndex) => (
        <Sequence
          key={`page-${pageIndex}`}
          from={page.timing.startFrame}
          durationInFrames={page.timing.endFrame - page.timing.startFrame}
        >
                    {page.layoutedLines.map((lineInfo, lineIndex) => {
            const lineWords = page.lineWords[lineIndex];
            
            // Use processed positions from layout algorithm
            const topPercent = (lineInfo as any).topPercent || 50;
            const leftPercent = lineInfo.centerPct || 50;
            
            // Check if this line contains the accent word
            const isAccentLine = page.longestWordInfo.lineIndex === lineIndex;
            
            return (
              <LineRenderer
                key={`line-${pageIndex}-${lineIndex}`}
                lineWords={lineWords}
                topPercent={topPercent}
                leftPercent={leftPercent}
                isAccentLine={isAccentLine}
                effectiveStyle={effectiveStyle}
                layoutConfig={layoutConfig}
                pageIndex={pageIndex}
                lineIndex={lineIndex}
                pageStartFrame={page.timing.startFrame}
                longestWordInfo={isAccentLine ? page.longestWordInfo : null}
              />
            );
          })}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

// Separate component to handle line rendering with proper hook usage
const LineRenderer: React.FC<{
  lineWords: Array<{ text: string; startTime: number; relativeStartTime: number }>;
  topPercent: number;
  leftPercent: number;
  isAccentLine: boolean;
  effectiveStyle: any;
  layoutConfig: any;
  pageIndex: number;
  lineIndex: number;
  pageStartFrame: number;
  longestWordInfo: { text: string; lineIndex: number; wordIndex: number; length: number } | null;
}> = ({ lineWords, topPercent, leftPercent, isAccentLine, effectiveStyle, layoutConfig, pageIndex, lineIndex, pageStartFrame, longestWordInfo }) => {
  const currentFrame = useCurrentFrame(); // This is relative to the Sequence start!
  
  // Convert seconds to frames
  const toFrame = (seconds: number) => Math.round(seconds * 24);
  
  return (
    <div
      style={{
        position: "absolute",
        top: `${topPercent}%`,
        left: `${leftPercent}%`,
        transform: "translateX(-50%)",
        whiteSpace: "nowrap",
        fontFamily: effectiveStyle.fontFamily,
        fontSize: effectiveStyle.fontSize,
        color: effectiveStyle.fontColor,
        fontWeight: effectiveStyle.fontWeight,
      }}
    >
            {lineWords.map((wordData, wordIndex) => {
        const wordStartFrame = toFrame(wordData.relativeStartTime);
        // Both currentFrame and wordStartFrame are relative to the page start
        const isWordVisible = currentFrame >= wordStartFrame;
        
                  // Check if this specific word should be accented
          const isWordAccent = longestWordInfo && wordIndex === longestWordInfo.wordIndex;
                    const isLongWord = wordData.text.length >= 14;
                    
                    // Calculate font size for this word
                    let wordFontSize = effectiveStyle.fontSize;
                    if (isWordAccent) {
                      wordFontSize *= layoutConfig.accentScale;
                    }
                    if (isLongWord) {
                      wordFontSize *= 0.75; // 25% reduction for long words
                    }
                    
                    const wordStyle = {
                      ...(isWordAccent ? {
                        color: layoutConfig.accentColor,
                        fontSize: wordFontSize,
                        fontWeight: layoutConfig.accentBold ? "bold" as const : effectiveStyle.fontWeight
                      } : {
                        fontSize: isLongWord ? wordFontSize : undefined
                      })
                    };
                    
                    // Generate glow effect
                    const { strengths } = effectiveStyle.glow;
                    const actualTextColor = isWordAccent ? layoutConfig.accentColor : effectiveStyle.fontColor;
                    let glowShadow = '';
                    if (strengths && strengths.length > 0) {
                      glowShadow = strengths.map((strength: number) => `0 0 ${strength}px ${actualTextColor}`).join(', ');
                    }
                    
                            return (
          <span
            key={`word-${pageIndex}-${lineIndex}-${wordIndex}`}
            style={{
              opacity: isWordVisible ? 1 : 0,
              transition: 'opacity 0.05s ease-in',
              textShadow: glowShadow || undefined,
              ...wordStyle,
              marginRight: wordIndex < lineWords.length - 1 ? '0.25em' : 0, // Add space between words
            }}
          >
            {wordData.text}
          </span>
        );
      })}
    </div>
  );
};