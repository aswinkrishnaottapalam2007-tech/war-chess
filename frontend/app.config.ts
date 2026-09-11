import config from './app.json';

export default {
  ...config.expo,
  name: 'WAR CHESS',
  slug: 'war-chess',
  scheme: 'warchess',
  orientation: 'default',
  icon: './assets/images/war-icon.png',
  plugins: [...config.expo.plugins.filter(plugin => plugin !== 'expo-audio' && !(Array.isArray(plugin) && plugin[0] === 'expo-splash-screen')), ['expo-splash-screen', { image: './assets/images/war-icon.png', imageWidth: 140, resizeMode: 'contain', backgroundColor: '#000000' }], ['expo-audio', { microphonePermission: 'Discuss strategy with your team.', enableBackgroundRecording: false }], ['expo-video', { supportsBackgroundPlayback: false, supportsPictureInPicture: false }]],
  extra: { backendUrl: process.env.EXPO_PUBLIC_BACKEND_URL },
  ios: { ...config.expo.ios, infoPlist: { NSMicrophoneUsageDescription: 'Discuss strategy with your team.' } },
  android: { ...config.expo.android, adaptiveIcon: { foregroundImage: './assets/images/war-icon.png', backgroundColor: '#000000' }, permissions: ['RECORD_AUDIO', 'MODIFY_AUDIO_SETTINGS'] },
  web: { ...config.expo.web, favicon: './assets/images/war-icon.png' },
};