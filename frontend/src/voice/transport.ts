export type VoicePeer = { id: number; name: string; role: string; muted: boolean };
export type VoiceSnapshot = { status: 'idle' | 'connecting' | 'connected' | 'error'; message: string; peers: VoicePeer[]; muted: boolean; receivedFrames: number };
export type VoiceTicket = { ticket: string; code: string };
export type VoiceConnection = { mute: (value: boolean) => void; close: () => void };
const initial: VoiceSnapshot = { status: 'connecting', message: 'Connecting securely…', peers: [], muted: false, receivedFrames: 0 };

export async function connectVoice(base: string, loadTicket: () => Promise<VoiceTicket>, onChange: (state: VoiceSnapshot) => void, signal?: AbortSignal): Promise<VoiceConnection> {
  let snapshot = { ...initial }, stream: MediaStream | undefined, socket: WebSocket | undefined;
  let context: AudioContext | undefined, capture: AudioWorkletNode | undefined, heartbeat: ReturnType<typeof setInterval> | undefined;
  let ended = false, ready = false;
  const pendingSources = new Set<AudioBufferSourceNode>(), nextTimes = new Map<number, number>();
  const update = (change: Partial<VoiceSnapshot>) => { snapshot = { ...snapshot, ...change }; onChange(snapshot); };
  const stop = () => {
    if (ended) return;
    ended = true; ready = false;
    clearInterval(heartbeat);
    stream?.getTracks().forEach(track => track.stop());
    capture?.disconnect();
    pendingSources.forEach(source => { try { source.stop(); } catch {} });
    pendingSources.clear();
    socket?.close();
    context?.close().catch(() => {});
    document.removeEventListener('visibilitychange', visibility);
    signal?.removeEventListener('abort', stop);
  };
  const ensureActive = () => { if (ended || signal?.aborted) { stream?.getTracks().forEach(track => track.stop()); throw new Error('Voice connection cancelled.'); } };
  const visibility = () => { if (document.hidden) { stop(); update({ status: 'idle', message: 'Voice paused when the app went into the background. Rejoin when ready.' }); } };
  onChange(snapshot);
  try {
    signal?.addEventListener('abort', stop, { once: true });
    ensureActive();
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('A secure HTTPS connection is required for microphone access.');
    // Resume in the Join button's user-gesture call stack, before network awaits.
    context = new AudioContext({ sampleRate: 16000, latencyHint: 'interactive' });
    await context.resume();
    ensureActive();
    if (!context.audioWorklet) throw new Error('This device does not support live audio processing. Update your device browser.');
    if (navigator.permissions) {
      try {
        const permission = await navigator.permissions.query({ name: 'microphone' as PermissionName });
        if (permission.state === 'denied') throw new Error('Microphone is blocked. Allow it in your browser or device settings. Text chat remains available.');
      } catch (error: any) { if (error.message?.includes('blocked')) throw error; /* Some Safari versions cannot query microphone permission. */ }
    }
    stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false });
    ensureActive();
    const ticket = await loadTicket();
    ensureActive();
    await context.audioWorklet.addModule(`${base}/api/static/pcm-worklet.js`);
    ensureActive();
    const input = context.createMediaStreamSource(stream);
    capture = new AudioWorkletNode(context, 'war-pcm-capture');
    const silent = context.createGain(); silent.gain.value = 0;
    input.connect(capture); capture.connect(silent); silent.connect(context.destination);
    const compressor = context.createDynamicsCompressor(); compressor.threshold.value = -18; compressor.ratio.value = 4;
    const volume = context.createGain(); volume.gain.value = 0.65; compressor.connect(volume); volume.connect(context.destination);
    socket = new WebSocket(`${base.replace(/^http/, 'ws')}/api/voice/ws/${encodeURIComponent(ticket.code)}`);
    socket.binaryType = 'arraybuffer';
    capture.port.onmessage = event => {
      if (!ended && ready && !snapshot.muted && socket?.readyState === WebSocket.OPEN && socket.bufferedAmount < 25600) socket.send(event.data);
    };
    capture.onprocessorerror = () => { stop(); update({ status: 'error', message: 'Audio processing stopped. Please rejoin voice.' }); };
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Voice connection timed out. Please try again.')), 12000);
      socket!.onopen = () => socket!.send(JSON.stringify({ type: 'voice_auth', ticket: ticket.ticket }));
      socket!.onerror = () => { clearTimeout(timeout); reject(new Error('Could not connect to team voice. Check your connection and retry.')); };
      socket!.onclose = () => {
        clearTimeout(timeout);
        if (!ready) reject(new Error('Voice access ended or another voice session is already open.'));
        if (!ended) { stop(); update({ status: 'idle', message: 'Voice disconnected. Tap Join to reconnect securely.' }); }
      };
      socket!.onmessage = event => {
        if (ended) return;
        if (typeof event.data === 'string') {
          const data = JSON.parse(event.data);
          if (data.type === 'error') { clearTimeout(timeout); reject(new Error(data.message)); stop(); update({ status: 'error', message: data.message }); }
          if (data.type === 'ready') { clearTimeout(timeout); ready = true; update({ status: 'connected', message: 'Live with your alliance. Microphone on.' }); resolve(); }
          if (data.type === 'peers') update({ peers: data.peers });
          return;
        }
        const bytes = event.data as ArrayBuffer;
        if (!ready || bytes.byteLength !== 2561 || context!.state !== 'running') return;
        const data = new DataView(bytes), id = data.getUint8(0), clock = context!.currentTime;
        let start = nextTimes.get(id) || clock + 0.16;
        if (start < clock) start = clock + 0.16;
        if (start > clock + 0.64 || pendingSources.size >= 48) return; // Never accumulate unbounded latency/memory.
        const buffer = context!.createBuffer(1, 1280, 16000), samples = buffer.getChannelData(0);
        for (let i = 0; i < samples.length; i++) samples[i] = data.getInt16(1 + i * 2, true) / 32768;
        const source = context!.createBufferSource(); source.buffer = buffer; source.connect(compressor);
        pendingSources.add(source); source.onended = () => { pendingSources.delete(source); source.disconnect(); };
        source.start(start); nextTimes.set(id, start + 0.08);
        snapshot.receivedFrames += 1;
        if (snapshot.receivedFrames % 10 === 1) update({ receivedFrames: snapshot.receivedFrames });
      };
    });
    heartbeat = setInterval(() => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping' })); }, 15000);
    document.addEventListener('visibilitychange', visibility);
    stream.getAudioTracks().forEach(track => { track.onended = () => { if (!ended) { stop(); update({ status: 'idle', message: 'Microphone access ended. You can rejoin voice.' }); } }; });
    return {
      mute(value) {
        if (ended) return;
        stream?.getAudioTracks().forEach(track => { track.enabled = !value; });
        socket?.send(JSON.stringify({ type: 'mute', muted: value }));
        update({ muted: value, message: value ? 'Microphone muted. You can still hear your team.' : 'Live with your alliance. Microphone on.' });
      },
      close() { stop(); update({ status: 'idle', message: 'You left voice. Team text chat is still available.', peers: [] }); },
    };
  } catch (error: any) {
    stop();
    const message = error.name === 'NotAllowedError' ? 'Microphone access was declined. Allow it in settings to join voice; text chat still works.' : error.message || 'Voice could not start.';
    update({ status: 'error', message });
    throw new Error(message);
  }
}