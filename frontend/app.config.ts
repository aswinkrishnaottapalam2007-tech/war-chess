import config from './app.json';

export default {
  ...config.expo,
  name: 'WAR CHESS',
  slug: 'war-chess',
  scheme: 'warchess',
  orientation: 'default',
  extra: { backendUrl: process.env.EXPO_PUBLIC_BACKEND_URL },
  ios: { ...config.expo.ios, infoPlist: { NSMicrophoneUsageDescription: 'Discuss strategy with your team.' } },
  android: { ...config.expo.android, permissions: ['RECORD_AUDIO', 'MODIFY_AUDIO_SETTINGS'] },
};