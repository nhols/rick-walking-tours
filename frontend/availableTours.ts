import almatyTourData from './assets/tour/almaty-kazakhstan/frontend_tour.json';
import edinburghTourData from './assets/tour/edinburgh/frontend_tour.json';
import originalEdinburghTourData from './assets/tour/harry-potter-themed-walking-tour-in-edinburgh/frontend_tour.json';
import wandsworthTourData from './assets/tour/wandsworth-common-southwest-london/frontend_tour.json';

export type Tour = typeof edinburghTourData | typeof almatyTourData;
export type AudioAssets = Record<string, number>;

const almatyAudioAssets: AudioAssets = {
  '01-chapter-1-the-foundations-of-identity.wav': require('./assets/tour/almaty-kazakhstan/01-chapter-1-the-foundations-of-identity.wav'),
  '02-chapter-2-the-heart-of-political-history.wav': require('./assets/tour/almaty-kazakhstan/02-chapter-2-the-heart-of-political-history.wav'),
  '03-chapter-3-soviet-modernist-ambition.wav': require('./assets/tour/almaty-kazakhstan/03-chapter-3-soviet-modernist-ambition.wav'),
  '04-chapter-4-surviving-the-tsarist-era.wav': require('./assets/tour/almaty-kazakhstan/04-chapter-4-surviving-the-tsarist-era.wav'),
  '05-chapter-5-the-living-silk-road.wav': require('./assets/tour/almaty-kazakhstan/05-chapter-5-the-living-silk-road.wav'),
};

const edinburghAudioAssets: AudioAssets = {
  '01-nicolson-s-caf-spoon.wav': require('./assets/tour/edinburgh/01-nicolson-s-caf-spoon.wav'),
  '02-the-elephant-house.wav': require('./assets/tour/edinburgh/02-the-elephant-house.wav'),
  '03-greyfriars-kirkyard.wav': require('./assets/tour/edinburgh/03-greyfriars-kirkyard.wav'),
  '04-george-heriot-s-school.wav': require('./assets/tour/edinburgh/04-george-heriot-s-school.wav'),
  '05-victoria-street.wav': require('./assets/tour/edinburgh/05-victoria-street.wav'),
  '06-edinburgh-castle-esplanade.wav': require('./assets/tour/edinburgh/06-edinburgh-castle-esplanade.wav'),
  '07-edinburgh-city-chambers.wav': require('./assets/tour/edinburgh/07-edinburgh-city-chambers.wav'),
  '08-the-balmoral-hotel.wav': require('./assets/tour/edinburgh/08-the-balmoral-hotel.wav'),
};

const originalEdinburghAudioAssets: AudioAssets = {
  '01-the-balmoral-hotel.wav': require('./assets/tour/harry-potter-themed-walking-tour-in-edinburgh/01-the-balmoral-hotel.wav'),
  '02-city-chambers.wav': require('./assets/tour/harry-potter-themed-walking-tour-in-edinburgh/02-city-chambers.wav'),
  '03-victoria-street.wav': require('./assets/tour/harry-potter-themed-walking-tour-in-edinburgh/03-victoria-street.wav'),
  '04-greyfriars-kirkyard.wav': require('./assets/tour/harry-potter-themed-walking-tour-in-edinburgh/04-greyfriars-kirkyard.wav'),
};

const wandsworthAudioAssets: AudioAssets = {
  '01-railway-gateway-and-suburban-growth.wav': require('./assets/tour/wandsworth-common-southwest-london/01-railway-gateway-and-suburban-growth.wav'),
  '02-victorian-preservation-and-the-toast-rack.wav': require('./assets/tour/wandsworth-common-southwest-london/02-victorian-preservation-and-the-toast-rack.wav'),
  '03-victorian-civic-life-and-social-history.wav': require('./assets/tour/wandsworth-common-southwest-london/03-victorian-civic-life-and-social-history.wav'),
  '04-the-scope-and-scientific-history.wav': require('./assets/tour/wandsworth-common-southwest-london/04-the-scope-and-scientific-history.wav'),
  '05-ponds-and-modern-conservation.wav': require('./assets/tour/wandsworth-common-southwest-london/05-ponds-and-modern-conservation.wav'),
  '06-civic-life-and-community-legacy.wav': require('./assets/tour/wandsworth-common-southwest-london/06-civic-life-and-community-legacy.wav'),
};

export const availableTours: { tour: Tour; audioAssets: AudioAssets }[] = [
  { tour: almatyTourData as Tour, audioAssets: almatyAudioAssets },
  { tour: edinburghTourData as Tour, audioAssets: edinburghAudioAssets },
  { tour: originalEdinburghTourData as Tour, audioAssets: originalEdinburghAudioAssets },
  { tour: wandsworthTourData as Tour, audioAssets: wandsworthAudioAssets },
];
