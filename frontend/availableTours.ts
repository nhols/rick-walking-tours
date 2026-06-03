import edinburghTourData from './assets/tour/harry-potter-themed-walking-tour-in-edinburgh/frontend_tour.json';
import wandsworthTourData from './assets/tour/wandsworth-common-southwest-london/frontend_tour.json';

export type Tour = typeof edinburghTourData;
export type AudioAssets = Record<string, number>;

const edinburghAudioAssets: AudioAssets = {
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
  { tour: edinburghTourData as Tour, audioAssets: edinburghAudioAssets },
  { tour: wandsworthTourData as Tour, audioAssets: wandsworthAudioAssets },
];
