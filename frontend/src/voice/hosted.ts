import { connectVoice, VoiceConnection, VoiceSnapshot, VoiceTicket } from './transport';
declare global { interface Window { ReactNativeWebView?: { postMessage: (value: string) => void }; startWarVoice: (ticket: VoiceTicket) => void; muteWarVoice: (muted: boolean) => void; stopWarVoice: () => void } }
let connection: VoiceConnection | undefined;
let starting = false;
let controller: AbortController | undefined;
const status = document.getElementById('status')!;
function update(state: VoiceSnapshot) { status.textContent = state.message; window.ReactNativeWebView?.postMessage(JSON.stringify(state)); }
window.startWarVoice = async ticket => {
  if (starting) return;
  starting = true;
  connection?.close();
  controller = new AbortController();
  try { connection = await connectVoice(location.origin, async () => ticket, update, controller.signal); }
  catch { /* The transport reports a friendly error through the bridge. */ }
  finally { starting = false; }
};
window.muteWarVoice = value => connection?.mute(value);
window.stopWarVoice = () => { controller?.abort(); connection?.close(); connection = undefined; };
window.addEventListener('pagehide', window.stopWarVoice);
window.ReactNativeWebView?.postMessage(JSON.stringify({ type: 'host-ready' }));