# MidiMania

[English](README.md) · **简体中文**

一款跨平台、DJmax 风格的音乐节奏游戏。音符从灭点（消失点）落下并逐渐放大，朝判定线
飞来；当每个音符到达时按下对应的按键即可。每张谱面都**由 `.mid` 文件自动生成**——
放入一个 MIDI 文件就能开玩，支持电脑键盘、真实 MIDI 键盘，或观看内置的自动演示。

```
python mania.py
```

会在 OpenGL 窗口中打开 `songs/` 曲库的选曲菜单。

---

## 功能特性

- **从 MIDI 生成谱面。** 直接从 `.mid`（type 0/1）生成音符模式，无需手工编谱。
- **三种游玩方式：**
  - **电脑键盘** —— 始终可用；将乐曲的音高范围压缩到 9 条轨道
    （`A S D F Space J K L ;`）。
  - **MIDI 键盘** —— 检测并校准设备后，音符与轨道 1:1 对应，和弦也能分得清。
  - **演示（Demo）** —— 以完美时机自动游玩（100% / S 评级），用于预览乐曲或在没有
    输入设备时验证配置。
- **自动判定键盘尺寸。** 根据 MIDI 的音高范围选取能覆盖它的最小键盘尺寸
  （25 / 32 / 37 / 49 / 61 / 88 键）。
- **OpenGL 灭点透视渲染器**，配霓虹街机 UI 皮肤、屏上 HUD（分数、连击、准确率），
  以及带评级徽章的结算画面。
- **音频开箱即用。** 若谱面附带了音频轨道则播放它；否则直接由 MIDI 合成预览音频——
  因此任何乐曲无需自带音频即可游玩。
- **以音频时钟为唯一计时权威**，支持手动音画偏移，±35 / 75 / 120 ms 的判定窗口与
  连击计分。

---

## 运行要求

- **Python 3.10+**
- **OpenGL** 驱动
- 在 Linux 上：`python-rtmidi` 所需的平台 MIDI 后端（如 ALSA / JACK 开发头文件）以及
  pygame 的系统依赖

Python 依赖（见 [`requirements.txt`](requirements.txt)）：

| 包 | 作用 |
|---|---|
| `pygame` | 窗口、音频混音、事件循环、表面绘制 |
| `mido` | MIDI 文件解析 |
| `python-rtmidi` | 实时 MIDI 设备输入 |
| `PyOpenGL`（+ `PyOpenGL_accelerate`） | 透视渲染器 |

## 安装

```bash
python -m venv venv
# Windows:  venv\Scripts\activate
# macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
```

## 运行

在 `songs/` 曲库上打开**选曲菜单**（默认）：

```bash
python mania.py
python mania.py --songs path/to/library   # 使用自定义曲库目录
```

**直接游玩单张谱面：**

```bash
python mania.py SONG.mid                   # 以演示模式自动游玩
python mania.py SONG.mid --play            # 用电脑键盘自己操作
python mania.py SONG.mid --audio SONG.ogg  # 指定音频轨道
python mania.py SONG.mid --mode pc         # 9 轨电脑模式（默认：midi，1:1）
```

直接游玩单张谱面时的音频优先级：给定 `--audio` 时用它 → 与 MIDI 同名配对的成品音轨
（`SONG.mid` → 同目录下的 `SONG.ogg/.mp3/.wav/.flac`）→ 否则由 MIDI 合成的临时 WAV。

## 操作说明

**菜单：** ↑↓ 选曲 · ←→ 切换输入模式（PC / Demo / MIDI）· `K` 切换键盘尺寸 ·
`M` 打开 MIDI 设置 · `Enter` 开始 · `Esc` 退出。

**游玩中：** 按下轨道按键（电脑：`A S D F Space J K L ;`，或你的 MIDI 键盘）。
`P` / `Space` 暂停 · `Esc` 返回。

**结算后：** `Enter` 返回菜单 · `R` 重试。

