import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { mapHtml } from './mapHtml';

type Props = {
  tour: Parameters<typeof mapHtml>[0];
  selectedStopId: string;
  onSelectStop: (stopId: string) => void;
  recenterSignal: number;
};

export default function MapSurface({
  tour,
  selectedStopId,
  onSelectStop,
  recenterSignal,
}: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const locationWatchRef = useRef<number | null>(null);
  const locationRequestIdRef = useRef(0);
  const html = useMemo(() => mapHtml(tour), [tour]);
  const [isTrackingLocation, setIsTrackingLocation] = useState(false);
  const [isLocating, setIsLocating] = useState(false);
  const sendMapMessage = useCallback((message: object) => {
    iframeRef.current?.contentWindow?.postMessage(message, '*');
  }, []);

  const stopLocationTracking = useCallback(() => {
    locationRequestIdRef.current += 1;
    if (locationWatchRef.current !== null) {
      navigator.geolocation.clearWatch(locationWatchRef.current);
      locationWatchRef.current = null;
    }
    setIsTrackingLocation(false);
    setIsLocating(false);
  }, []);

  const sendLocation = useCallback(
    (position: GeolocationPosition) => {
      sendMapMessage({
        type: 'userLocation',
        lat: position.coords.latitude,
        lon: position.coords.longitude,
      });
      setIsLocating(false);
      setIsTrackingLocation(true);
    },
    [sendMapMessage],
  );

  const startLocationTracking = useCallback(() => {
    if (isLocating) {
      return;
    }

    const requestId = locationRequestIdRef.current + 1;
    locationRequestIdRef.current = requestId;
    setIsLocating(true);
    if (!navigator.geolocation) {
      setIsLocating(false);
      sendMapMessage({ type: 'userLocationError', message: 'Location unavailable' });
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        if (locationRequestIdRef.current === requestId) {
          sendLocation(position);
        }
      },
      () => {
        if (locationRequestIdRef.current === requestId) {
          setIsLocating(false);
          sendMapMessage({ type: 'userLocationError', message: 'Location unavailable' });
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 },
    );

    locationWatchRef.current = navigator.geolocation.watchPosition(
      (position) => {
        if (locationRequestIdRef.current === requestId) {
          sendLocation(position);
        }
      },
      () => {
        if (locationRequestIdRef.current === requestId) {
          setIsLocating(false);
          sendMapMessage({ type: 'userLocationError', message: 'Location unavailable' });
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 },
    );
  }, [isLocating, sendLocation, sendMapMessage]);

  const toggleLocationTracking = useCallback(() => {
    if (isTrackingLocation || isLocating) {
      stopLocationTracking();
      return;
    }

    startLocationTracking();
  }, [isLocating, isTrackingLocation, startLocationTracking, stopLocationTracking]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const stopId =
        typeof event.data === 'string'
          ? event.data
          : event.data?.type === 'selectStop'
            ? event.data.id
            : null;

      if (stopId && tour.stops.some((stop) => stop.id === stopId)) {
        onSelectStop(stopId);
      }
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [onSelectStop, tour.stops]);

  useEffect(() => {
    sendMapMessage({ type: 'selectStop', id: selectedStopId });
  }, [selectedStopId, sendMapMessage]);

  useEffect(() => {
    if (recenterSignal > 0) {
      sendMapMessage({ type: 'recenterTour' });
    }
  }, [recenterSignal, sendMapMessage]);

  useEffect(() => stopLocationTracking, [stopLocationTracking]);

  return (
    <div style={{ flex: 1, position: 'relative', width: '100%', height: '100%' }}>
      <iframe
        ref={iframeRef}
        allow="geolocation"
        srcDoc={html}
        style={{ flex: 1, width: '100%', height: '100%', border: 0 }}
        title="Tour map"
      />
      <button
        aria-label={isTrackingLocation ? 'Stop location tracking' : 'Start location tracking'}
        onClick={toggleLocationTracking}
        style={{
          alignItems: 'center',
          background: isTrackingLocation ? '#2586ff' : '#fffdf7',
          border: 0,
          borderRadius: 6,
          bottom: 32,
          boxShadow: '0 2px 10px #0004',
          cursor: 'pointer',
          display: 'flex',
          height: 42,
          justifyContent: 'center',
          left: 10,
          position: 'absolute',
          width: 42,
          zIndex: 2,
        }}
        type="button"
      >
        <MaterialIcons
          color={isTrackingLocation ? '#fffdf7' : '#111816'}
          name={isTrackingLocation ? 'gps-fixed' : 'gps-not-fixed'}
          size={22}
        />
      </button>
    </div>
  );
}
