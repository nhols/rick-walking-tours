import { useEffect, useMemo, useRef } from 'react';

import { mapHtml } from './mapHtml';

type Props = {
  tour: Parameters<typeof mapHtml>[0];
  selectedStopId: string;
  onSelectStop: (stopId: string) => void;
};

export default function MapSurface({ tour, selectedStopId, onSelectStop }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const html = useMemo(() => mapHtml(tour), [tour]);

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
    iframeRef.current?.contentWindow?.postMessage(
      { type: 'selectStop', id: selectedStopId },
      '*',
    );
  }, [selectedStopId]);

  return (
    <iframe
      ref={iframeRef}
      srcDoc={html}
      style={{ flex: 1, width: '100%', height: '100%', border: 0 }}
      title="Tour map"
    />
  );
}
