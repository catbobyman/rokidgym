// 字符画舞台：把一组字符帧（人物动作）放在一个随节拍呼吸的字符圆环里。
// 用法：在页面的 <script setup> 里 export default createAsciiPage({ ... })。

import { BeatMusic } from './beat-music.js';

// 整个画面是一张 COLS x ROWS 的字符网格，每次刷新重新算出每个格子的字符
const COLS = 62;
const ROWS = 31;
const CELL_ASPECT = 0.5;            // 字符格的宽高比（预览里实测），画圆时用来补偿
const RAMP = ' .:-=+*#%@';          // 由暗到亮
const TICK_MS = 66;                 // 约 15 帧每秒

const CENTER_X = (COLS - 1) / 2;
const CENTER_Y = 15;
const GROUND = '_  .  _ . ';

const RING_MIN = 13.0;              // 圆环半径（以行为单位）在这两个值之间涨缩
const RING_MAX = 14.6;

// 每个格子到圆心的距离和方位角只算一次
const DIST = new Float32Array(COLS * ROWS);
const ANGLE = new Float32Array(COLS * ROWS);
for (let r = 0; r < ROWS; r += 1) {
  for (let c = 0; c < COLS; c += 1) {
    const dx = (c - CENTER_X) * CELL_ASPECT;
    const dy = r - CENTER_Y;
    DIST[r * COLS + c] = Math.sqrt(dx * dx + dy * dy);
    ANGLE[r * COLS + c] = Math.atan2(dy, dx);
  }
}

/**
 * @param {object} options
 * @param {string[][]} options.frames      一个动作周期的字符帧
 * @param {number} options.cols            每帧的列数
 * @param {number} options.rows            每帧的行数
 * @param {number} options.cycleBeats      一个动作周期占几拍
 * @param {number} options.breathBeats     圆环涨缩一次（一吸一呼）占几拍
 * @param {[string, string]} options.breathLabels  圆环变大、变小时显示的文字
 * @param {number[]} options.bpms          可切换的节奏档位
 * @param {boolean} [options.ground]       是否在脚下画滚动的地面
 */
export function createAsciiPage(options) {
  const { frames, cols, rows, cycleBeats, breathBeats, breathLabels, bpms } = options;
  const left = Math.round((COLS - cols) / 2);
  const top = Math.round(CENTER_Y - rows / 2);
  const groundRow = options.ground ? top + rows : -1;
  const startTempo = Math.floor(bpms.length / 2);

  return {
    data: {
      rows: [],
      breath: breathLabels[0],
      status: `BPM ${bpms[startTempo]}  VOL [..........]`,
      musicLabel: '音乐 关',
    },

    onLoad() {
      this.music = new BeatMusic();
      this.tempoIndex = startTempo;
      this.beats = 0;               // 累计拍数（带小数），所有动画都由它推导
      this.lastBeat = 0;
      this.lastBeatAt = Date.now();
      this.lastTick = Date.now();
      this.tick();
      this.timer = setInterval(() => this.tick(), TICK_MS);
    },

    onUnload() {
      clearInterval(this.timer);
      this.timer = null;
      return this.music.stop();
    },

    tick() {
      const now = Date.now();
      const bpm = bpms[this.tempoIndex];
      this.beats += ((now - this.lastTick) / 60000) * bpm;
      this.lastTick = now;

      const beat = Math.floor(this.beats);
      if (beat !== this.lastBeat) {
        this.lastBeat = beat;
        this.lastBeatAt = now;
        this.music.playBeat(beat);
      }

      // 有音乐时用真实音量，否则按拍点算一个衰减包络
      let level = this.music.level();
      if (level === null) level = Math.exp(-(now - this.lastBeatAt) / 140);

      const breathPhase = (this.beats / breathBeats) % 1;
      const swell = (1 - Math.cos(breathPhase * 2 * Math.PI)) / 2;
      const frame = Math.floor(((this.beats / cycleBeats) % 1) * frames.length);

      const bars = Math.round(level * 10);
      this.setData({
        rows: this.compose(frames[frame], RING_MIN + (RING_MAX - RING_MIN) * swell, level),
        breath: breathLabels[breathPhase < 0.5 ? 0 : 1],
        status: `BPM ${bpm}  VOL [${'#'.repeat(bars)}${'.'.repeat(10 - bars)}]`,
      });
    },

    compose(figure, radius, level) {
      const brightest = RAMP.length - 1;
      const width = 0.4 + 0.45 * level;                  // 圆环随音量变粗
      const gain = 0.35 + 0.5 * level;                   // 也随音量变亮，但始终比人物暗
      const sweep = (this.beats / 4) * 2 * Math.PI;      // 每 4 拍绕一圈的亮斑
      const scroll = Math.floor(this.beats * 4);
      const out = [];

      for (let r = 0; r < ROWS; r += 1) {
        const figureRow = figure[r - top];
        let line = '';
        for (let c = 0; c < COLS; c += 1) {
          // 人物在最上层
          if (figureRow) {
            const ch = figureRow[c - left];
            if (ch && ch !== ' ') {
              line += ch;
              continue;
            }
          }
          const i = r * COLS + c;
          const off = (DIST[i] - radius) / width;
          if (off > -2.2 && off < 2.2) {
            const glow = Math.exp(-off * off) * gain * (0.72 + 0.28 * Math.cos(ANGLE[i] - sweep));
            const step = Math.round(glow * brightest);
            line += step > 0 ? RAMP[step] : ' ';
          } else if (r === groundRow && DIST[i] < radius - 2) {
            line += GROUND[(c + scroll) % GROUND.length];
          } else {
            line += ' ';
          }
        }
        out.push(line);
      }
      return out;
    },

    async toggleMusic() {
      try {
        if (this.music.playing) {
          await this.music.stop();
          this.setData({ musicLabel: '音乐 关' });
        } else {
          await this.music.start();
          this.setData({ musicLabel: '音乐 开' });
        }
      } catch (error) {
        console.error('音乐切换失败', error);
        // 卡片态（target 为 _current）下运行时不允许出声
        const cardMode = String(error && error.message).includes('_current');
        this.setData({ musicLabel: cardMode ? '全屏后可开音乐' : '音乐不可用' });
      }
    },

    async onTargetChanged(target) {
      if (target === '_current' && this.music.playing) {
        await this.music.stop();
      }
      if (!this.music.playing) this.setData({ musicLabel: '音乐 关' });
    },

    changeTempo(step) {
      this.tempoIndex = Math.max(0, Math.min(bpms.length - 1, this.tempoIndex + step));
    },

    onKeyUp(event) {
      if (event.code === 'Enter') {
        this.toggleMusic();
      } else if (event.code === 'ArrowUp' || event.code === 'ArrowRight') {
        this.changeTempo(1);
      } else if (event.code === 'ArrowDown' || event.code === 'ArrowLeft') {
        this.changeTempo(-1);
      }
    },
  };
}
