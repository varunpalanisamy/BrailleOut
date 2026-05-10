// Streams the external webcam from the Flask backend via MJPEG.
// The backend opens the USB webcam with OpenCV and streams it at /api/video-feed.
export function useWebcam() {
  // No setup needed — the img src in the component handles the stream.
  // This hook just provides the stream URL so components stay consistent.
  const streamUrl = '/api/video-feed';
  return { streamUrl };
}
