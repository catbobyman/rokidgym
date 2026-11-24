<script def>
{
  "navigationBarTitleText": "精灵图帧动画"
}
</script>

<script setup>
// 精灵图帧动画：一张横向长图里排着一个动作周期的所有帧，
// 用 @keyframes 移动 background-position，steps(n) 让它一帧一帧跳。

const MOTIONS = [
  { key: 'run', name: '跑步', labels: ['吸气', '呼气'] },
  { key: 'pulldown', name: '高位下拉', labels: ['下拉 · 呼气', '还原 · 吸气'] },
];
const TEMPOS = [
  { key: 'slow', bpm: 90 },
  { key: 'mid', bpm: 120 },
  { key: 'fast', bpm: 150 },
];

export default {
  data: {
    stageClass: 'stage tempo-mid',
    spriteClass: 'sprite sprite-run',
    breath: MOTIONS[0].labels[0],
    status: '跑步 · 120 BPM',
  },

  onLoad() {
    this.motionIndex = 0;
    this.tempoIndex = 1;
    this.half = 0;
  },

  refresh() {
    const motion = MOTIONS[this.motionIndex];
    const tempo = TEMPOS[this.tempoIndex];
    this.setData({
      stageClass: `stage tempo-${tempo.key}`,
      spriteClass: `sprite sprite-${motion.key}`,
      breath: motion.labels[this.half],
      status: `${motion.name} · ${tempo.bpm} BPM`,
    });
  },

  // 圆环每涨或缩完一次触发，用来切换呼吸提示
  onBreathStart() {
    this.half = 0;
    this.refresh();
  },

  onBreathTurn() {
    this.half = 1 - this.half;
    this.refresh();
  },

  switchMotion() {
    this.motionIndex = (this.motionIndex + 1) % MOTIONS.length;
    this.half = 0;
    this.refresh();
  },

  changeTempo(step) {
    this.tempoIndex = Math.max(0, Math.min(TEMPOS.length - 1, this.tempoIndex + step));
    this.refresh();
  },

  onKeyUp(event) {
    if (event.code === 'Enter') {
      this.switchMotion();
    } else if (event.code === 'ArrowUp' || event.code === 'ArrowRight') {
      this.changeTempo(1);
    } else if (event.code === 'ArrowDown' || event.code === 'ArrowLeft') {
      this.changeTempo(-1);
    }
  },
};
</script>

<page>
  <view class="container">
    <view class="{{stageClass}}">
      <view class="ring" bindanimationstart="onBreathStart" bindanimationiteration="onBreathTurn"></view>
      <view class="{{spriteClass}}" bindtap="switchMotion"></view>
    </view>
    <text class="status">{{status}} · {{breath}}</text>
    <text class="caption">单击切换动作 · 前后滑动调节奏</text>
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
  width: 300px;
  height: 300px;
}

/* 呼吸环：4 拍涨、4 拍缩 */
.ring {
  position: absolute;
  left: 0;
  top: 0;
  width: 296px;
  height: 296px;
  border: 2px solid #40FF5E;
  border-radius: 150px;
  opacity: 0.6;
  animation: breathe 2000ms ease-in-out infinite alternate;
}

@keyframes breathe {
  from { transform: scale(0.92); opacity: 0.35; }
  to { transform: scale(1); opacity: 0.8; }
}

.sprite {
  position: absolute;
  background-repeat: no-repeat;
  background-position: 0px 0px;
}

/* 跑步：12 帧，每帧 200x200，一个周期 2 拍 */
.sprite-run {
  left: 50px;
  top: 50px;
  width: 200px;
  height: 200px;
  background-image: url('/assets/run-sheet.png');
  animation: play-run 1000ms steps(12) infinite;
}

@keyframes play-run {
  from { background-position: 0px 0px; }
  to { background-position: -2400px 0px; }
}

/* 高位下拉：16 帧，每帧 117x240，一个周期 8 拍 */
.sprite-pulldown {
  left: 92px;
  top: 30px;
  width: 117px;
  height: 240px;
  background-image: url('/assets/pulldown-sheet.png');
  animation: play-pulldown 4000ms steps(16) infinite;
}

@keyframes play-pulldown {
  from { background-position: 0px 0px; }
  to { background-position: -1872px 0px; }
}

.tempo-slow .ring { animation-duration: 2667ms; }
.tempo-slow .sprite-run { animation-duration: 1333ms; }
.tempo-slow .sprite-pulldown { animation-duration: 5333ms; }

.tempo-fast .ring { animation-duration: 1600ms; }
.tempo-fast .sprite-run { animation-duration: 800ms; }
.tempo-fast .sprite-pulldown { animation-duration: 3200ms; }

.status {
  font-size: 13px;
  line-height: 16px;
  color: #40FF5E;
  margin-top: 4px;
}

.caption {
  font-size: 11px;
  line-height: 14px;
  color: #40FF5E;
  opacity: 0.75;
  margin-top: 2px;
}
</style>
