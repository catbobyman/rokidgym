<script def>
{
  "navigationBarTitleText": "节奏呼吸环"
}
</script>

<script setup>
// 三档节奏。一个跑步周期 = 2 拍，一次吸气或呼气 = 4 拍（时长写在样式的 .tempo-* 里）。
const TEMPOS = [
  { name: 'slow', bpm: 90 },
  { name: 'mid', bpm: 120 },
  { name: 'fast', bpm: 150 },
];
// 五声音阶，随拍子循环
const NOTES = [262, 330, 392, 440, 392, 330, 294, 330];
const TICK_MS = 50;

export default {
  data: {
    tempo: 'mid',
    bpm: 120,
    breath: '吸气',
    musicOn: false,
    musicLabel: '音乐 关',
    pulseStyle: 'transform: scale(1); opacity: 0.35;',
  },

  onLoad() {
    this.tempoIndex = 1;
    this.beat = 0;
    this.lastBeatAt = Date.now();
    this.nextBeatAt = this.lastBeatAt + this.beatMs();
    this.timer = setInterval(() => this.tick(), TICK_MS);
  },

  onUnload() {
    clearInterval(this.timer);
    this.timer = null;
    return this.stopMusic();
  },

  beatMs() {
    return 60000 / TEMPOS[this.tempoIndex].bpm;
  },

  // 唯一的定时器：按真实时间判断是否到拍点，并刷新内环的律动
  tick() {
    const now = Date.now();
    if (now >= this.nextBeatAt) {
      this.beat += 1;
      this.lastBeatAt = now;
      this.nextBeatAt += this.beatMs();
      if (this.nextBeatAt < now) this.nextBeatAt = now + this.beatMs();
      if (this.audio) this.playBeat();
    }

    const level = this.readLevel(now);
    const scale = (1 + level * 0.35).toFixed(3);
    const opacity = (0.3 + level * 0.7).toFixed(2);
    this.setData({
      pulseStyle: `transform: scale(${scale}); opacity: ${opacity};`,
    });
  },

  // 有音乐时读取真实音量；没有音乐时按拍点算一个衰减包络，保证静音也有节奏
  readLevel(now) {
    if (this.audio) {
      const { analyser, waveform } = this.audio;
      analyser.getFloatTimeDomainData(waveform);
      let energy = 0;
      for (let i = 0; i < waveform.length; i += 1) {
        energy += waveform[i] * waveform[i];
      }
      const rms = Math.sqrt(energy / waveform.length);
      return Math.min(1, rms * 4);
    }
    const sinceBeat = now - this.lastBeatAt;
    return Math.exp(-sinceBeat / 140);
  },

  playBeat() {
    const { context, master } = this.audio;
    const t = context.currentTime;

    // 鼓点：频率快速下滑的正弦波
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

    // 旋律音
    const note = context.createOscillator();
    const noteGain = context.createGain();
    note.type = 'triangle';
    note.frequency.value = NOTES[this.beat % NOTES.length];
    noteGain.gain.setValueAtTime(0.18, t);
    noteGain.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
    note.connect(noteGain);
    noteGain.connect(master);
    note.start(t);
    note.stop(t + 0.37);
  },

  async startMusic() {
    if (this.audio) return;
    try {
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
      this.setData({ musicOn: true, musicLabel: '音乐 开' });
    } catch (error) {
      console.error('音乐启动失败', error);
      this.audio = null;
      // 卡片态（target 为 _current）下运行时不允许出声，进入全屏（_blank）后才能播放
      const cardMode = String(error && error.message).includes('_current');
      this.setData({
        musicOn: false,
        musicLabel: cardMode ? '全屏后可开音乐' : '音乐不可用',
      });
    }
  },

  async stopMusic() {
    if (!this.audio) return;
    const { context } = this.audio;
    this.audio = null;
    try {
      await context.close();
    } catch (error) {
      console.error('音乐关闭失败', error);
    }
    this.setData({ musicOn: false, musicLabel: '音乐 关' });
  },

  // 从全屏退回卡片态时停掉音乐；进入全屏时清掉之前的提示
  onTargetChanged(target) {
    if (target === '_current') return this.stopMusic();
    if (!this.audio) this.setData({ musicLabel: '音乐 关' });
  },

  toggleMusic() {
    return this.audio ? this.stopMusic() : this.startMusic();
  },

  changeTempo(step) {
    const next = Math.max(0, Math.min(TEMPOS.length - 1, this.tempoIndex + step));
    if (next === this.tempoIndex) return;
    this.tempoIndex = next;
    this.nextBeatAt = Date.now() + this.beatMs();
    this.setData({ tempo: TEMPOS[next].name, bpm: TEMPOS[next].bpm });
  },

  // 外环用 alternate 往返播放：每完成一程就在吸气和呼气之间切换
  onBreathStart() {
    this.setData({ breath: '吸气' });
  },
  onBreathTurn() {
    this.setData({ breath: this.data.breath === '吸气' ? '呼气' : '吸气' });
  },

  onKeyUp(event) {
    console.log('key', event.code);
    if (event.code === 'Enter') {
      this.toggleMusic();
    } else if (event.code === 'ArrowUp' || event.code === 'ArrowRight') {
      this.changeTempo(1);
    } else if (event.code === 'ArrowDown' || event.code === 'ArrowLeft') {
      this.changeTempo(-1);
    }
  },
}
</script>

