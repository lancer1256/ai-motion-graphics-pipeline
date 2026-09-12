/**
 * Font loading utilities for Google Fonts
 */

// Define supported Google Fonts
export const SUPPORTED_GOOGLE_FONTS = {
  'montserrat': () => import('@remotion/google-fonts/Montserrat'),
  'roboto': () => import('@remotion/google-fonts/Roboto'),
  'open sans': () => import('@remotion/google-fonts/OpenSans'),
  'lato': () => import('@remotion/google-fonts/Lato'),
  'poppins': () => import('@remotion/google-fonts/Poppins'),
  'inter': () => import('@remotion/google-fonts/Inter'),
  'playfair display': () => import('@remotion/google-fonts/PlayfairDisplay'),
  'source sans pro': () => import('@remotion/google-fonts/SourceSans3'),
  'cutive': () => import('@remotion/google-fonts/Cutive'),
  'eb garamond': () => import('@remotion/google-fonts/EBGaramond'),
} as const;

export type SupportedGoogleFont = keyof typeof SUPPORTED_GOOGLE_FONTS;

/**
 * Load a Google Font if it's supported, otherwise return the original font family
 */
export async function loadGoogleFont(fontFamily: string): Promise<string> {
  const normalizedName = fontFamily.toLowerCase().trim();
  
  // Check if it's a supported Google Font
  const googleFontKey = Object.keys(SUPPORTED_GOOGLE_FONTS).find(key => 
    normalizedName.includes(key)
  ) as SupportedGoogleFont;
  
  if (googleFontKey) {
    try {
      const fontModule = await SUPPORTED_GOOGLE_FONTS[googleFontKey]();
      // Use type assertion to ensure we have the correct loadFont function
      // Use appropriate weights for different fonts
      let weights = ['400', '700']; // default weights
      if (googleFontKey === 'eb garamond') {
        weights = ['500', '600'];
      } else if (googleFontKey === 'cutive') {
        weights = ['400'];
      } else if (googleFontKey === 'inter') {
        weights = ['500', '600'];
      }
      
      const { fontFamily: loadedFontFamily } = (fontModule as any).loadFont('normal', {
        weights,
        subsets: ['latin', 'latin-ext'],
      });
      console.log(`Successfully loaded Google Font: ${loadedFontFamily}`);
      return loadedFontFamily;
    } catch (error) {
      console.warn(`Failed to load Google Font ${googleFontKey}:`, error);
      return fontFamily; // Fallback to original
    }
  }
  
  // Return original font family if not a Google Font
  return fontFamily;
}

/**
 * Synchronous version that loads common fonts immediately
 * Used for better performance when we know the font ahead of time
 */
export function loadGoogleFontSync(fontFamily: string): string {
  const normalizedName = fontFamily.toLowerCase().trim();
  
  // Handle Montserrat specifically since it's commonly used
  if (normalizedName.includes('montserrat')) {
    try {
      // Dynamic import is not available in sync context, so we use direct import
      const { loadFont } = require('@remotion/google-fonts/Montserrat');
      const { fontFamily: loadedFontFamily } = loadFont('normal', {
        weights: ['400', '700'],
        subsets: ['latin', 'latin-ext'],
      });
      console.log(`Successfully loaded Montserrat: ${loadedFontFamily}`);
      return loadedFontFamily;
    } catch (error) {
      console.warn('Failed to load Montserrat:', error);
      return fontFamily;
    }
  }
  
  // Add more sync loaders as needed for commonly used fonts
  if (normalizedName.includes('roboto')) {
    try {
      const { loadFont } = require('@remotion/google-fonts/Roboto');
      const { fontFamily: loadedFontFamily } = loadFont('normal', {
        weights: ['400', '700'],
        subsets: ['latin', 'latin-ext'],
      });
      console.log(`Successfully loaded Roboto: ${loadedFontFamily}`);
      return loadedFontFamily;
    } catch (error) {
      console.warn('Failed to load Roboto:', error);
      return fontFamily;
    }
  }
  
  // Add Cutive sync loader
  if (normalizedName.includes('cutive')) {
    try {
      const { loadFont } = require('@remotion/google-fonts/Cutive');
      const { fontFamily: loadedFontFamily } = loadFont('normal', {
        weights: ['400'],
        subsets: ['latin', 'latin-ext'],
      });
      console.log(`Successfully loaded Cutive: ${loadedFontFamily}`);
      return loadedFontFamily;
    } catch (error) {
      console.warn('Failed to load Cutive:', error);
      return fontFamily;
    }
  }
  
  // Add EB Garamond sync loader
  if (normalizedName.includes('eb garamond') || normalizedName.includes('garamond')) {
    try {
      const { loadFont } = require('@remotion/google-fonts/EBGaramond');
      const { fontFamily: loadedFontFamily } = loadFont('normal', {
        weights: ['600', '700'],
        subsets: ['latin', 'latin-ext'],
      });
      console.log(`Successfully loaded EB Garamond: ${loadedFontFamily}`);
      return loadedFontFamily;
    } catch (error) {
      console.warn('Failed to load EB Garamond:', error);
      return fontFamily;
    }
  }
  
  // Add Inter sync loader
  if (normalizedName.includes('inter')) {
    try {
      const { loadFont } = require('@remotion/google-fonts/Inter');
      const { fontFamily: loadedFontFamily } = loadFont('normal', {
        weights: ['500', '600'],
        subsets: ['latin', 'latin-ext'],
      });
      console.log(`Successfully loaded Inter: ${loadedFontFamily}`);
      return loadedFontFamily;
    } catch (error) {
      console.warn('Failed to load Inter:', error);
      return fontFamily;
    }
  }
  
  // Return original font family if not a known Google Font
  return fontFamily;
}