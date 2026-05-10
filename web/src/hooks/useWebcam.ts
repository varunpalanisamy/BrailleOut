import { useEffect, useRef, useState } from 'react';

export function useWebcam() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;

    async function startCamera() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'environment' },
        });

        const video = videoRef.current;
        if (!video) return;

        video.srcObject = stream;
        video.onloadedmetadata = () => setIsReady(true);
      } catch (err) {
        const e = err as DOMException;
        if (e.name === 'NotAllowedError') {
          setError('Camera access denied. Allow camera in browser settings.');
        } else if (e.name === 'NotFoundError') {
          setError('No camera found on this device.');
        } else {
          setError(`Camera error: ${e.message}`);
        }
      }
    }

    startCamera();

    return () => {
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { videoRef, isReady, error };
}
