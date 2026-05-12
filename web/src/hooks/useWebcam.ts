// Streams the external webcam from the Flask backend via MJPEG.
// Points directly at Flask (not through the Vite proxy) because Vite buffers
// streaming responses and breaks multipart/x-mixed-replace.
export function useWebcam() {
  const streamUrl = 'http://localhost:5001/api/video-feed';
  return { streamUrl };
}
