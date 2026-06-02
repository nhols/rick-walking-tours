import { useEffect, useMemo, useRef } from 'react';
import { WebView } from 'react-native-webview';

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
  const webViewRef = useRef<WebView>(null);
  const html = useMemo(() => mapHtml(tour), [tour]);

  useEffect(() => {
    webViewRef.current?.postMessage(JSON.stringify({ type: 'selectStop', id: selectedStopId }));
  }, [selectedStopId]);

  useEffect(() => {
    if (recenterSignal > 0) {
      webViewRef.current?.postMessage(JSON.stringify({ type: 'recenterTour' }));
    }
  }, [recenterSignal]);

  return (
    <WebView
      ref={webViewRef}
      geolocationEnabled
      originWhitelist={['*']}
      source={{ html, baseUrl: 'https://localhost' }}
      style={{ flex: 1 }}
      onMessage={(event) => onSelectStop(event.nativeEvent.data)}
    />
  );
}
