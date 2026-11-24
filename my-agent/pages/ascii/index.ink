<script def>
{
  "navigationBarTitleText": "字符节奏环"
}
</script>

<script setup>
import { RUNNER_FRAMES, RUNNER_COLS, RUNNER_ROWS } from '../../lib/runner-frames.js';
import { createAsciiPage } from '../../lib/ascii-scene.js';

// 真人跑步：一个跑步周期 2 拍，脚落地卡在拍点上；圆环 8 拍一吸一呼
export default createAsciiPage({
  frames: RUNNER_FRAMES,
  cols: RUNNER_COLS,
  rows: RUNNER_ROWS,
  cycleBeats: 2,
  breathBeats: 8,
  breathLabels: ['吸气', '呼气'],
  bpms: [90, 120, 150],
  ground: true,
});
</script>

<page>
  <view class="container">
    <view class="screen">
      <text class="row" ink:for="{{rows}}">{{item}}</text>
    </view>
    <text class="status">{{status}}</text>
    <text class="caption" bindtap="toggleMusic">{{breath}} · {{musicLabel}} · 单击开关音乐 · 前后滑动调节奏</text>
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

.screen {
  display: flex;
  flex-direction: column;
}

/* 等宽字体加 white-space: pre，保证每个字符占一格、空格不被合并 */
.row {
  font-family: monospace;
  font-size: 10px;
  line-height: 10px;
  height: 10px;
  white-space: pre;
  color: #40FF5E;
}

.status {
  font-family: monospace;
  font-size: 12px;
  line-height: 14px;
  white-space: pre;
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
