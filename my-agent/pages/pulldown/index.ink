<script def>
{
  "navigationBarTitleText": "高位下拉"
}
</script>

<script setup>
import { PULLDOWN_FRAMES, PULLDOWN_COLS, PULLDOWN_ROWS } from '../../lib/pulldown-frames.js';
import { createAsciiPage } from '../../lib/ascii-scene.js';

// 高位下拉：一次动作 8 拍，圆环跟动作同步——下拉时呼气，还原时吸气
export default createAsciiPage({
  frames: PULLDOWN_FRAMES,
  cols: PULLDOWN_COLS,
  rows: PULLDOWN_ROWS,
  cycleBeats: 8,
  breathBeats: 8,
  breathLabels: ['下拉 · 呼气', '还原 · 吸气'],
  bpms: [90, 120, 150],
  ground: false,
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
