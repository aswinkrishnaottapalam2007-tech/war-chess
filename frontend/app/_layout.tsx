import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { LogBox } from "react-native";
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useFonts } from 'expo-font';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';
import { AppProvider } from '@/src/context';
import { useTheme } from '@/src/theme';
import React, { useCallback, useState } from 'react';
import { VoiceProvider } from '@/src/voice/VoiceProvider';
import { StudioIntro } from '@/src/components/StudioIntro';

import { ErrorBoundary } from "@/src/components/error-boundary";
import { queryClient } from "@/src/query-client";

// Disable logbox errors etc so that users can see the app
// and agent works as expected.
LogBox.ignoreAllLogs(true)

export default function RootLayout() {
  // Prewarm icon fonts before rendering: native Expo Go must not race icon loading.
  const [loaded, error] = useFonts({ ...Ionicons.font, ...MaterialCommunityIcons.font,
    Cinzel: require('../assets/fonts/Cinzel.ttf'), Manrope: require('../assets/fonts/Manrope.ttf') });
  if (!loaded && !error) return null;
  // One app level ErrorBoundary; a render crash shows a reload screen
  // instead of a blank app.
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SafeAreaProvider><AppProvider><VoiceProvider><LaunchNavigator /></VoiceProvider></AppProvider></SafeAreaProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

function LaunchNavigator() {
  const [opening, setOpening] = useState(true), { scheme, colors } = useTheme();
  const complete = useCallback(() => setOpening(false), []);
  if (opening) return <StudioIntro onDone={complete} />;
  return <><StatusBar style={scheme === 'dark' ? 'light' : 'dark'} /><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface }, animation: 'fade_from_bottom' }} /></>;
}
