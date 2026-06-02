import tourData from './assets/tour/harry-potter-themed-walking-tour-in-edinburgh/frontend_tour.json';

export type Tour = typeof tourData;
export type AudioAssets = Record<string, number>;

const edinburghAudioAssets: AudioAssets = {
  '01-the-balmoral-hotel.wav': require('./assets/tour/harry-potter-themed-walking-tour-in-edinburgh/01-the-balmoral-hotel.wav'),
  '02-city-chambers.wav': require('./assets/tour/harry-potter-themed-walking-tour-in-edinburgh/02-city-chambers.wav'),
  '03-victoria-street.wav': require('./assets/tour/harry-potter-themed-walking-tour-in-edinburgh/03-victoria-street.wav'),
  '04-greyfriars-kirkyard.wav': require('./assets/tour/harry-potter-themed-walking-tour-in-edinburgh/04-greyfriars-kirkyard.wav'),
};

export const availableTours: { tour: Tour; audioAssets: AudioAssets }[] = [
  { tour: tourData as Tour, audioAssets: edinburghAudioAssets },
];
