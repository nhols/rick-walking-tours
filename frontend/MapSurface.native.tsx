import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import * as Location from 'expo-location';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';
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
  const locationSubscriptionRef = useRef<Location.LocationSubscription | null>(null);
  const locationRequestIdRef = useRef(0);
  const html = useMemo(() => mapHtml(tour), [tour]);
  const [isTrackingLocation, setIsTrackingLocation] = useState(false);
  const [isLocating, setIsLocating] = useState(false);
  const sendMapMessage = useCallback((message: object) => {
    webViewRef.current?.postMessage(JSON.stringify(message));
  }, []);

  const stopLocationTracking = useCallback(() => {
    locationRequestIdRef.current += 1;
    locationSubscriptionRef.current?.remove();
    locationSubscriptionRef.current = null;
    setIsTrackingLocation(false);
    setIsLocating(false);
  }, []);

  const sendLocation = useCallback(
    (position: Location.LocationObject) => {
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

  const startLocationTracking = useCallback(async () => {
    if (isLocating) {
      return;
    }

    const requestId = locationRequestIdRef.current + 1;
    locationRequestIdRef.current = requestId;
    setIsLocating(true);
    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (locationRequestIdRef.current !== requestId) {
        return;
      }
      if (!permission.granted) {
        setIsLocating(false);
        sendMapMessage({ type: 'userLocationError', message: 'Location permission denied' });
        return;
      }

      const lastKnownPosition = await Location.getLastKnownPositionAsync({
        maxAge: 60000,
        requiredAccuracy: 1000,
      });
      if (lastKnownPosition) {
        sendLocation(lastKnownPosition);
      }

      const currentPosition = await withTimeout(
        Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
          mayShowUserSettingsDialog: true,
        }),
        15000,
      );
      if (locationRequestIdRef.current !== requestId) {
        return;
      }
      sendLocation(currentPosition);

      locationSubscriptionRef.current?.remove();
      locationSubscriptionRef.current = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.Balanced,
          distanceInterval: 5,
          timeInterval: 3000,
          mayShowUserSettingsDialog: true,
        },
        (position) => {
          if (locationRequestIdRef.current === requestId) {
            sendLocation(position);
          }
        },
      );
    } catch {
      if (locationRequestIdRef.current !== requestId) {
        return;
      }
      setIsLocating(false);
      sendMapMessage({ type: 'userLocationError', message: 'Location unavailable' });
    }
  }, [isLocating, sendLocation, sendMapMessage]);

  const toggleLocationTracking = useCallback(() => {
    if (isTrackingLocation || isLocating) {
      stopLocationTracking();
      return;
    }

    void startLocationTracking();
  }, [isLocating, isTrackingLocation, startLocationTracking, stopLocationTracking]);

  useEffect(() => {
    webViewRef.current?.postMessage(JSON.stringify({ type: 'selectStop', id: selectedStopId }));
  }, [selectedStopId]);

  useEffect(() => {
    if (recenterSignal > 0) {
      webViewRef.current?.postMessage(JSON.stringify({ type: 'recenterTour' }));
    }
  }, [recenterSignal]);

  useEffect(() => stopLocationTracking, [stopLocationTracking]);

  return (
    <View style={styles.container}>
      <WebView
        ref={webViewRef}
        originWhitelist={['*']}
        source={{ html, baseUrl: 'https://localhost' }}
        style={styles.map}
        onMessage={(event) => {
          const data = parseMapMessage(event.nativeEvent.data);
          const stopId =
            typeof event.nativeEvent.data === 'string'
              ? event.nativeEvent.data
              : data?.type === 'selectStop'
                ? data.id
                : null;
          if (stopId && tour.stops.some((stop) => stop.id === stopId)) {
            onSelectStop(stopId);
          }
        }}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={isTrackingLocation ? 'Stop location tracking' : 'Start location tracking'}
        style={[
          styles.locationButton,
          isTrackingLocation ? styles.locationButtonActive : null,
          isLocating ? styles.locationButtonLocating : null,
        ]}
        onPress={toggleLocationTracking}
      >
        {isLocating ? (
          <ActivityIndicator color="#111816" size="small" />
        ) : (
          <MaterialIcons
            color={isTrackingLocation ? '#fffdf7' : '#111816'}
            name={isTrackingLocation ? 'gps-fixed' : 'gps-not-fixed'}
            size={22}
          />
        )}
      </Pressable>
    </View>
  );
}

function parseMapMessage(data: string): { type?: string; id?: string } | null {
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

function withTimeout<T>(promise: Promise<T>, timeoutMillis: number) {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => {
      setTimeout(() => reject(new Error('Location request timed out')), timeoutMillis);
    }),
  ]);
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  map: {
    flex: 1,
  },
  locationButton: {
    position: 'absolute',
    left: 10,
    bottom: 32,
    width: 42,
    height: 42,
    borderRadius: 6,
    backgroundColor: '#fffdf7',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.22,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 5,
  },
  locationButtonActive: {
    backgroundColor: '#2586ff',
  },
  locationButtonLocating: {
    backgroundColor: '#fffdf7',
  },
});
