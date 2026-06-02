import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { Audio, AVPlaybackStatus } from 'expo-av';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Linking,
  LayoutAnimation,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  UIManager,
  View,
} from 'react-native';

import tourData from './assets/tour/frontend_tour.json';
import MapSurface from './MapSurface';

type Tour = typeof tourData;

const audioAssets: Record<string, number> = {
  '01-the-balmoral-hotel.wav': require('./assets/tour/01-the-balmoral-hotel.wav'),
  '02-city-chambers.wav': require('./assets/tour/02-city-chambers.wav'),
  '03-victoria-street.wav': require('./assets/tour/03-victoria-street.wav'),
  '04-greyfriars-kirkyard.wav': require('./assets/tour/04-greyfriars-kirkyard.wav'),
};

export default function App() {
  const tour = tourData as Tour;
  const [selectedStopId, setSelectedStopId] = useState(tour.stops[0].id);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const [positionMillis, setPositionMillis] = useState(0);
  const [durationMillis, setDurationMillis] = useState(0);
  const [recenterSignal, setRecenterSignal] = useState(0);
  const soundRef = useRef<Audio.Sound | null>(null);

  const selectedStop = useMemo(
    () => tour.stops.find((stop) => stop.id === selectedStopId) ?? tour.stops[0],
    [selectedStopId, tour.stops],
  );

  useEffect(() => {
    setIsPlaying(false);
    setPositionMillis(0);
    setDurationMillis(0);
    if (detailsExpanded) {
      animateDetailsLayout();
    }
    setDetailsExpanded(false);
    void unloadSound();
  }, [selectedStopId]);

  useEffect(() => {
    if (Platform.OS === 'android') {
      const layoutManager = UIManager as typeof UIManager & {
        setLayoutAnimationEnabledExperimental?: (enabled: boolean) => void;
      };
      layoutManager.setLayoutAnimationEnabledExperimental?.(true);
    }

    return () => {
      void unloadSound();
    };
  }, []);

  async function unloadSound() {
    if (soundRef.current) {
      await soundRef.current.unloadAsync();
      soundRef.current = null;
    }
  }

  async function togglePlayback() {
    if (isLoadingAudio) {
      return;
    }

    if (soundRef.current) {
      const status = await soundRef.current.getStatusAsync();
      if (status.isLoaded && status.isPlaying) {
        await soundRef.current.pauseAsync();
        setIsPlaying(false);
      } else if (status.isLoaded) {
        await soundRef.current.playAsync();
        setIsPlaying(true);
      }
      return;
    }

    const source = audioAssets[selectedStop.audio.src];
    if (!source) {
      return;
    }

    setIsLoadingAudio(true);
    try {
      await Audio.setAudioModeAsync({
        playsInSilentModeIOS: true,
        staysActiveInBackground: true,
      });
      const { sound } = await Audio.Sound.createAsync(
        source,
        { shouldPlay: true },
        onPlaybackStatusUpdate,
      );
      soundRef.current = sound;
      setIsPlaying(true);
    } finally {
      setIsLoadingAudio(false);
    }
  }

  function onPlaybackStatusUpdate(status: AVPlaybackStatus) {
    if (!status.isLoaded) {
      return;
    }
    setIsPlaying(status.isPlaying);
    setPositionMillis(status.positionMillis ?? 0);
    setDurationMillis(status.durationMillis ?? 0);
    if (status.didJustFinish) {
      setIsPlaying(false);
      setPositionMillis(0);
    }
  }

  const selectStop = useCallback((stopId: string) => {
    setSelectedStopId(stopId);
  }, []);

  const openDirections = useCallback(async () => {
    const label = encodeURIComponent(selectedStop.title);
    const { lat, lon } = selectedStop.position;
    const nativeUrl = Platform.select({
      ios: `maps://?daddr=${lat},${lon}&q=${label}`,
      android: `geo:0,0?q=${lat},${lon}(${label})`,
      default: `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`,
    });
    const fallbackUrl = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`;

    if (nativeUrl && (await Linking.canOpenURL(nativeUrl))) {
      await Linking.openURL(nativeUrl);
      return;
    }

    await Linking.openURL(fallbackUrl);
  }, [selectedStop]);

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="dark" />
      <MapSurface
        tour={tour}
        selectedStopId={selectedStop.id}
        onSelectStop={selectStop}
        recenterSignal={recenterSignal}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Recenter map on tour"
        style={styles.mapHeader}
        onPress={() => setRecenterSignal((signal) => signal + 1)}
      >
        <Text style={styles.kicker} numberOfLines={1}>
          {tour.location}
        </Text>
        <Text style={styles.tourTitle} numberOfLines={2}>
          {tour.title}
        </Text>
      </Pressable>

      <View style={styles.bottomChrome}>
        <View style={styles.detailsPanel}>
          <View style={styles.detailsHeader}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Directions to ${selectedStop.title}`}
              style={styles.directionsButton}
              onPress={() => void openDirections()}
            >
              <MaterialIcons color="#fffdf7" name="location-pin" size={23} />
            </Pressable>

            <Pressable
              style={styles.detailsToggle}
              onPress={() => {
                animateDetailsLayout();
                setDetailsExpanded((expanded) => !expanded);
              }}
            >
              <View style={styles.titleWrap}>
                <Text style={styles.detailsTitle} numberOfLines={1}>
                  {selectedStop.order}. {selectedStop.title}
                </Text>
                <Text style={styles.detailsSubtitle} numberOfLines={1}>
                  {detailsExpanded ? selectedStop.formattedAddress : selectedStop.description}
                </Text>
              </View>
              <View style={styles.expandIconWrap}>
                <MaterialIcons
                  color="#c94738"
                  name={detailsExpanded ? 'expand-more' : 'expand-less'}
                  size={28}
                />
              </View>
            </Pressable>
          </View>

          {detailsExpanded ? (
            <ScrollView
              style={styles.expandedDetails}
              showsVerticalScrollIndicator={false}
            >
              <Text style={styles.sectionLabel}>Address</Text>
              <Text style={styles.bodyText}>{selectedStop.formattedAddress}</Text>

              <Text style={styles.sectionLabel}>Why this stop</Text>
              <Text style={styles.bodyText}>{selectedStop.description}</Text>

              <Text style={styles.sectionLabel}>Narration</Text>
              <Text style={styles.narrationText}>{selectedStop.narration}</Text>

              <ScrollView
                horizontal
                contentContainerStyle={styles.stopList}
                showsHorizontalScrollIndicator={false}
              >
                {tour.stops.map((stop) => (
                  <Pressable
                    key={stop.id}
                    style={[
                      styles.stopChip,
                      selectedStop.id === stop.id ? styles.stopChipSelected : null,
                    ]}
                    onPress={() => selectStop(stop.id)}
                  >
                    <Text
                      style={[
                        styles.stopChipText,
                        selectedStop.id === stop.id ? styles.stopChipTextSelected : null,
                      ]}
                    >
                      {stop.order}. {stop.title}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
            </ScrollView>
          ) : null}
        </View>

        <View style={styles.playerBanner}>
          <Pressable
            style={styles.playButton}
            onPress={togglePlayback}
            disabled={isLoadingAudio}
          >
            <MaterialIcons
              color="#111816"
              name={isLoadingAudio ? 'hourglass-empty' : isPlaying ? 'pause' : 'play-arrow'}
              size={25}
            />
          </Pressable>
          <View style={styles.playerTextWrap}>
            <View style={styles.progressTrack}>
              <View
                style={[
                  styles.progressFill,
                  {
                    width: `${playbackProgress(positionMillis, durationMillis) * 100}%`,
                  },
                ]}
              />
            </View>
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

function playbackProgress(position: number, duration: number) {
  if (!duration) {
    return 0;
  }

  return Math.min(1, Math.max(0, position / duration));
}

function animateDetailsLayout() {
  LayoutAnimation.configureNext({
    duration: 260,
    create: {
      type: LayoutAnimation.Types.easeInEaseOut,
      property: LayoutAnimation.Properties.opacity,
    },
    update: {
      type: LayoutAnimation.Types.easeInEaseOut,
    },
    delete: {
      type: LayoutAnimation.Types.easeInEaseOut,
      property: LayoutAnimation.Properties.opacity,
    },
  });
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#f7f4ee',
  },
  mapHeader: {
    position: 'absolute',
    top: 58,
    left: 18,
    right: 18,
    paddingHorizontal: 16,
    paddingVertical: 13,
    borderRadius: 16,
    backgroundColor: 'rgba(17, 24, 22, 0.68)',
    shadowColor: '#000',
    shadowOpacity: 0.22,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 12,
  },
  kicker: {
    color: 'rgba(199, 215, 207, 0.82)',
    fontSize: 12,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  tourTitle: {
    color: 'rgba(255, 253, 247, 0.88)',
    fontSize: 18,
    fontWeight: '900',
    lineHeight: 22,
    marginTop: 2,
  },
  bottomChrome: {
    marginHorizontal: 10,
    marginBottom: 10,
    overflow: 'hidden',
    borderRadius: 24,
    backgroundColor: '#fffdf7',
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 22,
    shadowOffset: { width: 0, height: 10 },
    elevation: 20,
  },
  detailsPanel: {
    paddingHorizontal: 18,
    paddingTop: 12,
  },
  detailsHeader: {
    minHeight: 54,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  directionsButton: {
    width: 42,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 21,
    backgroundColor: '#111816',
  },
  detailsToggle: {
    flex: 1,
    minWidth: 0,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  playerBanner: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 12,
    borderTopWidth: 1,
    borderTopColor: '#ece7dc',
    backgroundColor: '#111816',
  },
  titleWrap: {
    flex: 1,
    minWidth: 0,
  },
  detailsTitle: {
    color: '#111816',
    fontSize: 15,
    fontWeight: '900',
  },
  detailsSubtitle: {
    color: '#6a6f69',
    fontSize: 13,
    marginTop: 2,
  },
  expandIconWrap: {
    width: 34,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 17,
    backgroundColor: '#f5e8df',
  },
  expandedDetails: {
    maxHeight: 292,
    marginTop: 8,
    paddingBottom: 8,
  },
  sectionLabel: {
    color: '#c94738',
    fontSize: 12,
    fontWeight: '900',
    marginTop: 12,
    marginBottom: 4,
    textTransform: 'uppercase',
  },
  bodyText: {
    color: '#242825',
    fontSize: 15,
    lineHeight: 21,
  },
  playButton: {
    width: 42,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 21,
    backgroundColor: '#fffdf7',
  },
  playerTextWrap: {
    flex: 1,
    minWidth: 0,
  },
  progressTrack: {
    height: 5,
    overflow: 'hidden',
    borderRadius: 2.5,
    backgroundColor: '#34413c',
  },
  progressFill: {
    height: 5,
    borderRadius: 2.5,
    backgroundColor: '#f06f5c',
  },
  narrationText: {
    color: '#242825',
    fontSize: 15,
    lineHeight: 22,
  },
  stopList: {
    gap: 8,
    paddingTop: 14,
    paddingBottom: 4,
  },
  stopChip: {
    minHeight: 36,
    justifyContent: 'center',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#d8d7cd',
    paddingHorizontal: 14,
    backgroundColor: '#fffdf7',
  },
  stopChipSelected: {
    borderColor: '#111816',
    backgroundColor: '#111816',
  },
  stopChipText: {
    color: '#242825',
    fontWeight: '800',
  },
  stopChipTextSelected: {
    color: '#fffdf7',
  },
});
