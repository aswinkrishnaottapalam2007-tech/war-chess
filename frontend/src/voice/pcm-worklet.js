/* global AudioWorkletProcessor, sampleRate, registerProcessor */
class WarPcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.phase = 0;
    this.previous = 0;
    this.frame = new ArrayBuffer(2560);
    this.view = new DataView(this.frame);
    this.cursor = 0;
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (let i = 0; i < channel.length; i++) {
      const value = channel[i];
      while (this.phase < 1) {
        const sample = Math.max(-1, Math.min(1, this.previous + (value - this.previous) * this.phase));
        this.view.setInt16(this.cursor * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
        this.cursor += 1;
        if (this.cursor === 1280) {
          this.port.postMessage(this.frame, [this.frame]);
          this.frame = new ArrayBuffer(2560);
          this.view = new DataView(this.frame);
          this.cursor = 0;
        }
        this.phase += this.ratio;
      }
      this.phase -= 1;
      this.previous = value;
    }
    return true;
  }
}
registerProcessor('war-pcm-capture', WarPcmCapture);