<page>
  <view class="container tempo-{{tempo}}">
    <view class="stage">
      <view class="ring ring-breath" bindanimationstart="onBreathStart" bindanimationiteration="onBreathTurn"></view>
      <view class="ring ring-pulse" style="{{pulseStyle}}"></view>

      <!-- 书写顺序即前后层次：远侧肢体在前（被身体挡住），近侧肢体在后 -->
      <view class="runner">
        <view class="limb thigh thigh-b far">
          <view class="limb shin shin-b"><view class="foot"></view></view>
        </view>
        <view class="hips"></view>
        <view class="limb thigh thigh-a">
          <view class="limb shin shin-a"><view class="foot"></view></view>
        </view>
        <view class="upper">
          <view class="limb arm arm-b far">
            <view class="limb forearm"><view class="hand"></view></view>
          </view>
          <view class="neck"></view>
          <view class="chest"></view>
          <view class="head"></view>
          <view class="limb arm arm-a">
            <view class="limb forearm"><view class="hand"></view></view>
          </view>
        </view>
      </view>

      <view class="ground-clip">
        <view class="ground"></view>
      </view>
    </view>

    <text class="breath">{{breath}}</text>
    <text class="status">{{bpm}} BPM · {{musicLabel}}</text>
    <text class="hint" bindtap="toggleMusic">单击开关音乐 · 前后滑动调节奏</text>
  </view>
</page>

<style>
.container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
}

.stage {
  position: relative;
  width: 190px;
  height: 190px;
  margin-bottom: 14px;
}

/* ---------- 圆环 ---------- */
.ring {
  position: absolute;
  border-radius: 50%;
  box-sizing: border-box;
}

/* 外环：纯 CSS 的呼吸，往返一程 = 4 拍 */
.ring-breath {
  left: 15px;
  top: 15px;
  width: 160px;
  height: 160px;
  border: 2px solid #40FF5E;
  animation: breathe 2000ms ease-in-out infinite alternate;
}

/* 内环：由脚本按音量逐帧设置 scale 和 opacity */
.ring-pulse {
  left: 35px;
  top: 35px;
  width: 120px;
  height: 120px;
  border: 4px solid #40FF5E;
  transition: transform 60ms linear, opacity 60ms linear;
}

@keyframes breathe {
  from { transform: scale(0.82); opacity: 0.35; }
  to { transform: scale(1.12); opacity: 1; }
}

/* ---------- 小人 ---------- */
.runner {
  position: absolute;
  left: 55px;
  top: 46px;
  width: 80px;
  height: 100px;
  animation: bob 500ms ease-in-out infinite;
}

/* 上半身整体前倾，支点在髋部（容器的底边中点） */
.upper {
  position: absolute;
  left: 0;
  top: 0;
  width: 80px;
  height: 48px;
  transform-origin: center bottom;
  transform: rotate(9deg);
}

.head {
  position: absolute;
  left: 32px;
  top: 0;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background-color: #40FF5E;
}

.neck {
  position: absolute;
  left: 37px;
  top: 13px;
  width: 6px;
  height: 7px;
  background-color: #40FF5E;
}

.chest {
  position: absolute;
  left: 32px;
  top: 17px;
  width: 16px;
  height: 25px;
  border-radius: 8px;
  background-color: #40FF5E;
}

.hips {
  position: absolute;
  left: 33px;
  top: 34px;
  width: 14px;
  height: 17px;
  border-radius: 7px;
  background-color: #40FF5E;
}

