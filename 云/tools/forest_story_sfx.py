"""森林章节剧本（data/story_forest.json）里的音效（第一批 29 个 + 第二批 12 个 + 第三批 10 个，全部程序生成，以后可以换正式的，文件名不变即可）。

    "/Users/jiamulin/Desktop/程序programs/AI Oscar/.venv/bin/python" tools/forest_story_sfx.py

输出 audio/sfx/*.wav（44.1kHz 单声道 16 位），跑完打印每个文件的时长 / 峰值 / RMS / 频谱质心，
两个循环环境声另外打印首尾样本和接缝检查。方向和 level1_sfx.py / flight_sfx.py 一样：
安静、克制、偏低频、不刺耳；室外的声音带一点潮湿的林子混响，屋里的带一点小木屋混响。

循环环境声（story_runner 的 ambient）：
  deer_knock   3.6 秒：鹿角敲树两下 + 一段安静；首尾都是精确的 0。
  water_hollow 6.0 秒：塌陷口下面空洞里的水声；尾巴和开头交叉淡化，再把起点挪到过零点。
  两个的 .import 里设了 edit/loop_mode=2（和 rain_loop 一样），播放器不会在接缝处停一帧。
  alarm_broken 4.0 秒：坏掉的警报，首尾都是 0、接缝在安静处。.import 保持 loop_mode=0（还不知道
  引擎用 ambient 还是普通 sfx 播它；普通 sfx 设了循环会永远不结束），用 ambient 播就是无缝的。

第二批（剧本补充）：elephant_call_1/2（同一个合成的低鸣，2 更远、被风盖住、回声沿山谷滚走）、
tree_sway、alarm_broken、musicbox_pat、pen_write、pen_strike、page_turn、cup_set、sugar_drop、
tool_tap、paper_slide。都加在 JOBS 最后，前 29 个的随机数顺序不变。

第三批（剧本第四版）：tap、sugar、chen_hum（合成的闭口哼，E4→D4，第二个音偏高后断掉）、
branch_shift、branch_drop、plank_drop、sap_drip、clock_open、radio_static、fire_flare。同样加在最后。

旋律（音乐盒和留声机是同一首，原创）：A 小调五声（A C D E G），3/4 拍，8 小节 24 拍。
  旋律  | E5 - D5 | C5 A4 - | G4 A4 C5 | D5 - - | E5 - G5 | E5 D5 - | C5 A4 G4 | A4 - - |
  和声  |   Am    |    F    |    C    |   Dm   |    C    |   Em   |    F     |   Am   |
  「卡住」都卡在第 3 小节第 2 拍（G4 之后、A4 那一下）：音乐盒是那根簧片被碎屑压住只剩一声闷响，
  留声机是唱针在 G4 那一圈来回跳、然后转盘慢下来停住。full 越过这个地方一直走完。
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "audio" / "sfx"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(41)


# ================================================================== 工具
def tt(sec):
    return np.arange(int(round(sec * SR))) / SR


def _fftconv(x, h):
    n = len(x) + len(h)
    N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)[: len(x)]


def lp(x, cutoff, n=1):
    """一阶低通（和 flight_sfx 一样：截断的指数冲激响应卷积），n = 叠几次。"""
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    L = int(8 / (2 * np.pi * cutoff / SR)) + 1
    h = a * (1 - a) ** np.arange(L)
    for _ in range(n):
        x = _fftconv(x, h)
    return x


def hp(x, cutoff):
    return x - lp(x, cutoff)


def band(x, lo=None, hi=None, order=2):
    """零相位 Butterworth 幅度响应的带通（FFT 里乘），用来塑形噪声和整体音色。"""
    n = len(x)
    N = 1 << (2 * n - 1).bit_length()
    f = np.fft.rfftfreq(N, 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    if hi:
        g *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    return np.fft.irfft(np.fft.rfft(x, N) * g, N)[:n]


def peak_eq(x, fc, gain_db, q=1.0):
    """在 fc 附近抬一点 / 压一点（高斯形，按倍频程算宽度）。"""
    n = len(x)
    N = 1 << (2 * n - 1).bit_length()
    f = np.fft.rfftfreq(N, 1 / SR)
    oct_ = np.log2(np.maximum(f, 1) / fc)
    g = 10 ** (gain_db / 20 * np.exp(-0.5 * (oct_ * q * 2) ** 2))
    return np.fft.irfft(np.fft.rfft(x, N) * g, N)[:n]


def lp_tv(x, cut):
    """随时间变的一阶低通（逐样本），cut 是和 x 一样长的截止频率数组。"""
    a = (1 - np.exp(-2 * np.pi * np.asarray(cut) / SR)).tolist()
    xs = x.tolist()
    y = [0.0] * len(xs)
    s = 0.0
    for i, v in enumerate(xs):
        s += a[i] * (v - s)
        y[i] = s
    return np.array(y)


def noise(n, seed=None):
    r = rng if seed is None else np.random.default_rng(seed)
    return r.standard_normal(n)


def unit(x):
    m = np.max(np.abs(x)) or 1.0
    return x / m


def mix(*xs):
    """长短不一的几段从同一刻开始叠在一起。"""
    y = np.zeros(max(len(v) for v in xs))
    for v in xs:
        y[: len(v)] += v
    return y


def add(buf, at, sig, amp=1.0):
    p = int(round(at * SR))
    if p < 0:
        sig = sig[-p:]
        p = 0
    L = min(len(sig), len(buf) - p)
    if L > 0:
        buf[p:p + L] += sig[:L] * amp
    return buf


def tone(f, sec, decay, amp=1.0, phase=0.0, attack=0.0015):
    t = tt(sec)
    return amp * np.sin(2 * np.pi * f * t + phase) * np.exp(-t / decay) * np.clip(t / attack, 0, 1)


def modal(modes, sec, attack=0.0008):
    """modes: [(频率, 衰减时间常数, 振幅)]，敲击类声音的身体。"""
    x = np.zeros(int(round(sec * SR)))
    for f, d, a in modes:
        x += tone(f, sec, d, a, phase=rng.uniform(0, 0.3), attack=attack)
    return x


def burst(sec, decay, lo=None, hi=None, seed=None):
    """一小团噪声（敲击的那一下「咔」/「噗」）。"""
    t = tt(sec)
    w = band(noise(len(t), seed), lo, hi)
    return unit(w) * np.exp(-t / decay)


def reverb(x, decay=0.8, wet=0.25, lo=150, hi=2500, pre=0.012, seed=5):
    """噪声冲激响应的混响。长度不变（调用的人自己给尾巴留够安静）。"""
    L = int(decay * SR * 1.1)
    r = np.random.default_rng(seed)
    t = np.arange(L) / SR
    ir = r.standard_normal(L) * np.exp(-t * 6.91 / decay)
    ir = band(ir, lo, hi)
    ir[: int(pre * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum())
    return x + wet * _fftconv(x, ir)


def wet_forest(x, wet=0.22):
    """室外：雨夜林子，散、暗、有点潮。"""
    return reverb(x, decay=1.1, wet=wet, lo=120, hi=1800, pre=0.02, seed=7)


def wet_room(x, wet=0.16):
    """树屋里：小木屋，短、暖。"""
    return reverb(x, decay=0.55, wet=wet, lo=150, hi=3000, pre=0.006, seed=9)


def warp(x, rate):
    """变速播放（像转盘变慢）：rate 是每个输出样本前进多少个输入样本。"""
    pos = np.concatenate([[0.0], np.cumsum(rate)[:-1]])
    pos = pos[pos < len(x) - 1]
    return np.interp(pos, np.arange(len(x)), x)


def fades(x, fin=0.002, fout=0.03):
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b) ** 2
    return x


def loop_xfade(x, n, xf):
    """x 至少 n + xf 长：把 [n, n+xf) 交叉淡化进开头，得到长度 n 的无缝循环。"""
    head, tail = x[:xf], x[n:n + xf]
    f = np.sin(np.linspace(0, np.pi / 2, xf)) ** 2      # 等功率一点的曲线
    y = x[:n].copy()
    y[:xf] = head * f + tail * (1 - f)
    return y


def rotate_to_zero(y):
    """循环的起点挪到一个往上的过零点（转一圈的循环还是无缝的）。"""
    s = np.signbit(y)
    idx = np.where(s[:-1] & ~s[1:])[0]
    if len(idx) == 0:
        return y
    k = idx[np.argmin(np.abs(y[idx]) + np.abs(y[idx + 1]))] + 1
    return np.roll(y, -k)


def mtof(m, cents=0.0):
    return 440.0 * 2 ** ((m - 69) / 12 + cents / 1200)


STATS: list[tuple] = []


def save(name, x, peak, loop=False):
    m = np.max(np.abs(x)) or 1.0
    x = x / m * peak
    if not loop:
        x = fades(x)
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(OUT / (name + ".wav")), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    STATS.append((name, pcm.astype(float) / 32768, loop))


# ================================================================== 旋律（音乐盒 / 留声机共用）
# (拍, 拍长, midi)
MEL = [(0, 2, 76), (2, 1, 74),
       (3, 1, 72), (4, 2, 69),
       (6, 1, 67), (7, 1, 69), (8, 1, 72),
       (9, 3, 74),
       (12, 2, 76), (14, 1, 79),
       (15, 1, 76), (16, 2, 74),
       (18, 1, 72), (19, 1, 69), (20, 1, 67),
       (21, 3, 69)]
# 每小节：低音根音、第二拍的内声部、和弦（留声机的垫底）
BARS = [(57, 64, (57, 60, 64)),   # Am
        (53, 60, (53, 57, 60)),   # F
        (48, 64, (55, 60, 64)),   # C
        (50, 65, (57, 62, 65)),   # Dm
        (48, 64, (55, 60, 64)),   # C
        (52, 59, (55, 59, 64)),   # Em
        (53, 60, (53, 57, 60)),   # F
        (57, 64, (57, 60, 64))]   # Am
STUCK_BEAT = 7       # 第 3 小节第 2 拍（G4 后面那个 A4）

# 旧音乐盒：每根簧片固定的走音（同一根簧片每次都一样跑调），音分
_tr = np.random.default_rng(1977)
MB_DETUNE = {m: float(_tr.uniform(-16, 16)) for m in range(40, 90)}
MB_DETUNE[69] = -19.0     # 卡住的那根也偏低
_tj = np.random.default_rng(311)
MB_JITTER = [float(_tj.uniform(-0.012, 0.012)) for _ in range(64)]


def mb_events(upto=None):
    """[(拍, midi, 力度, 是低音吗)]，upto = 只要这一拍之前的。"""
    ev = []
    for b, _, m in MEL:
        ev.append((b, m, 1.0, False))
    for i, (root, inner, _) in enumerate(BARS):
        ev.append((i * 3, root, 0.62, True))
        if i < 7:
            ev.append((i * 3 + 1, inner, 0.28, False))
        else:
            ev.append((i * 3, inner, 0.3, False))         # 最后一小节：根音和五度一起落
    ev.sort()
    if upto is not None:
        ev = [e for e in ev if e[0] < upto]
    return ev


def mb_note(m, vel):
    f = mtof(m, MB_DETUNE[m])
    sec = 3.6
    t = tt(sec)
    tau = 1.25 * (440 / f) ** 0.45
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / tau)
    x += 0.10 * np.sin(2 * np.pi * (f + 0.8) * t + 1.0) * np.exp(-t / tau)        # 旧簧片：一点点拍频
    x += 0.10 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / (tau * 0.35))
    x += 0.05 * np.sin(2 * np.pi * min(5.93 * f, 6500) * t) * np.exp(-t / 0.05)   # 簧片的金属「叮」
    x *= np.clip(t / 0.0012, 0, 1)
    x[: int(0.004 * SR)] += unit(band(noise(int(0.004 * SR)), 800, 4500)) * 0.12 * np.exp(-np.arange(int(0.004 * SR)) / 40)
    return x * vel


def mb_time(b, beat, rit=True):
    extra = 0.03 * max(0, b - 17) ** 2 if rit else 0.0
    return beat * (b + extra)


def musicbox(full=True):
    beat = 0.6
    lead = 0.7 if full else 0.15
    upto = None if full else STUCK_BEAT
    end_b = 24 if full else STUCK_BEAT
    total = lead + mb_time(end_b, beat) + (2.5 if full else 1.8)
    x = np.zeros(int(total * SR))
    for i, (b, m, vel, is_bass) in enumerate(mb_events(upto)):
        add(x, lead + mb_time(b, beat) + MB_JITTER[i % 64], mb_note(m, vel))
    # 发条和滚筒：很轻的机械沙沙（只在转的时候）
    t = np.arange(len(x)) / SR
    play_end = lead + mb_time(end_b, beat) + (0.25 if full else 0.0)
    mech = band(noise(len(t)), 300, 1600) * (0.55 + 0.45 * np.sin(2 * np.pi * 11 * t) ** 2)
    on = np.clip((t - lead + 0.1) / 0.1, 0, 1) * np.clip((play_end - t) / 0.12, 0, 1)
    if full:   # 最后发条松了：沙沙也慢慢没了
        on *= np.clip((play_end - t) / 2.5, 0, 1) ** 0.5
    x += unit(mech) * 0.012 * on
    if not full:
        # 卡住：那根簧片被压住，只有一声闷闷的「嗒」，滚筒顿一下停了
        at = lead + mb_time(STUCK_BEAT, beat) + 0.05
        thunk = mix(tone(mtof(69, -19), 0.2, 0.022, 0.5), burst(0.05, 0.008, 200, 1400) * 0.35,
                    modal([(190, 0.04, 0.35), (430, 0.03, 0.2), (1250, 0.012, 0.08)], 0.25))
        add(x, at, thunk)
        add(x, at + 0.11, modal([(1650, 0.01, 0.12), (2600, 0.006, 0.06)], 0.08))   # 齿轮最后一下小「咔」
    x = peak_eq(x, 650, 3, 0.8)            # 小木盒的共鸣
    x = band(x, 120, 5200)
    return wet_room(x, 0.18)


def piano(m, vel, cents=0.0, sec=3.2):
    f = mtof(m, cents)
    t = tt(sec)
    x = np.zeros(len(t))
    for k in range(1, 8):
        fk = k * f * np.sqrt(1 + 0.0004 * k * k)
        if fk > 7000:
            break
        x += (1 / k ** 1.5) * np.sin(2 * np.pi * fk * t + k) * np.exp(-t / (1.7 * (440 / f) ** 0.3 / k ** 0.65))
    x *= np.clip(t / 0.003, 0, 1)
    return x * vel


def record_dry(beat, upto=None):
    """唱片里录的东西：钢琴旋律 + 低音 + 很轻的和弦垫底。"""
    end_b = 24 if upto is None else upto
    total = beat * end_b + 2.8
    x = np.zeros(int(total * SR))
    _j = np.random.default_rng(55)
    for b, _, m in MEL:
        if upto is not None and b >= upto:
            continue
        add(x, b * beat + _j.uniform(-0.01, 0.01), piano(m, 0.9))
    for i, (root, inner, chord) in enumerate(BARS):
        if upto is not None and i * 3 >= upto:
            continue
        add(x, i * 3 * beat, piano(root - 12, 0.55, sec=4.0))
        L = 3 * beat + 0.6 if i < 7 else 3.2
        t = tt(L)
        e = np.clip(t / 0.35, 0, 1) * np.clip((L - t) / 0.5, 0, 1)
        pad = sum(np.sin(2 * np.pi * mtof(c) * t + c) for c in chord) * 0.05 * e
        if upto is not None:
            pad = pad[: max(0, int((upto - i * 3) * beat * SR) + int(0.4 * SR))]
        add(x, i * 3 * beat, pad)
    return x


def gramo_process(x, seed, cut_hi=3000, wet=0.18, wow=True):
    """老留声机：喇叭的窄频带、转速微微晃、表面沙沙和噼啪、每转一圈一个很轻的「嗒」。"""
    if wow:
        t = np.arange(len(x)) / SR
        rate = 0.988 * (1 + 0.0045 * np.sin(2 * np.pi * 0.55 * t) + 0.0012 * np.sin(2 * np.pi * 3.3 * t + 1))
        x = warp(x, rate)
    x = band(x, 280, cut_hi, order=2)
    x = peak_eq(x, 1100, 4, 1.0)               # 喇叭的鼻音
    r = np.random.default_rng(seed)
    n = len(x)
    t = np.arange(n) / SR
    level = np.max(np.abs(x)) or 1.0
    hiss = band(r.standard_normal(n), 400, 2600) * 0.010 * (1 + 0.25 * np.sin(2 * np.pi * 1.3 * t))
    cr = np.zeros(n)
    for p in r.integers(0, n, int(n / SR * 9)):
        cr[p] = r.uniform(-1, 1) * r.uniform(0.02, 0.09)
    for k in range(int(n / SR * 1.3)):      # 78 转：每圈一下
        p = int((k / 1.3 + 0.21) * SR)
        if p < n:
            cr[p] += 0.05
    cr = band(cr, 500, 3500)
    cr = cr / (np.max(np.abs(cr)) or 1) * 0.07
    return wet_room(x / level + unit(hiss) * 0.010 + cr, wet), r


G_BEAT = 0.68
G_LEAD = 0.55


def gramophone_full(quiet=False):
    rec = record_dry(G_BEAT)
    x = np.concatenate([np.zeros(int(G_LEAD * SR)), rec])
    y, r = gramo_process(x, seed=3 if not quiet else 8, cut_hi=3000 if not quiet else 1700,
                         wet=0.18 if not quiet else 0.42)
    # 放针：开头一下软的「嘟」
    add(y, 0.0, mix(tone(70, 0.3, 0.06, 0.25), burst(0.03, 0.006, 300, 2000) * 0.12))
    t = np.arange(len(y)) / SR
    e = np.clip((len(y) / SR - t) / 1.2, 0, 1)
    if quiet:
        e *= np.clip(t / 1.5, 0, 1)   # 远：慢慢淡进来
    return y * e


def gramophone_stuck():
    """放到 G4 那一圈，唱针来回跳两次，然后转盘慢下来停住。"""
    rec = record_dry(G_BEAT, upto=STUCK_BEAT)
    x = np.concatenate([np.zeros(int(G_LEAD * SR)), rec])
    cut = G_LEAD + (STUCK_BEAT - 0.12) * G_BEAT     # 跳回去的地方：正好在 A4 之前
    rev = 0.77                                       # 一圈
    a, b = int((cut - rev) * SR), int(cut * SR)
    frag = x[a:b]
    parts = [x[:b], frag, frag]
    joins = [b / SR, (b + len(frag)) / SR]
    # 最后一圈半慢下来：音高往下掉，停住
    slow_src = np.concatenate([frag, frag[: len(frag) // 2]])
    tl = np.arange(int(1.5 * SR)) / SR
    rate = np.clip(1 - tl / 1.3, 0, 1) ** 1.3
    slow = warp(slow_src, rate)
    slow *= np.clip(1 - np.arange(len(slow)) / len(slow), 0, 1) ** 0.6
    body = np.concatenate(parts + [slow, np.zeros(int(0.35 * SR))])
    y, r = gramo_process(body, seed=12)
    for j in joins + [(len(np.concatenate(parts))) / SR]:   # 跳针的「嗒」（不尖）
        add(y, j * 0.988 ** -1, burst(0.03, 0.005, 300, 2500) * 0.18)
    add(y, 0.0, mix(tone(70, 0.3, 0.06, 0.25), burst(0.03, 0.006, 300, 2000) * 0.12))
    t = np.arange(len(y)) / SR
    return y * np.clip((len(y) / SR - t) / 0.4, 0, 1)


# ================================================================== 坠毁现场 / 飞船
def metal_clank():
    """零件往船上一靠：一声闷的金属「哐」，跟一下小的回弹。"""
    x = np.zeros(int(0.8 * SR))
    add(x, 0.0, modal([(410, 0.20, 0.6), (1130, 0.11, 0.35), (1870, 0.07, 0.2), (2650, 0.045, 0.1)], 0.8))
    add(x, 0.0, burst(0.05, 0.01, 200, 2500) * 0.5)
    add(x, 0.0, tone(120, 0.3, 0.06, 0.5))
    add(x, 0.055, modal([(430, 0.09, 0.25), (1210, 0.05, 0.12)], 0.4))
    return wet_forest(band(x, 80, 4000), 0.2)


def crank(sec, seed):
    """起动机转：一下一下的「突突」（7 下 / 秒）+ 低的电机嗡。"""
    t = tt(sec)
    n = len(t)
    f = 120 + 50 * np.clip(t / 0.6, 0, 1)
    ph = 2 * np.pi * np.cumsum(f) / SR
    whine = 0.5 * np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)
    pulse = (0.5 + 0.5 * np.sin(2 * np.pi * 7 * t - 1.5)) ** 3
    chug = band(noise(n, seed), 50, 500) * pulse
    thump = np.zeros(n)
    for k in range(int(sec * 7)):
        add(thump, k / 7 + 0.03, tone(62, 0.15, 0.04, 0.6))
    return whine * 0.35 * (0.7 + 0.3 * pulse) + unit(chug) * 0.45 + thump


def drone(t, f0, bright=0.0):
    """引擎的低嗡（和 flight_engine_loop 同一家：55Hz 和几条泛音），f0 可以是数组。"""
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(f0, t.shape)) / SR
    x = 0.55 * np.sin(ph) + 0.3 * np.sin(2 * ph + 0.4) + (0.12 + 0.15 * bright) * np.sin(3 * ph + 1.1)
    x += (0.06 + 0.12 * bright) * np.sin(5 * ph) + 0.08 * bright * np.sin(7 * ph)
    return x


def engine_try():
    sec = 1.5
    t = tt(sec)
    x = crank(sec, 3) * np.clip(t / 0.05, 0, 1) * np.clip((sec - t) / 0.18, 0, 1)
    return band(x, 40, 2500)


def engine_fail():
    """差一点着了：嗡一下 → 两声咳 → 音往下掉、熄掉，最后一声闷「咔」和一口泄气。"""
    sec = 2.6
    t = tt(sec)
    f = 56 - 26 * np.clip((t - 0.5) / 1.3, 0, 1) ** 1.2
    amp = np.clip(t / 0.15, 0, 1) * np.clip(1 - (t - 0.45) / 1.35, 0, 1) ** 1.5
    x = drone(t, f) * amp * 0.8
    x *= 1 - 0.5 * np.exp(-((t - 0.32) / 0.04) ** 2) - 0.5 * np.exp(-((t - 0.62) / 0.05) ** 2)   # 断两下
    for at, a in ((0.3, 0.8), (0.6, 0.6)):
        add(x, at, mix(burst(0.25, 0.07, 40, 420) * a, tone(80, 0.2, 0.05, 0.5 * a)))
    add(x, 1.62, mix(modal([(300, 0.08, 0.35), (720, 0.05, 0.2), (1300, 0.02, 0.06)], 0.5), burst(0.04, 0.01, 100, 1500) * 0.2))
    hs = band(noise(int(0.9 * SR)), 600, 2400)
    add(x, 1.68, unit(hs) * 0.07 * np.sin(np.pi * np.clip(tt(0.9) / 0.9, 0, 1)) ** 2)
    return wet_forest(band(x, 30, 3000), 0.15)


def engine_test():
    """修好以后试机：短短转一下，着了，平稳地嗡一秒多，关掉。"""
    sec = 3.4
    t = tt(sec)
    x = np.zeros(len(t))
    add(x, 0.0, crank(0.55, 5) * np.clip(tt(0.55) / 0.04, 0, 1) * np.clip((0.55 - tt(0.55)) / 0.1, 0, 1), 0.8)
    f = 55 + 3 * np.clip((t - 0.5) / 0.6, 0, 1) - 6 * np.clip((t - 2.5) / 0.7, 0, 1)
    amp = np.clip((t - 0.42) / 0.35, 0, 1) * np.clip((3.25 - t) / 0.75, 0, 1)
    x += drone(t, f, 0.2) * amp * 0.85
    air = band(noise(len(t)), 120, 700)
    x += unit(air) * 0.12 * amp
    add(x, 0.45, tone(60, 0.3, 0.08, 0.5))           # 着火那一下
    return band(x, 30, 3000)


def engine_start():
    """最后起飞：转、着、嗡越来越满、音往上走、气流涌起来，然后飞远。最长、最有力。"""
    sec = 7.5
    t = tt(sec)
    n = len(t)
    x = np.zeros(n)
    add(x, 0.0, crank(0.7, 9) * np.clip(tt(0.7) / 0.04, 0, 1) * np.clip((0.7 - tt(0.7)) / 0.12, 0, 1), 0.75)
    add(x, 0.62, mix(tone(48, 0.6, 0.15, 0.9), burst(0.3, 0.06, 40, 600) * 0.5))   # 着火：一声厚的「轰」
    rise = np.clip((t - 0.7) / 4.0, 0, 1)
    f = 50 + 28 * rise ** 1.4
    amp = np.clip((t - 0.6) / 0.5, 0, 1) * (0.75 + 0.25 * rise)
    away = np.clip(1 - (t - 4.8) / 2.6, 0, 1) ** 1.6      # 飞远
    x += drone(t, f, rise) * amp * away
    w = band(noise(n), 100, None)
    cut = 350 + 1500 * np.sin(np.pi * np.clip((t - 0.8) / 5.6, 0, 1)) ** 1.5
    air = lp_tv(lp_tv(w, cut), cut)
    air = unit(air) * (0.15 + 0.5 * np.sin(np.pi * np.clip((t - 0.8) / 6.0, 0, 1)) ** 2) * np.clip((t - 0.7) / 0.3, 0, 1)
    x += air * np.clip((sec - t) / 1.0, 0, 1)
    x *= 1 + 0.04 * np.sin(2 * np.pi * 9 * t) * np.clip(1 - rise, 0, 1)    # 刚着的时候有点抖
    return wet_forest(band(x, 30, 3500), 0.18)


# ================================================================== 旧路
def drag_grains(sec, rate, lo, hi, seed):
    """拖东西：一串很短的颗粒（叶子、泥、小枝刮过）。"""
    r = np.random.default_rng(seed)
    n = int(sec * SR)
    x = np.zeros(n)
    k = int(sec * rate)
    for _ in range(k):
        p = r.integers(0, n - 3000)
        L = int(r.integers(150, 1500))
        g = r.standard_normal(L) * np.exp(-np.arange(L) / (L / 3)) * r.uniform(0.2, 1.0)
        x[p:p + L] += g
    return band(x, lo, hi)


def branch_drag():
    sec = 1.8
    t = tt(sec)
    e = np.sin(np.pi * np.clip(t / 1.55, 0, 1)) ** 0.8 * (0.75 + 0.25 * np.sin(2 * np.pi * 2.6 * t))
    leaves = unit(drag_grains(sec, 260, 350, 2600, 21)) * e
    mud = unit(band(noise(len(t)), 60, 400)) * 0.35 * e
    x = leaves * 0.7 + mud
    for at in (0.42, 1.05):                                 # 小枝折一下（很软）
        add(x, at, mix(modal([(1400, 0.012, 0.25), (2300, 0.008, 0.12)], 0.06), burst(0.03, 0.006, 600, 3000) * 0.18))
    return wet_forest(band(x, 50, 3200), 0.22)


def log_push():
    """推倒木：低低的滚、木头吱一下，最后闷闷地落进泥里。"""
    sec = 2.2
    t = tt(sec)
    n = len(t)
    roll_e = np.clip(t / 0.25, 0, 1) * np.clip((1.35 - t) / 0.3, 0, 1)
    roll = unit(band(noise(n), 40, 260)) * (0.6 + 0.4 * np.sin(2 * np.pi * 2.8 * t) ** 2) * roll_e
    x = roll * 0.55
    x += unit(drag_grains(sec, 120, 200, 1600, 33)) * 0.25 * roll_e
    # 木头被压得吱一声：低的摩擦音（脉冲串过木头的共鸣）
    cr = np.zeros(n)
    pp = 0.35
    while pp < 0.95:
        add(cr, pp, modal([(520, 0.01, 0.5), (1150, 0.006, 0.25)], 0.03))
        pp += 1 / (55 + 25 * np.sin(np.pi * (pp - 0.35) / 0.6))
    x += cr * 0.35 * 0.6
    add(x, 1.32, mix(tone(58, 0.6, 0.12, 0.9), burst(0.4, 0.07, 40, 500) * 0.55, modal([(170, 0.08, 0.3), (390, 0.05, 0.15)], 0.4)))
    add(x, 1.36, unit(drag_grains(0.5, 300, 300, 1800, 34)) * 0.12 * np.exp(-tt(0.5) / 0.12))   # 泥溅一点
    return wet_forest(band(x, 30, 2500), 0.24)


def wood_tap(at, buf, amp, bright=1.0, seed=0):
    """敲树干（鹿角是硬的：多一点点「嗒」）。"""
    r = np.random.default_rng(seed)
    d = r.uniform(0.97, 1.03)
    body = modal([(212 * d, 0.075, 0.6), (468 * d, 0.05, 0.4), (870 * d, 0.03, 0.22), (1580 * d, 0.015, 0.1)], 0.5)
    body = mix(body, tone(105 * d, 0.3, 0.045, 0.35))
    click = burst(0.012, 0.0018, 1500, 4500, seed=seed + 1) * 0.28 * bright
    add(buf, at, mix(body, click) * amp)


def deer_knock():
    """循环：两下鹿角敲树 + 一段雾里的安静。3.6 秒，首尾都是 0。"""
    sec = 3.6
    x = np.zeros(int(sec * SR))
    wood_tap(0.10, x, 1.0, 1.0, seed=2)
    wood_tap(0.37, x, 0.78, 0.8, seed=5)
    x = band(x, 70, 3500)
    x = wet_forest(x, 0.3)
    t = tt(sec)
    x *= np.clip((sec - 0.05 - t) / 1.0, 0, 1) ** 2      # 尾巴 2.5 秒后已经 < -60dB，再收到精确的 0
    x[: int(0.06 * SR)] = 0
    x[-int(0.05 * SR):] = 0
    return x


def water_hollow():
    """循环：塌陷口下面空着，水在里面流：低低的流水 + 空洞的共鸣 + 咕噜的水泡。6 秒。"""
    sec = 6.0
    extra = 1.5
    n = int(sec * SR)
    N = int((sec + extra) * SR)
    t = np.arange(N) / SR
    flow = band(noise(N), 70, 900) * (0.8 + 0.2 * np.sin(2 * np.pi * t / sec * 2 + 0.3))
    flow = unit(flow) * 0.35
    bub = np.zeros(N)
    r = np.random.default_rng(77)
    for _ in range(int((sec + extra) * 14)):
        p = r.uniform(0, sec + extra - 0.2)
        dur = r.uniform(0.03, 0.09)
        f0 = r.uniform(240, 700)
        tb = tt(dur + 0.05)
        f = f0 * (1 + 1.8 * tb)            # 水泡：音往上一挑
        b = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tb / (dur / 2.5)) * np.clip(tb / 0.002, 0, 1)
        add(bub, p, b, r.uniform(0.1, 0.45))
    for _ in range(int((sec + extra) * 1.2)):            # 偶尔一声低的「咕咚」
        p = r.uniform(0, sec + extra - 0.4)
        tb = tt(0.3)
        f = r.uniform(120, 170) * (1 + 0.9 * tb)
        add(bub, p, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tb / 0.06) * np.clip(tb / 0.004, 0, 1), r.uniform(0.15, 0.3))
    x = flow + bub
    # 下面是空的：反馈梳状滤波（7ms ≈ 143Hz 的空腔共鸣），再一层洞里的混响
    D = int(0.007 * SR)
    y = x.copy()
    for k in range(1, 14):
        y[k * D:] += (0.62 ** k) * x[:-k * D]
    y = reverb(band(y, 50, 2200), decay=1.6, wet=0.35, lo=80, hi=1400, pre=0.03, seed=13)
    y = loop_xfade(y, n, int(1.0 * SR))
    return rotate_to_zero(y)


# ================================================================== 树屋
def rattle():
    """弥洛晃那块坏零件：里面有松掉的小东西，三下沙啦。"""
    sec = 1.1
    x = np.zeros(int(sec * SR))
    r = np.random.default_rng(91)
    for s0 in (0.0, 0.26, 0.5):
        for _ in range(r.integers(7, 12)):
            at = s0 + abs(r.normal(0.03, 0.035))
            f = r.uniform(1300, 3000)
            add(x, at, modal([(f, r.uniform(0.006, 0.018), 1.0), (f * 1.63, 0.006, 0.4)], 0.08), r.uniform(0.1, 0.35))
        add(x, s0, modal([(330, 0.05, 0.3), (760, 0.03, 0.15)], 0.3))     # 壳子本身闷闷一下
    return wet_room(band(x, 150, 4200), 0.16)


def screw_dish():
    """装螺丝的小碟子：手指拨一下，几颗螺丝在瓷碟里叮叮碰。"""
    sec = 1.0
    x = np.zeros(int(sec * SR))
    r = np.random.default_rng(17)
    dish = [(1720, 0.16, 0.5), (2830, 0.09, 0.25), (4100, 0.04, 0.08)]
    for at, a in ((0.0, 0.8), (0.07, 0.45), (0.15, 0.55), (0.28, 0.3), (0.41, 0.18)):
        d = r.uniform(0.98, 1.02)
        add(x, at + r.uniform(-0.01, 0.01), modal([(f * d, dd, aa) for f, dd, aa in dish], 0.6) * a)
        add(x, at, burst(0.01, 0.0015, 1500, 5000) * 0.25 * a)
    return wet_room(band(x, 300, 4800), 0.15)


def kettle_whistle():
    """水壶：先是一口气，然后一个低低的、有气的哨音冒出来，被拿开、落下去。不尖。"""
    sec = 3.0
    t = tt(sec)
    n = len(t)
    e = np.clip((t - 0.2) / 1.0, 0, 1) ** 1.5 * np.clip((sec - 0.1 - t) / 0.9, 0, 1) ** 1.5
    f = 960 + 110 * np.clip((t - 0.3) / 1.6, 0, 1) - 140 * np.clip((t - 2.0) / 0.9, 0, 1)
    f = f * (1 + 0.006 * np.sin(2 * np.pi * 5.2 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    whistle = (np.sin(ph) + 0.12 * np.sin(2 * ph)) * (0.85 + 0.15 * unit(lp(noise(n), 30)))
    breath = unit(band(noise(n), 500, 2400)) * np.clip(t / 0.6, 0, 1) * np.clip((sec - t) / 0.6, 0, 1)
    bubbles = unit(band(noise(n), 80, 400)) * 0.3 * np.clip(t / 0.3, 0, 1) * np.clip((2.2 - t) / 0.6, 0, 1)
    x = whistle * e * 0.5 + breath * 0.35 + bubbles * 0.5
    return wet_room(band(x, 60, 3000), 0.15)


def sigh():
    """弥洛叹气：一口短短的气声（不是人声采样），先吸一点，再长长地呼出去。"""
    sec = 1.25
    t = tt(sec)
    n = len(t)
    w = noise(n)
    inhale = unit(band(w, 900, 2600)) * 0.25 * np.sin(np.pi * np.clip(t / 0.22, 0, 1)) ** 2
    cut = 1700 - 900 * np.clip((t - 0.28) / 0.9, 0, 1)
    exh = lp_tv(lp_tv(band(w, 250, None), cut), cut)
    exh = band(peak_eq(exh, 550, 5, 1.2), None, 2200)   # 一点点「哈」的腔，再压暗
    exe = np.clip((t - 0.26) / 0.1, 0, 1) * np.clip((sec - t) / 0.85, 0, 1) ** 1.6
    return inhale + unit(exh) * exe


def pipe_tap(sec, modes, click_hi, damp_noise=0.0):
    x = modal(modes, sec)
    add(x, 0.0, burst(0.02, 0.002, 600, click_hi) * 0.2)
    if damp_noise:
        add(x, 0.0, burst(0.12, 0.025, 60, 500) * damp_noise)
    return x


def pipe_clear():
    """好管道：清清脆脆，像敲空瓶子——一个干净的音，余音长。"""
    x = pipe_tap(1.4, [(880, 0.45, 0.7), (1760, 0.18, 0.12), (2570, 0.09, 0.08), (5150, 0.03, 0.02)], 3500)
    return wet_room(band(x, 200, 6000), 0.18)


def pipe_dull():
    """积灰的管道：闷闷的，像隔着被子——低、短、没有余音。"""
    x = pipe_tap(0.5, [(250, 0.05, 0.6), (560, 0.025, 0.25), (930, 0.012, 0.08)], 900, damp_noise=0.45)
    return wet_room(band(x, 60, 1200), 0.1)


def pipe_hiss():
    """漏气的管道：一下普通的敲，然后一缕很细的尖响漏气声（窄、高、轻，带一点颤）。"""
    sec = 2.0
    t = tt(sec)
    n = len(t)
    x = np.zeros(n)
    add(x, 0.0, pipe_tap(0.5, [(620, 0.08, 0.5), (1350, 0.04, 0.2)], 2500), 0.55)
    e = np.clip((t - 0.12) / 0.25, 0, 1) * np.clip((sec - t) / 0.5, 0, 1)
    fl = 1 + 0.25 * unit(lp(noise(n), 6)) + 0.1 * np.sin(2 * np.pi * 7 * t)
    hiss = band(noise(n), 3300, 4600, order=4)
    whistle = np.sin(2 * np.pi * np.cumsum(3750 * (1 + 0.004 * unit(lp(noise(n), 4)))) / SR)
    x += (unit(hiss) * 0.13 + whistle * 0.06) * e * fl
    return wet_room(x, 0.12)


def wrench():
    """扳手：棘轮咔哒几下，越拧越紧，最后一下用力的闷响。"""
    sec = 1.3
    x = np.zeros(int(sec * SR))
    at = 0.0
    for k in range(6):
        add(x, at, mix(modal([(2150, 0.009, 0.35), (3300, 0.005, 0.15), (880, 0.02, 0.3)], 0.08), burst(0.008, 0.0012, 1000, 4500) * 0.2))
        at += 0.11 + 0.012 * k
    add(x, at + 0.05, mix(modal([(310, 0.07, 0.5), (690, 0.05, 0.3), (1540, 0.02, 0.1)], 0.5), burst(0.03, 0.008, 100, 1500) * 0.3))
    return wet_room(band(x, 150, 4500), 0.15)


def small_click():
    """一个小小的「咔」：拨回开关 / 扣上卡扣。"""
    x = modal([(1850, 0.008, 0.5), (3050, 0.004, 0.2), (620, 0.015, 0.35)], 0.18)
    add(x, 0.0, burst(0.006, 0.001, 1000, 4000) * 0.25)
    return wet_room(band(x, 200, 4500), 0.12)


def scrape():
    """弥洛用小工具刮音乐盒里的碎屑：两下细细的刮擦（一顿一顿的摩擦）。"""
    sec = 0.75
    t = tt(sec)
    n = len(t)
    x = np.zeros(n)
    for s0, L in ((0.0, 0.26), (0.36, 0.3)):
        tl = tt(L)
        stick = (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(90 + 60 * tl / L) / SR)) ** 4      # 一顿一顿
        g = unit(band(noise(len(tl)), 1300, 3800)) * stick * np.sin(np.pi * tl / L) ** 0.7
        add(x, s0, g)
    add(x, 0.66, modal([(2400, 0.01, 0.2)], 0.05))      # 一颗碎屑弹出去
    return wet_room(band(x, 400, 4000), 0.1)


def box_close():
    """小木盒合上：软的一下「嗒」，紧跟着扣上的小咔。"""
    x = np.zeros(int(0.6 * SR))
    add(x, 0.0, mix(modal([(230, 0.05, 0.6), (520, 0.035, 0.35), (940, 0.02, 0.15)], 0.5), burst(0.04, 0.006, 100, 1500) * 0.35))
    add(x, 0.045, modal([(1900, 0.006, 0.25), (3100, 0.003, 0.1)], 0.05))
    return wet_room(band(x, 70, 4000), 0.16)


# ================================================================== 外面
def hoof(seed, amp):
    r = np.random.default_rng(seed)
    x = tone(r.uniform(80, 100), 0.25, 0.035, 0.7)
    x = mix(x, burst(0.25, 0.03, 80, 900, seed=seed) * 0.5)                 # 湿泥「噗」
    x += np.pad(burst(0.03, 0.004, 900, 2800, seed=seed + 1) * 0.12, (0, len(x) - int(0.03 * SR)))   # 蹄子边一点点硬
    sq = unit(band(r.standard_normal(int(0.12 * SR)), 300, 1600)) * np.exp(-np.arange(int(0.12 * SR)) / (0.03 * SR)) * 0.18
    add(x, 0.04, sq)                                                    # 抬脚的那点湿
    return x * amp


def deer_steps():
    """屋外鹿走过来：湿泥和落叶上的蹄子，越来越近，然后停住。"""
    sec = 3.0
    x = np.zeros(int(sec * SR))
    at = 0.05
    for k in range(8):
        a = (0.45 + 0.55 * k / 7) * (1.0 if k % 2 == 0 else 0.8)
        add(x, at, hoof(100 + k, a))
        add(x, at + 0.02, unit(drag_grains(0.15, 200, 400, 2500, 200 + k)) * 0.08 * a)   # 踩到叶子
        at += 0.3 + (0.04 if k % 2 else 0.0) + (0.06 if k >= 6 else 0.0)
    return wet_forest(band(x, 50, 3000), 0.28)


def knock():
    """敲一下空屋的木门（剧本里连敲两次）：指节、木板、门后面空空的。"""
    x = np.zeros(int(0.7 * SR))
    add(x, 0.0, modal([(142, 0.09, 0.6), (330, 0.06, 0.45), (590, 0.035, 0.25), (1050, 0.018, 0.1)], 0.7))
    add(x, 0.0, burst(0.015, 0.002, 600, 3000) * 0.25)
    x = band(x, 60, 3000)
    x = reverb(x, decay=0.9, wet=0.3, lo=100, hi=1500, pre=0.015, seed=19)   # 门后面是空屋
    return wet_forest(x, 0.15)


def door_touch():
    """手碰到旧商店的门：门在框里轻轻挪一下，吱——很短很低，框上一点点松动的响。"""
    sec = 1.3
    t = tt(sec)
    x = np.zeros(len(t))
    pp = 0.08
    while pp < 0.75:      # 一顿一顿的摩擦脉冲（越来越慢）
        u = (pp - 0.08) / 0.67
        add(x, pp, modal([(480, 0.012, 0.6), (1020, 0.007, 0.3), (1900, 0.003, 0.08)], 0.04), 0.35 + 0.65 * np.sin(np.pi * u))
        pp += 1 / (70 - 35 * u)
    add(x, 0.8, mix(modal([(260, 0.05, 0.35), (610, 0.03, 0.2)], 0.3), burst(0.02, 0.004, 200, 2000) * 0.15))
    add(x, 0.86, modal([(1500, 0.01, 0.12), (2300, 0.006, 0.06)], 0.05))
    return wet_forest(band(x, 100, 3000), 0.22)


def pebbles():
    """鹿的蹄子拨了一下：几颗小石子滚下坡，叮当几下，越来越远、落进湿土里。"""
    sec = 1.6
    x = np.zeros(int(sec * SR))
    r = np.random.default_rng(61)
    add(x, 0.0, hoof(61, 0.55))
    at = 0.12
    a = 0.5
    for k in range(9):
        f = r.uniform(1900, 3400)
        add(x, at, modal([(f, 0.012, 1.0), (f * 1.47, 0.006, 0.4), (r.uniform(500, 800), 0.015, 0.4)], 0.06), a)
        at += r.uniform(0.06, 0.16) * (1 + k * 0.08)
        a *= 0.8
    return wet_forest(band(x, 80, 4500), 0.25)


# ================================================================== 剧本补充（第二批）
def elephant_voice(sec=4.2, seed=0):
    """大象的低鸣（不是真大象）：很低的一口长音，先往上挑再慢慢落下，像「呜——啊——呜」，
    元音（共振峰）跟着音量慢慢开合；没有粗糙的颤（不吓人），只有很慢的颤音。
    基频 58~92Hz，但力气在 2~6 次泛音（150~500Hz），手机喇叭也听得到。"""
    r = np.random.default_rng(seed)
    t = tt(sec)
    n = len(t)
    f0 = np.interp(t, [0, 0.5, 1.3, 2.4, 3.4, sec], [66, 78, 92, 88, 72, 58])
    f0 = lp(np.concatenate([np.full(SR, f0[0]), f0]), 3)[SR:]
    vib = 1 + 0.011 * np.sin(2 * np.pi * 4.2 * t) * np.clip((t - 0.8) / 0.8, 0, 1)
    vib *= 1 + 0.004 * unit(lp(r.standard_normal(n), 1.5))
    f0 = f0 * vib
    env = np.sin(np.pi / 2 * np.clip(t / 0.7, 0, 1)) ** 2 * np.clip((sec - t) / 1.4, 0, 1) ** 1.5
    env *= 1 + 0.12 * np.sin(np.pi * np.clip(t / sec, 0, 1))
    F1 = 320 + 200 * np.sin(np.pi * np.clip((t - 0.3) / (sec - 0.8), 0, 1)) ** 1.5
    F2 = 760 + 260 * np.sin(np.pi * np.clip((t - 0.3) / (sec - 0.8), 0, 1)) ** 1.5
    ph = 2 * np.pi * np.cumsum(f0) / SR
    x = np.zeros(n)
    for k in range(1, 32):
        fk = k * f0
        a = (1 / k ** 0.7) * (0.3 + np.exp(-0.5 * ((fk - F1) / 130) ** 2) + 0.55 * np.exp(-0.5 * ((fk - F2) / 210) ** 2))
        a *= np.clip(env, 1e-4, None) ** (0.06 * (k - 1))       # 越响越亮
        a *= fk < 2600
        x += a * np.sin(k * ph + r.uniform(0, 6.28))
    breath = band(r.standard_normal(n), 150, 1000)
    x = unit(x) + unit(breath) * 0.05
    return x * env


def elephant_call_1():
    """开场那次：森林深处一声低鸣，比较清楚，林子里回两下。"""
    sec = 6.0
    v = elephant_voice(4.2, seed=4)
    x = np.zeros(int(sec * SR))
    add(x, 0.15, v)
    x = band(x, 40, 1800)
    dry = x.copy()
    for d, g, c in ((0.42, 0.30, 1000), (0.95, 0.17, 700)):     # 林间回声
        add(x, d, lp(dry, c, 2), g)
    x = reverb(x, decay=2.8, wet=0.45, lo=60, hi=1200, pre=0.04, seed=31)
    t = tt(sec)
    return x * np.clip((sec - t) / 0.8, 0, 1)


def elephant_call_2():
    """坡地上那次：同一个声音，更远，被风盖住一半，回声沿山谷一节一节滚过去，越来越暗，没了。"""
    sec = 8.0
    v = elephant_voice(4.2, seed=4)
    x = np.zeros(int(sec * SR))
    add(x, 0.3, v)
    x = band(x, 40, 800)
    dry = x.copy()
    for d, g, c in ((0.5, 0.45, 700), (1.1, 0.36, 550), (1.8, 0.26, 420), (2.6, 0.16, 330)):
        add(x, d, lp(dry, c, 2), g)
    x = reverb(x, decay=3.5, wet=0.6, lo=60, hi=800, pre=0.05, seed=37)
    t = tt(sec)
    x = unit(x) * np.clip((sec - t) / 1.2, 0, 1)
    r = np.random.default_rng(38)
    gust = 0.55 + 0.45 * unit(lp(r.standard_normal(len(t)), 0.6))
    wind = unit(band(r.standard_normal(len(t)), 120, 1400)) * gust
    wind *= np.clip(t / 0.8, 0, 1) * np.clip((sec - t) / 1.5, 0, 1)
    return x + wind * 0.22


def tree_sway():
    """远处一排树冠依次被推了一下：一阵一阵的沙沙接力过去（先近后远，亮度先升后降）。约 3 秒。
    文件是单声道；「从一侧移到另一侧」要靠播放时的 pan（或者引擎里把 pan 补间过去）。"""
    sec = 3.4
    x = np.zeros(int(sec * SR))
    r = np.random.default_rng(71)
    for i in range(6):
        L = 1.3
        t = tt(L)
        u = i / 5
        cut = 1300 + 1000 * np.sin(np.pi * u)
        leaf = band(r.standard_normal(len(t)), 350, cut)
        flutter = 0.35 + unit(lp(np.abs(r.standard_normal(len(t))), 25)) ** 2
        g = unit(leaf * flutter) * np.sin(np.pi * t / L) ** 1.5 * (0.55 + 0.45 * np.sin(np.pi * (0.2 + 0.8 * u)))
        add(x, 0.05 + i * 0.38, g)
    x += unit(band(r.standard_normal(len(x)), 80, 500)) * 0.12 * np.sin(np.pi * np.clip(tt(sec) / sec, 0, 1))   # 一口风
    return wet_forest(band(x, 150, 2600), 0.3)


def alarm_beep(f, dur, amp, sag=1.0):
    t = tt(dur + 0.05)
    ff = f * (1 - (1 - sag) * np.clip(t / dur, 0, 1))
    ph = 2 * np.pi * np.cumsum(ff) / SR
    x = np.sin(ph) + 0.22 * np.sin(3 * ph) + 0.08 * np.sin(5 * ph)
    e = np.clip(t / 0.012, 0, 1) * np.clip((dur - t) / 0.03, 0, 1)
    return x * e * amp


def alarm_broken():
    """飞机里坏掉的警报（循环 4 秒）：闷在机舱里的「嘀—嘟」，一会儿正常，一会儿断一半、
    一会儿没电似的往下掉，中间有一点电流噼啪。首尾都是 0，接缝在安静处。"""
    sec = 4.0
    x = np.zeros(int(sec * SR))
    HI, LO = 740, 620
    add(x, 0.20, alarm_beep(HI, 0.18, 1.0))
    add(x, 0.42, alarm_beep(LO, 0.18, 1.0))
    add(x, 1.05, alarm_beep(HI, 0.18, 0.85))
    add(x, 1.27, alarm_beep(LO, 0.06, 0.85))              # 断了
    add(x, 1.33, burst(0.05, 0.01, 800, 3000) * 0.12)
    add(x, 1.36, burst(0.03, 0.006, 800, 3000) * 0.08)
    add(x, 2.15, alarm_beep(HI, 0.30, 0.45, sag=0.93))    # 没电似的往下掉
    add(x, 2.90, alarm_beep(HI, 0.11, 0.7))               # 匆匆又来一下
    add(x, 3.05, alarm_beep(LO, 0.11, 0.6))
    add(x, 3.17, burst(0.04, 0.008, 800, 3000) * 0.08)
    x = band(x, 250, 1500)                                # 隔着机壳
    x = wet_room(x, 0.15)
    x[: int(0.1 * SR)] *= np.linspace(0, 1, int(0.1 * SR)) ** 2
    x[-int(0.25 * SR):] *= np.linspace(1, 0, int(0.25 * SR)) ** 2
    x[0] = x[-1] = 0.0
    return x


def musicbox_pat():
    """在音乐盒的木盒底轻拍两下：手掌软软的「噗、噗」，里面一根簧片被震得很轻地响了一点。"""
    sec = 1.0
    x = np.zeros(int(sec * SR))
    for at, a in ((0.0, 1.0), (0.3, 0.8)):
        add(x, at, mix(modal([(190, 0.05, 0.6), (450, 0.03, 0.3), (900, 0.015, 0.1)], 0.4),
                       burst(0.08, 0.018, 60, 600) * 0.35), a)
    add(x, 0.31, mb_note(76, 0.035))
    return wet_room(band(x, 60, 3500), 0.15)


def pen_strokes(strokes, lo, hi, seed, body=0.25):
    r = np.random.default_rng(seed)
    n = int((max(s + d for s, d, _ in strokes) + 0.1) * SR)
    x = np.zeros(n)
    for s0, d, a in strokes:
        t = tt(d)
        grain = 0.3 + unit(lp(np.abs(r.standard_normal(len(t))), 180)) ** 2
        g = unit(band(r.standard_normal(len(t)), lo, hi)) * grain
        g += unit(band(r.standard_normal(len(t)), 200, 800)) * body
        add(x, s0, g * np.sin(np.pi * t / d) ** 0.6, a)
    return x


def pen_write():
    """在本子上写几个字：几笔很轻的沙沙。"""
    x = pen_strokes([(0.0, 0.12, 0.8), (0.15, 0.07, 0.6), (0.25, 0.16, 1.0), (0.45, 0.09, 0.7), (0.57, 0.15, 0.85)],
                    1300, 4000, 81)
    return wet_room(band(x, 300, 4500), 0.08)


def pen_strike():
    """用笔划掉一行：落笔一点、一道干脆的长划，越划越快、收笔。"""
    sec = 0.55
    t = tt(sec)
    x = np.zeros(len(t))
    add(x, 0.0, modal([(1900, 0.006, 0.2), (700, 0.01, 0.2)], 0.04))
    d = 0.38
    tl = tt(d)
    r = np.random.default_rng(83)
    grain = 0.4 + unit(lp(np.abs(r.standard_normal(len(tl))), 250)) ** 2
    s = lp_tv(band(r.standard_normal(len(tl)), 900, None), 2200 + 1600 * tl / d)
    g = unit(s) * grain * np.clip(tl / 0.03, 0, 1) * np.clip((d - tl) / 0.06, 0, 1)
    g += unit(band(r.standard_normal(len(tl)), 200, 700)) * 0.3 * np.clip((d - tl) / 0.06, 0, 1)
    add(x, 0.02, g)
    return wet_room(band(x, 300, 4500), 0.08)


def page_turn():
    """翻一页：纸被掀起来的一点脆响，一口带风的「呼」，落下去轻轻一拍。"""
    sec = 0.9
    t = tt(sec)
    r = np.random.default_rng(87)
    x = np.zeros(len(t))
    crink = np.zeros(int(0.35 * SR))
    for _ in range(40):
        p = r.integers(0, len(crink) - 400)
        L = int(r.integers(40, 300))
        crink[p:p + L] += r.standard_normal(L) * np.exp(-np.arange(L) / (L / 3)) * r.uniform(0.2, 1.0)
    crink = band(crink, 1500, 4200) * np.linspace(1, 0.3, len(crink))
    add(x, 0.0, unit(crink) * 0.5)
    air = unit(band(r.standard_normal(len(t)), 200, 1300)) * np.sin(np.pi * np.clip((t - 0.08) / 0.45, 0, 1)) ** 2
    x += air * 0.45
    add(x, 0.5, burst(0.1, 0.022, 150, 900) * 0.6)
    return wet_room(band(x, 120, 4500), 0.1)


def cup_set():
    """杯子放在木桌上：木头一声闷「嗒」，瓷杯底一点点亮。"""
    x = mix(modal([(160, 0.04, 0.6), (390, 0.03, 0.35), (820, 0.015, 0.15)], 0.5),
            modal([(2350, 0.06, 0.16), (3480, 0.035, 0.07)], 0.5),
            burst(0.02, 0.003, 300, 3000) * 0.25)
    return wet_room(band(x, 70, 4500), 0.14)


def sugar_drop():
    """一小块糖落进杯子：很小的「扑通」——一个往上挑的小水泡，一点点水花。"""
    sec = 0.6
    x = np.zeros(int(sec * SR))
    for at, f0, f1, a in ((0.0, 900, 1500, 1.0), (0.05, 1250, 1900, 0.4)):
        tb = tt(0.08)
        f = f0 + (f1 - f0) * np.clip(tb / 0.03, 0, 1)
        add(x, at, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tb / 0.016) * np.clip(tb / 0.001, 0, 1), a)
    add(x, 0.002, burst(0.04, 0.008, 1000, 4000) * 0.25)
    add(x, 0.0, modal([(2350, 0.03, 0.05)], 0.1))        # 杯子被碰了一下
    return wet_room(band(x, 300, 4500), 0.15)


def tool_tap():
    """工具柄敲木桌两下：「笃、笃」。"""
    x = np.zeros(int(0.65 * SR))
    for at, a in ((0.0, 1.0), (0.2, 0.85)):
        add(x, at, mix(modal([(260, 0.035, 0.6), (610, 0.025, 0.35), (1250, 0.012, 0.15)], 0.4),
                       burst(0.012, 0.0018, 800, 3500) * 0.25), a)
    return wet_room(band(x, 80, 4000), 0.15)


def paper_slide():
    """把明信片推到桌子对面：一道顺滑的纸擦木头的「嘶——」，停住时一点点轻碰。"""
    sec = 0.85
    t = tt(sec)
    r = np.random.default_rng(97)
    d = 0.6
    tl = tt(d)
    grain = 0.6 + 0.4 * unit(lp(np.abs(r.standard_normal(len(tl))), 60))
    g = unit(band(r.standard_normal(len(tl)), 500, 2600)) * grain
    g *= np.clip(tl / 0.08, 0, 1) * np.clip((d - tl) / 0.15, 0, 1) ** 1.2
    x = np.zeros(len(t))
    add(x, 0.02, g)
    add(x, 0.6, mix(modal([(700, 0.012, 0.25), (1500, 0.006, 0.1)], 0.05), burst(0.02, 0.004, 200, 1500) * 0.15))
    return wet_room(band(x, 200, 3500), 0.1)


# ================================================================== 剧本第四版（第三批）
def tap():
    """指尖轻敲一下木盒（剧本里一下一下地敲不唱的音乐盒）：比 musicbox_pat 小、硬一点，只是「嗒」。"""
    x = mix(modal([(330, 0.03, 0.5), (760, 0.02, 0.3), (1480, 0.008, 0.12)], 0.3),
            burst(0.01, 0.0015, 700, 3000) * 0.2)
    return wet_room(band(x, 100, 3800), 0.12)


def sugar():
    """一小块糖放进杯里：先碰一下瓷杯沿「叮」（小小的、短），再轻轻落进去。和 sugar_drop 的区别是这个主要是杯沿那一下。"""
    sec = 0.7
    x = np.zeros(int(sec * SR))
    add(x, 0.0, mix(modal([(2350, 0.11, 0.5), (3480, 0.06, 0.22), (5100, 0.025, 0.06)], 0.5),
                    burst(0.008, 0.0012, 1500, 4500) * 0.2))
    add(x, 0.09, modal([(2350, 0.05, 0.12)], 0.2))          # 在杯沿上又磕一下
    tb = tt(0.08)
    f = 800 + 500 * np.clip(tb / 0.03, 0, 1)
    add(x, 0.2, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tb / 0.014) * np.clip(tb / 0.001, 0, 1), 0.35)
    return wet_room(band(x, 300, 5000), 0.14)


def hum_note(m, dur, cents_fn=None, seed=0, cut_at=None):
    """闭着嘴的哼（合成，不是人声）：陡降的谐波 + 低的鼻腔共振（约 260Hz），1k 以上压掉，带一点气声。"""
    r = np.random.default_rng(seed)
    t = tt(dur)
    n = len(t)
    c = np.zeros(n) if cents_fn is None else cents_fn(t)
    f0 = mtof(m) * 2 ** (c / 1200) * (1 + 0.006 * np.sin(2 * np.pi * 5.0 * t) * np.clip((t - 0.15) / 0.2, 0, 1))
    ph = 2 * np.pi * np.cumsum(f0) / SR
    x = np.zeros(n)
    for k in range(1, 12):
        fk = k * f0
        a = (1 / k ** 1.8) * (0.4 + 1.2 * np.exp(-0.5 * ((fk - 260) / 90) ** 2)) * (1 / (1 + (fk / 900) ** 4))
        x += a * np.sin(k * ph + k)
    breath = unit(band(r.standard_normal(n), 300, 2200)) * 0.07
    e = np.sin(np.pi / 2 * np.clip(t / 0.07, 0, 1)) ** 2
    if cut_at is None:
        e *= np.clip((dur - t) / 0.12, 0, 1)
    else:   # 哼到一半断掉：很快收掉，只剩一点气
        e *= np.clip((cut_at - t) / 0.035, 0, 1)
        breath = breath * (1 + 2.5 * np.exp(-((t - cut_at - 0.05) / 0.06) ** 2))
    return unit(x) * e + breath * np.maximum(e, np.exp(-np.clip(t - (cut_at or dur), 0, None) / 0.08) * (t > (cut_at or dur) - 0.05) * 0.8)


def chen_hum():
    """晨跟着音乐盒哼两个音：旋律开头的 E→D（低八度，E4→D4）。第一个音还算准；第二个一出来就偏高
    （约 +60 音分、还往上飘），哼了一下自己听出不对，断掉，剩一口气。很轻。"""
    sec = 1.5
    x = np.zeros(int(sec * SR))
    add(x, 0.05, hum_note(64, 0.6, lambda t: -8 + 6 * np.clip(t / 0.15, 0, 1), seed=1))
    add(x, 0.66, hum_note(62, 0.6, lambda t: 55 + 30 * np.clip(t / 0.3, 0, 1) - 20 * np.clip((t - 0.15) / 0.2, 0, 1), seed=2,
                          cut_at=0.36), 0.7)          # 没把握的音：轻一点
    return wet_room(band(x, 120, 2500), 0.12)


def twig_clicks(sec, count, seed, lo=900, hi=2600):
    r = np.random.default_rng(seed)
    x = np.zeros(int(sec * SR))
    for _ in range(count):
        f = r.uniform(lo, hi)
        add(x, r.uniform(0, sec - 0.08), modal([(f, r.uniform(0.006, 0.015), 1.0), (f * 0.52, 0.02, 0.6)], 0.06), r.uniform(0.15, 0.5))
    return x


def branch_shift():
    """抱着一捆树枝换手：一阵木棍互相磕碰的咔啦、一点干叶子沙沙。"""
    sec = 0.8
    t = tt(sec)
    e = np.sin(np.pi * np.clip(t / 0.6, 0, 1)) ** 0.8
    x = twig_clicks(sec, 14, 101) * np.clip(1.2 * e, 0, 1)
    x += unit(drag_grains(sec, 220, 500, 2600, 102)) * 0.18 * e
    add(x, 0.12, modal([(240, 0.04, 0.3), (520, 0.025, 0.15)], 0.2))     # 整捆在怀里一沉
    return wet_forest(band(x, 100, 3500), 0.2)


def branch_drop():
    """把最上面那根树枝放到地上：一头先着地「嗒」，另一头再落下、在湿地上弹一下，带点小枝的碰响。"""
    sec = 0.9
    x = np.zeros(int(sec * SR))
    for at, a in ((0.0, 0.8), (0.12, 1.0), (0.24, 0.35)):
        add(x, at, mix(modal([(300, 0.04, 0.6), (690, 0.025, 0.3), (1300, 0.01, 0.1)], 0.3),
                       burst(0.05, 0.01, 80, 900) * 0.4), a)
    add(x, 0.13, twig_clicks(0.3, 5, 103) * 0.6)
    add(x, 0.13, unit(drag_grains(0.25, 200, 400, 2000, 104)) * 0.1)
    return wet_forest(band(x, 60, 3500), 0.22)


def plank_drop():
    """木板搭上塌陷口：厚木板落下一声闷「咚」，下面是空的所以有一点空腔的回响，再「嗒」地一下放稳。"""
    sec = 1.6
    x = np.zeros(int(sec * SR))
    hit = mix(modal([(118, 0.12, 0.7), (265, 0.08, 0.4), (520, 0.04, 0.2), (980, 0.015, 0.06)], 0.8),
              tone(70, 0.4, 0.08, 0.5), burst(0.08, 0.015, 60, 1200) * 0.4)
    add(x, 0.0, hit)
    add(x, 0.22, hit, 0.35)                                  # 另一头落稳
    D = int(0.007 * SR)                                      # 和 water_hollow 一样的空腔（143Hz）
    y = x.copy()
    for k in range(1, 8):
        y[k * D:] += (0.5 ** k) * x[:-k * D] * 0.8
    y = reverb(band(y, 50, 2500), decay=1.2, wet=0.3, lo=80, hi=1000, pre=0.025, seed=41)
    return wet_forest(y, 0.15)


def sap_drip():
    """松脂慢慢滴进罐子：几滴很稠的、慢慢拉断的「嗒…」，打在罐底，罐子轻轻地亮一下；一滴比一滴快一点。"""
    sec = 2.8
    x = np.zeros(int(sec * SR))
    at = 0.15
    r = np.random.default_rng(109)
    for k in range(5):
        tb = tt(0.12)
        f = r.uniform(380, 460) * (1 + 0.5 * np.clip(tb / 0.05, 0, 1))      # 比水滴低、慢、钝
        d = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tb / 0.03) * np.clip(tb / 0.004, 0, 1)
        d = mix(d, modal([(1650, 0.08, 0.12), (2900, 0.04, 0.05)], 0.3), burst(0.03, 0.008, 150, 900) * 0.25)
        add(x, at, d, 0.8 + 0.05 * k)
        at += 0.62 - 0.06 * k
    return wet_room(band(x, 120, 4000), 0.14)


def clock_open():
    """撬开旧闹钟的后盖：卡扣「咔」一下松开，盖子刮着边被掀起，里面的铃和弹簧被震得很轻地「叮」了一下。"""
    sec = 1.0
    x = np.zeros(int(sec * SR))
    add(x, 0.0, mix(modal([(1700, 0.008, 0.5), (2900, 0.004, 0.2), (650, 0.015, 0.3)], 0.06),
                    burst(0.008, 0.0012, 1000, 4500) * 0.25))
    tl = tt(0.18)
    sc = unit(band(noise(len(tl)), 1200, 3500)) * (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(70 + 0 * tl) / SR) ** 4)
    add(x, 0.07, sc * np.sin(np.pi * tl / 0.18) * 0.3)
    add(x, 0.28, modal([(420, 0.04, 0.35), (980, 0.02, 0.15)], 0.2))      # 盖子放下
    add(x, 0.3, modal([(2640, 0.35, 0.06), (3960, 0.2, 0.025)], 0.7))     # 铃很轻地一声
    add(x, 0.3, modal([(820, 0.15, 0.05), (1230, 0.1, 0.03)], 0.5))       # 弹簧嗡一下
    return wet_room(band(x, 150, 5000), 0.12)


def radio_static():
    """旧收音机：短短一段沙沙，忽大忽小，偶尔噼啪；底下若有若无飘过一点远处电台的残音（说不清是人声还是音乐）。"""
    sec = 2.0
    t = tt(sec)
    n = len(t)
    r = np.random.default_rng(113)
    sw = 0.65 + 0.35 * unit(lp(r.standard_normal(n), 2.5))
    st = unit(band(r.standard_normal(n), 350, 2800, order=4)) * sw
    cr = np.zeros(n)
    for p in r.integers(0, n, 30):
        cr[p] = r.uniform(-1, 1)
    st += unit(band(cr, 500, 3000)) * 0.35
    # 残音：很远的一点和弦 + 按音节一开一合的「人声」共振，忽隐忽现
    fade = np.clip(0.5 + 0.8 * np.sin(2 * np.pi * 0.7 * t + 1.0), 0, 1) ** 2
    chord = sum(np.sin(2 * np.pi * mtof(m) * t * (1 + 0.003 * np.sin(2 * np.pi * 0.4 * t))) for m in (57, 64, 69))
    syl = (0.5 + 0.5 * np.sin(2 * np.pi * 3.7 * t)) ** 2
    voice = peak_eq(band(r.standard_normal(n), 400, 1800), 700, 8, 1.5) * syl
    ghost = band(unit(chord) * 0.6 + unit(voice) * 0.5, 450, 1800) * fade
    x = st * 0.75 + ghost * 0.22
    x *= np.clip(t / 0.04, 0, 1) * np.clip((sec - t) / 0.25, 0, 1)
    return wet_room(x, 0.08)


def fire_flare():
    """炉子里加了一块树脂：「呼」地亮一下（噪声一下变亮再落回去），几下油脂的噼啪，底下一口暖的低音。"""
    sec = 2.0
    t = tt(sec)
    n = len(t)
    w = noise(n)
    cut = 250 + 1500 * np.exp(-((t - 0.3) / 0.22) ** 2) * (t > 0.08) + 500 * np.clip((t - 0.08) / 0.15, 0, 1) * np.exp(-np.clip(t - 0.5, 0, None) / 0.5)
    roar = lp_tv(lp_tv(band(w, 60, None), cut), cut)
    roar = unit(roar) * np.clip((t - 0.06) / 0.12, 0, 1) * (0.35 + 0.65 * np.exp(-np.clip(t - 0.35, 0, None) / 0.45)) * np.clip((sec - t) / 0.5, 0, 1)
    cr = np.zeros(n)
    r = np.random.default_rng(127)
    for _ in range(18):
        p = int(r.uniform(0.15, 1.6) * SR)
        L = int(r.integers(80, 400))
        cr[p:p + L] += r.standard_normal(L) * np.exp(-np.arange(L) / (L / 4)) * r.uniform(0.2, 0.8)
    cr = band(cr, 300, 3000)
    body = unit(band(noise(n), 40, 180)) * 0.5 * np.exp(-((t - 0.35) / 0.35) ** 2)
    x = roar * 0.75 + unit(cr) * 0.35 + body
    return wet_room(band(x, 40, 3200), 0.12)


# ================================================================== 主程序
JOBS = [
    ("metal_clank", metal_clank, 0.55),
    ("musicbox_stuck", lambda: musicbox(False), 0.45),
    ("engine_try", engine_try, 0.55),
    ("engine_fail", engine_fail, 0.6),
    ("branch_drag", branch_drag, 0.45),
    ("log_push", log_push, 0.65),
    ("deer_knock", deer_knock, 0.55),
    ("water_hollow", water_hollow, 0.55),
    ("rattle", rattle, 0.4),
    ("screw_dish", screw_dish, 0.32),
    ("kettle_whistle", kettle_whistle, 0.3),
    ("sigh", sigh, 0.28),
    ("pipe_clear", pipe_clear, 0.5),
    ("pipe_dull", pipe_dull, 0.5),
    ("pipe_hiss", pipe_hiss, 0.35),
    ("wrench", wrench, 0.42),
    ("engine_test", engine_test, 0.6),
    ("small_click", small_click, 0.3),
    ("gramophone_stuck", gramophone_stuck, 0.45),
    ("scrape", scrape, 0.28),
    ("musicbox_full", lambda: musicbox(True), 0.45),
    ("box_close", box_close, 0.42),
    ("deer_steps", deer_steps, 0.5),
    ("knock", knock, 0.6),
    ("door_touch", door_touch, 0.35),
    ("pebbles", pebbles, 0.4),
    ("gramophone_full", lambda: gramophone_full(False), 0.5),
    ("gramophone_quiet", lambda: gramophone_full(True), 0.24),
    ("engine_start", engine_start, 0.8),
    # 第二批（剧本补充）：加在最后，前面 29 个的随机数顺序不变，重跑结果一样
    ("elephant_call_1", elephant_call_1, 0.7),
    ("elephant_call_2", elephant_call_2, 0.5),
    ("tree_sway", tree_sway, 0.4),
    ("alarm_broken", alarm_broken, 0.3),
    ("musicbox_pat", musicbox_pat, 0.4),
    ("pen_write", pen_write, 0.18),
    ("pen_strike", pen_strike, 0.24),
    ("page_turn", page_turn, 0.3),
    ("cup_set", cup_set, 0.42),
    ("sugar_drop", sugar_drop, 0.28),
    ("tool_tap", tool_tap, 0.42),
    ("paper_slide", paper_slide, 0.24),
    # 第三批（剧本第四版）
    ("tap", tap, 0.32),
    ("sugar", sugar, 0.26),
    ("chen_hum", chen_hum, 0.24),
    ("branch_shift", branch_shift, 0.38),
    ("branch_drop", branch_drop, 0.45),
    ("plank_drop", plank_drop, 0.65),
    ("sap_drip", sap_drip, 0.32),
    ("clock_open", clock_open, 0.32),
    ("radio_static", radio_static, 0.22),
    ("fire_flare", fire_flare, 0.5),
]
LOOPS = {"deer_knock", "water_hollow", "alarm_broken"}


def report():
    print(f"\n{'name':18s} {'sec':>6s} {'peak':>6s} {'rms':>6s} {'centroid':>9s} {'<-30dB':>7s}")
    for name, x, loop in STATS:
        sp = np.abs(np.fft.rfft(x))
        fr = np.fft.rfftfreq(len(x), 1 / SR)
        cen = (sp * fr).sum() / (sp.sum() or 1)
        # 从峰值往后，包络最后一次高于 -30dB 的时间（余音长短）
        envl = np.sqrt(np.convolve(x ** 2, np.ones(441) / 441, "same"))
        ip = int(np.argmax(envl))
        above = np.where(envl[ip:] > envl[ip] * 10 ** (-30 / 20))[0]
        dec = (above[-1] if len(above) else 0) / SR
        print(f"{name:18s} {len(x) / SR:6.2f} {np.max(np.abs(x)):6.3f} {np.sqrt((x ** 2).mean()):6.3f} {cen:8.0f}Hz {dec:6.2f}s")
    print("\n循环接缝：")
    for name, x, loop in STATS:
        if not loop:
            continue
        d = np.abs(np.diff(x))
        seam = abs(x[0] - x[-1])
        q = int(0.5 * SR)
        print(f"  {name}: 首样本 {x[0]:+.5f} 尾样本 {x[-1]:+.5f} 接缝跳变 {seam:.5f}"
              f"（样本间跳变 中位 {np.median(d):.5f} / 99% {np.percentile(d, 99):.5f}）"
              f" 首 0.5s RMS {np.sqrt((x[:q] ** 2).mean()):.4f} 尾 0.5s RMS {np.sqrt((x[-q:] ** 2).mean()):.4f}")


def main():
    for name, fn, pk in JOBS:
        save(name, fn(), pk, loop=name in LOOPS)
    report()


if __name__ == "__main__":
    main()
