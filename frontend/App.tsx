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

import { availableTours } from './availableTours';
import MapSurface from './MapSurface';

export default function App() {
  const [selectedTourId, setSelectedTourId] = useState(availableTours[0].tour.id);
  const [selectedStopId, setSelectedStopId] = useState(availableTours[0].tour.stops[0].id);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const [positionMillis, setPositionMillis] = useState(0);
  const [durationMillis, setDurationMillis] = useState(0);
  const [recenterSignal, setRecenterSignal] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [toursOpen, setToursOpen] = useState(false);
  const soundRef = useRef<Audio.Sound | null>(null);

  const selectedTourEntry = useMemo(
    () => availableTours.find((entry) => entry.tour.id === selectedTourId) ?? availableTours[0],
    [selectedTourId],
  );
  const tour = selectedTourEntry.tour;
  const audioAssets = selectedTourEntry.audioAssets;

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

  const selectTour = useCallback((tourId: string) => {
    const nextTour = availableTours.find((entry) => entry.tour.id === tourId)?.tour;
    if (!nextTour) {
      return;
    }

    setSelectedTourId(tourId);
    setSelectedStopId(nextTour.stops[0].id);
    setMenuOpen(false);
    setToursOpen(false);
    setRecenterSignal((signal) => signal + 1);
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
      <View style={styles.menuChrome}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Open menu"
          style={styles.menuButton}
          onPress={() => setMenuOpen(true)}
        >
          <MaterialIcons color="#111816" name="menu" size={25} />
        </Pressable>
      </View>

      {menuOpen ? (
        <View style={styles.menuOverlay}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Close menu backdrop"
            style={styles.menuScrim}
            onPress={() => setMenuOpen(false)}
          />
          <View style={styles.menuDrawer}>
            <View style={styles.menuDrawerHeader}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Close menu"
                style={styles.drawerCloseButton}
                onPress={() => setMenuOpen(false)}
              >
                <MaterialIcons color="#111816" name="close" size={25} />
              </Pressable>
              <Text style={styles.menuTitle}>Menu</Text>
            </View>

            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Show tours"
              style={styles.menuItem}
              onPress={() => setToursOpen((open) => !open)}
            >
              <View style={styles.menuItemLabel}>
                <MaterialIcons color="#c94738" name="map" size={19} />
                <Text style={styles.menuItemText}>Tours</Text>
              </View>
              <MaterialIcons
                color="#6a6f69"
                name={toursOpen ? 'expand-less' : 'expand-more'}
                size={24}
              />
            </Pressable>

            {toursOpen ? (
              <View style={styles.tourMenuList}>
                {availableTours.map((entry) => {
                  const isSelected = entry.tour.id === tour.id;
                  return (
                    <Pressable
                      key={entry.tour.id}
                      accessibilityRole="button"
                      accessibilityLabel={`Load ${entry.tour.title}`}
                      style={[
                        styles.tourMenuItem,
                        isSelected ? styles.tourMenuItemSelected : null,
                      ]}
                      onPress={() => selectTour(entry.tour.id)}
                    >
                      <View style={styles.tourMenuTextWrap}>
                        <Text
                          style={[
                            styles.tourMenuTitle,
                            isSelected ? styles.tourMenuTitleSelected : null,
                          ]}
                          numberOfLines={3}
                        >
                          {entry.tour.title}
                        </Text>
                        <Text
                          style={[
                            styles.tourMenuLocation,
                            isSelected ? styles.tourMenuLocationSelected : null,
                          ]}
                          numberOfLines={1}
                        >
                          {entry.tour.location} - {entry.tour.stops.length} stops
                        </Text>
                      </View>
                      {isSelected ? (
                        <MaterialIcons color="#fffdf7" name="check" size={20} />
                      ) : null}
                    </Pressable>
                  );
                })}
              </View>
            ) : null}
          </View>
        </View>
      ) : null}

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
    top: 56,
    left: 76,
    right: 16,
    zIndex: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 16,
    backgroundColor: 'rgba(17, 24, 22, 0.76)',
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 7 },
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
    fontSize: 17,
    fontWeight: '900',
    lineHeight: 21,
    marginTop: 3,
  },
  menuChrome: {
    position: 'absolute',
    top: 56,
    left: 18,
    zIndex: 18,
    alignItems: 'flex-start',
  },
  menuButton: {
    width: 46,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 23,
    backgroundColor: 'rgba(255, 253, 247, 0.9)',
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 7 },
    elevation: 12,
  },
  menuOverlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 40,
    elevation: 40,
  },
  menuScrim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(17, 24, 22, 0.26)',
  },
  menuDrawer: {
    width: 340,
    maxWidth: '88%',
    height: '100%',
    paddingHorizontal: 16,
    paddingTop: 18,
    backgroundColor: '#fffdf7',
    shadowColor: '#000',
    shadowOpacity: 0.26,
    shadowRadius: 22,
    shadowOffset: { width: 8, height: 0 },
    elevation: 42,
  },
  menuDrawerHeader: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 14,
  },
  drawerCloseButton: {
    width: 46,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 23,
    backgroundColor: '#f4f0e8',
  },
  menuTitle: {
    color: '#111816',
    fontSize: 18,
    fontWeight: '900',
  },
  menuItem: {
    minHeight: 54,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    borderRadius: 12,
    paddingHorizontal: 12,
    backgroundColor: '#f7f4ee',
  },
  menuItemLabel: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  menuItemText: {
    color: '#111816',
    fontSize: 15,
    fontWeight: '900',
  },
  tourMenuList: {
    gap: 8,
    paddingTop: 10,
  },
  tourMenuItem: {
    minHeight: 72,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 9,
    backgroundColor: '#f4f0e8',
  },
  tourMenuItemSelected: {
    backgroundColor: '#111816',
  },
  tourMenuTextWrap: {
    flex: 1,
    minWidth: 0,
  },
  tourMenuTitle: {
    color: '#111816',
    fontSize: 14,
    fontWeight: '900',
    lineHeight: 18,
  },
  tourMenuTitleSelected: {
    color: '#fffdf7',
  },
  tourMenuLocation: {
    color: '#6a6f69',
    fontSize: 12,
    fontWeight: '800',
    marginTop: 3,
  },
  tourMenuLocationSelected: {
    color: '#c7d7cf',
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
