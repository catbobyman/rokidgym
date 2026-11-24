// 现场合成的节拍音乐：每拍一个鼓点加一个五声音阶的音，并提供实时音量。
// 只在全屏态（target 为 _blank）下可用，卡片态下 start() 会抛出 InvalidStateError。

const NOTES = [262, 330, 392, 440, 392, 330, 294, 330];

export class BeatMusic {
  constructor() {
    this.audio = null;
  }

  get playing() {
    return this.audio !== null;
  }

  async start() {
    if (this.audio) return;
    const context = new AudioContext();
    const master = context.createGain();
    const analyser = context.createAnalyser();
    analyser.fftSize = 512;
    master.gain.value = 0.8;
    master.connect(analyser);
    analyser.connect(context.destination);
    await context.resume();
    this.audio = {
      context,
      master,
      analyser,
      waveform: new Float32Array(analyser.fftSize),
    };
  }

  async stop() {
    if (!this.audio) return;
    const { context } = this.audio;
    this.audio = null;
    await context.close();
  }

  // 在拍点调用，beat 是第几拍
  playBeat(beat) {
    if (!this.audio) return;
    const { context, master } = this.audio;
    const t = context.currentTime;

    const kick = context.createOscillator();
    const kickGain = context.createGain();
    kick.frequency.setValueAtTime(130, t);
    kick.frequency.exponentialRampToValueAtTime(45, t + 0.12);
    kickGain.gain.setValueAtTime(0.6, t);
    kickGain.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
    kick.connect(kickGain);
    kickGain.connect(master);
    kick.start(t);
    kick.stop(t + 0.22);

    const note = context.createOscillator();
    const noteGain = context.createGain();
    note.type = 'triangle';
    note.frequency.value = NOTES[beat % NOTES.length];
    noteGain.gain.setValueAtTime(0.18, t);
    noteGain.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
    note.connect(noteGain);
    noteGain.connect(master);
    note.start(t);
    note.stop(t + 0.37);
  }

  // 当前音量，0..1；没在播放时返回 null
  level() {
    if (!this.audio) return null;
    const { analyser, waveform } = this.audio;
    analyser.getFloatTimeDomainData(waveform);
    let energy = 0;
    for (let i = 0; i < waveform.length; i += 1) {
      energy += waveform[i] * waveform[i];
    }
    return Math.min(1, Math.sqrt(energy / waveform.length) * 4);
  }
}