**MIDI 键盘设置：** 在菜单中按 `M`，选择你的设备，然后分别按下**最低**和**最高**的
键来校准音域（MIDI 端口无法上报自身键数）。校准得到的音域会限制可用的键盘尺寸与可玩
的乐曲。

---

## 乐曲包格式

菜单会扫描 `songs/`，每首曲子对应一个文件夹。没有谱面、或 MIDI 无法解析 / 超出范围的
文件夹会被**跳过，而非报错终止**。

```
songs/<name>/
├── chart.mid                     # 必需（或文件夹内第一个 *.mid）
├── meta.json                     # 可选：{ "title", "artist", "bpm" }
└── <name>.ogg|.mp3|.wav|.flac    # 可选的成品音频；否则使用合成预览
```

`meta.json` 的所有字段均为可选；缺少 `title` 时回退为美化后的文件夹名。内置示例曲：
`bach-cello`、`chords`、`heiwa-na-hibi`、`twinkle`。

---

## 项目结构

```
mania.py              # 启动器 / 命令行入口
src/
├── app.py            # 画面流程：MENU → MIDI_SETUP → PLAYING → RESULTS
├── midi/             # 解析器（MIDI→音符）、分类器（键盘尺寸）、设备（rtmidi I/O）
├── game/             # 谱面构建、引擎（状态机）、计分、演示自动游玩
├── audio/            # 音频播放器（计时时钟）+ MIDI→WAV 合成回退
├── input/            # InputSignal 通用输入 + MIDI 音符→轨道适配器
└── ui/               # OpenGL 渲染器、几何、HUD、菜单、结算、MIDI 设置、霓虹皮肤
songs/                # 曲库（每首曲子一个文件夹）
resources/            # UI 资源（霓虹图集）
tests/                # 无头单元 / 流程测试（+ GL 冒烟测试）
ai-working-log/       # 设计文档、原始代码库报告、各功能规格、进度跟踪
```

## 架构概览

`InputSignal(lane, time_ms)` 是 PC、MIDI 与演示三种来源共用的输入载体。**音频时钟是
唯一的计时权威**——引擎用它为输入打时间戳，因此异构事件的时间不会污染判定。先绘制
OpenGL 场景，再把每一层 2D 内容（菜单、HUD、倒计时、结算）作为全屏纹理四边形叠加在
上面。外部后端（rtmidi、混音器、合成器）都置于可注入、延迟导入的接缝之后，因此模块
在无硬件时也能导入、测试也能运行。

音符通过 `note_z = (note.time_ms − current_ms) × UNITS_PER_MS` 存在于世界空间中；
透视投影将 Z 映射到屏幕 Y。位置计算是纯函数且经过单元测试。

完整设计思路与决策：
[`ai-working-log/DESIGN.md`](ai-working-log/DESIGN.md) ·
各功能详细规格见 [`ai-working-log/specs/`](ai-working-log/specs/) ·
进度见 [`ai-working-log/TRACKING.md`](ai-working-log/TRACKING.md)。

## 测试

测试在 SDL 的 dummy 视频/音频驱动下**无头运行**——无需显示器或音频设备即可验证完整
的核心与 UI 流程：

```bash
python -m pytest tests/
# 或： python -m unittest discover -s tests
```

少数 GL 冒烟测试需要真实的 OpenGL 上下文，在 dummy 驱动 / CI 下会自动跳过。

## 状态

第 1–4 阶段已完成（基础重构、游戏引擎、UI 与音频、MIDI 设备输入）；第 5 阶段打磨
进行中（霓虹街机皮肤已落地）。待办：连击/分数动画、面向大键盘（49 键以上）的滚动视
口、跨平台验证，以及 PyInstaller 打包。各功能细分见
[`ai-working-log/TRACKING.md`](ai-working-log/TRACKING.md)。

v1 暂不涉及：在线排行榜、自定义皮肤/主题、多人游戏、谱面编辑器、视频背景。
