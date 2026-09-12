const express = require('express');
const { bundle } = require('@remotion/bundler');
const { renderMedia, selectComposition } = require('@remotion/renderer');
const path = require('path');
const fs = require('fs').promises;
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = process.env.PORT || 3002;

app.use(express.json({ limit: '10mb' }));

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Video rendering endpoint
app.post('/render', async (req, res) => {
  const startTime = Date.now();
  let tempPropsFile = null;
  
  try {
    const { 
      words, 
      startTimes, 
      duration, 
      style, 
      layoutSeed, 
      outputPath,
      fps = parseInt(process.env.TRANSITION_VIDEO_FPS) || 24,
      width = parseInt(process.env.TRANSITION_VIDEO_WIDTH) || 1080,
      height = parseInt(process.env.TRANSITION_VIDEO_HEIGHT) || 1920
    } = req.body;

    console.log(`[${new Date().toISOString()}] Starting render request`);

    // Validate required fields
    if (!words || !startTimes || !outputPath) {
      return res.status(400).json({ 
        error: 'Missing required fields: words, startTimes, outputPath' 
      });
    }

    // Create output directory if it doesn't exist
    const outputDir = path.dirname(outputPath);
    await fs.mkdir(outputDir, { recursive: true });

    // Bundle the Remotion project
    console.log(`[${new Date().toISOString()}] Starting bundle...`);
    const bundleLocation = await bundle({
      entryPoint: path.join(__dirname, 'src/index.tsx'),
      webpackOverride: (config) => config,
    });
    console.log(`[${new Date().toISOString()}] Bundle complete`);

    // Get composition
    const compositions = await selectComposition({
      serveUrl: bundleLocation,
      id: 'MainVideoTransition',
      inputProps: {
        words,
        startTimes,
        duration,
        fps,
        width,
        height,
        style,
        layoutSeed
      },
    });
    console.log(`[${new Date().toISOString()}] Composition selected`);

    // Calculate duration in frames
    const durationInFrames = Math.ceil(duration * fps);

    // Render the video
    console.log(`[${new Date().toISOString()}] Starting render...`);
    await renderMedia({
      composition: {
        ...compositions,
        durationInFrames,
        fps,
        width,
        height,
      },
      serveUrl: bundleLocation,
      codec: 'h264',
      outputLocation: outputPath,
      inputProps: {
        words,
        startTimes,
        duration,
        fps,
        width,
        height,
        style,
        layoutSeed
      },
      concurrency: 1,
      verbose: true,
      overwrite: true,
    });

    const renderTime = Date.now() - startTime;
    console.log(`[${new Date().toISOString()}] Render complete in ${renderTime}ms`);

    // Verify output file exists
    try {
      const stats = await fs.stat(outputPath);
      console.log(`[${new Date().toISOString()}] Output file created: ${stats.size} bytes`);
      
      res.json({
        success: true,
        outputPath,
        fileSize: stats.size,
        renderTimeMs: renderTime,
        timestamp: new Date().toISOString()
      });
    } catch (statError) {
      console.error(`[${new Date().toISOString()}] Output file not found:`, statError);
      res.status(500).json({
        error: 'Render completed but output file not found',
        details: statError.message
      });
    }

  } catch (error) {
    const renderTime = Date.now() - startTime;
    console.error(`[${new Date().toISOString()}] Render failed after ${renderTime}ms:`, error);
    
    res.status(500).json({
      error: 'Render failed',
      details: error.message,
      renderTimeMs: renderTime
    });
  } finally {
    // Cleanup temp files if any
    if (tempPropsFile) {
      try {
        await fs.unlink(tempPropsFile);
      } catch (cleanupError) {
        console.warn(`[${new Date().toISOString()}] Failed to cleanup temp file:`, cleanupError);
      }
    }
  }
});

// Error handling middleware
app.use((error, req, res, next) => {
  console.error(`[${new Date().toISOString()}] Unhandled error:`, error);
  res.status(500).json({
    error: 'Internal server error',
    details: process.env.NODE_ENV === 'development' ? error.message : undefined
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`[${new Date().toISOString()}] Remotion render server listening on port ${PORT}`);
  console.log(`[${new Date().toISOString()}] Health check: http://localhost:${PORT}/health`);
  console.log(`[${new Date().toISOString()}] Render endpoint: POST http://localhost:${PORT}/render`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log(`[${new Date().toISOString()}] SIGTERM received, shutting down gracefully`);
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log(`[${new Date().toISOString()}] SIGINT received, shutting down gracefully`);
  process.exit(0);
});
