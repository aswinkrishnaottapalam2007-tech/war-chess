import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { LogBox } from "react-native";
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useFonts } from 'expo-font';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { StatusBar } from 'expo-status-bar';
import { AppProvider } from '@/src/context';
import { useTheme } from '@/src/theme';

import { ErrorBoundary } from "@/src/components/error-boundary";
import { queryClient } from "@/src/query-client";

// Disable logbox errors etc so that users can see the app
// and agent works as expected.
LogBox.ignoreAllLogs(true)

export default function RootLayout() {
  const { scheme, colors } = useTheme();
  // Prewarm icon fonts before rendering: native Expo Go must not race icon loading.
  const [loaded, error] = useFonts({ ...Ionicons.font, ...MaterialCommunityIcons.font,
    Cinzel: require('../assets/fonts/Cinzel.ttf'), Manrope: require('../assets/fonts/Manrope.ttf') });
  if (!loaded && !error) return null;
  // One app level ErrorBoundary; a render crash shows a reload screen
  // instead of a blank app.
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SafeAreaProvider><AppProvider>
          <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface }, animation: 'fade_from_bottom' }} />
        </AppProvider></SafeAreaProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