/* 所有肢体都绕自己的顶端中点旋转，圆角充当关节 */
.limb {
  position: absolute;
  background-color: #40FF5E;
  transform-origin: center top;
}

/* 远侧的手臂和腿调暗，做出前后层次 */
.far {
  opacity: 0.5;
}

.arm {
  left: 36px;
  top: 19px;
  width: 8px;
  height: 19px;
  border-radius: 4px;
}

.forearm {
  left: 1px;
  top: 14px;
  width: 6px;
  height: 16px;
  border-radius: 3px;
  transform: rotate(-85deg);
}

.hand {
  position: absolute;
  left: -1px;
  top: 12px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #40FF5E;
}

.thigh {
  left: 35px;
  top: 42px;
  width: 10px;
  height: 27px;
  border-radius: 5px;
}

.shin {
  left: 1px;
  top: 21px;
  width: 8px;
  height: 26px;
  border-radius: 4px;
}

.foot {
  position: absolute;
  left: 0;
  top: 21px;
  width: 14px;
  height: 6px;
  border-radius: 3px;
  background-color: #40FF5E;
}

/* 一个跑步周期 = 2 拍；a、b 两组相位相差半个周期，手臂与同侧腿反向 */
.arm-a { animation: swing-arm-a 1000ms ease-in-out infinite; }
.arm-b { animation: swing-arm-b 1000ms ease-in-out infinite; }
.thigh-a { animation: swing-leg-a 1000ms ease-in-out infinite; }
.thigh-b { animation: swing-leg-b 1000ms ease-in-out infinite; }
.shin-a { animation: bend-a 1000ms ease-in-out infinite; }
.shin-b { animation: bend-b 1000ms ease-in-out infinite; }

@keyframes swing-leg-a {
  from { transform: rotate(-45deg); }
  50% { transform: rotate(32deg); }
  to { transform: rotate(-45deg); }
}
@keyframes swing-leg-b {
  from { transform: rotate(32deg); }
  50% { transform: rotate(-45deg); }
  to { transform: rotate(32deg); }
}
@keyframes bend-a {
  from { transform: rotate(8deg); }
  50% { transform: rotate(55deg); }
  75% { transform: rotate(95deg); }
  to { transform: rotate(8deg); }
}
@keyframes bend-b {
  from { transform: rotate(55deg); }
  25% { transform: rotate(95deg); }
  50% { transform: rotate(8deg); }
  to { transform: rotate(55deg); }
}
@keyframes swing-arm-a {
  from { transform: rotate(40deg); }
  50% { transform: rotate(-45deg); }
  to { transform: rotate(40deg); }
}
@keyframes swing-arm-b {
  from { transform: rotate(-45deg); }
  50% { transform: rotate(40deg); }
  to { transform: rotate(-45deg); }
}
@keyframes bob {
  from { transform: translateY(0); }
  50% { transform: translateY(-4px); }
  to { transform: translateY(0); }
}

/* ---------- 地面 ---------- */
.ground-clip {
  position: absolute;
  left: 50px;
  top: 142px;
  width: 90px;
  height: 4px;
  overflow: hidden;
}

.ground {
  width: 140px;
  height: 0;
  border-top: 2px dashed #40FF5E;
  opacity: 0.6;
  animation: scroll 500ms linear infinite;
}

@keyframes scroll {
  from { transform: translateX(0); }
  to { transform: translateX(-24px); }
}

/* ---------- 三档节奏：90 / 120 / 150 BPM ---------- */
.tempo-slow .ring-breath { animation-duration: 2667ms; }
.tempo-slow .runner,
.tempo-slow .ground { animation-duration: 667ms; }
.tempo-slow .arm,
.tempo-slow .thigh,
.tempo-slow .shin { animation-duration: 1333ms; }

.tempo-fast .ring-breath { animation-duration: 1600ms; }
.tempo-fast .runner,
.tempo-fast .ground { animation-duration: 400ms; }
.tempo-fast .arm,
.tempo-fast .thigh,
.tempo-fast .shin { animation-duration: 800ms; }

/* ---------- 文字 ---------- */
.breath {
  color: #40FF5E;
  font-size: 22px;
  line-height: 26px;
  text-align: center;
}

.status {
  color: #40FF5E;
  font-size: 14px;
  line-height: 20px;
  margin-top: 4px;
  text-align: center;
}

.hint {
  color: #40FF5E;
  opacity: 0.6;
  font-size: 11px;
  line-height: 16px;
  margin-top: 4px;
  text-align: center;
}
</style>
