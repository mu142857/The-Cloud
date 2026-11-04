"""森林夜里的环境音（11-04 作者：「白噪音声音为什么这么大……这个难听的白噪音删了」→ 换成好听的森林背景音）。
合成（不是录音，没有授权问题），60 秒无缝循环：
  - 松林里的风：棕红噪声在频域里整形（150~1100 Hz 一个软鼓包，2 kHz 以上很快压下去，没有刺耳的沙沙），
    整段噪声就是周期的（频域生成、逆 FFT），首尾天然接得上；音量跟着一条慢慢起伏的「阵风」包络（几个周期整除 60 秒的正弦叠加）。
    再叠一层很轻的「松针」高一点的风声（1.2~3 kHz），只在阵风大的时候出来一点。
  - 蟋蟀：三只，不同音高（4.3 / 4.7 / 5.1 kHz）、不同左右；每只叫一阵（一串 3~4 下的短颤音）停一阵，远、轻。
  - 猫头鹰：远处「呼——呼呼」，60 秒里两次（约 17 秒、44 秒），380 Hz 往下滑一点，带一点远处的回声尾巴。
  左右声道略有不同（风的两路噪声相关但不相同），听起来宽一点。
用法：python3 tools/forest_night_ambient.py 输出.wav [频谱图.png]
"""
import sys, math
import numpy as np
import scipy.io.wavfile as wavfile

SR = 44100
SEC = 60
N = SR * SEC
rng = np.random.default_rng(20261104)


def shaped_noise(shape_fn, seed):
    """频域整形的周期噪声：长度正好 N，首尾无缝"""
    r = np.random.default_rng(seed)
    f = np.fft.rfftfreq(N, 1.0 / SR)
    mag = shape_fn(f)
    ph = r.uniform(0, 2 * np.pi, f.size)
    spec = mag * np.exp(1j * ph)
    spec[0] = 0
    x = np.fft.irfft(spec, N)
    return x / (np.max(np.abs(x)) + 1e-12)


def wind_shape(f):
    f = np.maximum(f, 1.0)
    body = 1.0 / np.sqrt(f)                                      # 粉红一点
    hump = np.exp(-((np.log(f) - np.log(420.0)) / 0.9) ** 2)     # 150~1100 Hz 的软鼓包
    low_cut = 1.0 / (1.0 + (60.0 / f) ** 4)                      # 太低的轰轰声去掉
    high_cut = 1.0 / (1.0 + (f / 1800.0) ** 6)                   # 2 kHz 以上很快压下去
    return body * (0.35 + hump) * low_cut * high_cut


def needle_shape(f):
    f = np.maximum(f, 1.0)
    return np.exp(-((np.log(f) - np.log(2000.0)) / 0.35) ** 2) / (1.0 + (f / 3200.0) ** 8)


def periodic_env(periods_sec, amps, phases):
    """周期整除 SEC 的正弦叠加：一条首尾接得上的慢包络"""
    t = np.arange(N) / SR
    e = np.zeros(N)
    for p, a, ph in zip(periods_sec, amps, phases):
        e += a * np.sin(2 * np.pi * t / p + ph)
    return e


def add_wrap(out, sig, start):
    """把一段声音加进循环里，超出末尾的绕回开头"""
    n = sig.shape[0]
    idx = (np.arange(n) + start) % N
    np.add.at(out, idx, sig)


# ---------------------------------------------------------------- 风
gust = periodic_env([60, 30, 20, 12, 7.5], [0.45, 0.3, 0.2, 0.12, 0.06], rng.uniform(0, 2 * np.pi, 5))
gust = 0.55 + 0.45 * np.tanh(gust * 1.6)                          # 0.1 ~ 1.0，大部分时候中间
wind_l = shaped_noise(wind_shape, 1) * 0.8 + shaped_noise(wind_shape, 3) * 0.2
wind_r = shaped_noise(wind_shape, 2) * 0.8 + shaped_noise(wind_shape, 3) * 0.2
needle_l = shaped_noise(needle_shape, 11)
needle_r = shaped_noise(needle_shape, 12)
needle_env = np.clip((gust - 0.55) / 0.45, 0, 1) ** 2             # 只有阵风大的时候松针才响一点
L = wind_l * gust * 0.55 + needle_l * needle_env * 0.10
R = wind_r * gust * 0.55 + needle_r * needle_env * 0.10

# ---------------------------------------------------------------- 蟋蟀
def chirp(freq, pulses, rate=28.0, pulse_ms=14.0):
    n = int(SR * pulses / rate) + int(SR * 0.03)
    t = np.arange(n) / SR
    s = np.zeros(n)
    pl = pulse_ms / 1000.0
    for k in range(pulses):
        t0 = k / rate
        m = (t >= t0) & (t < t0 + pl)
        u = (t[m] - t0) / pl
        env = np.sin(np.pi * u) ** 2
        s[m] += env * np.sin(2 * np.pi * freq * t[m] * (1.0 + 0.004 * np.sin(2 * np.pi * 9 * t[m])))
    return s


crickets_l = np.zeros(N)
crickets_r = np.zeros(N)
for ci, (fq, pan, level) in enumerate([(4300.0, -0.6, 0.040), (4700.0, 0.5, 0.032), (5100.0, 0.1, 0.022)]):
    r = np.random.default_rng(100 + ci)
    t = r.uniform(0, 3)
    while t < SEC:
        # 叫一阵：每 0.5~0.7 秒一下，持续 4~9 秒；停 3~8 秒
        bout = r.uniform(4, 9)
        gap = r.uniform(0.5, 0.7)
        tt = t
        while tt < t + bout:
            c = chirp(fq * r.uniform(0.995, 1.005), int(r.integers(3, 5))) * level * r.uniform(0.75, 1.0)
            st = int(tt * SR)
            add_wrap(crickets_l, c * (1 - pan) / 2 * 1.4, st)
            add_wrap(crickets_r, c * (1 + pan) / 2 * 1.4, st)
            tt += gap * r.uniform(0.9, 1.1)
        t += bout + r.uniform(4, 10)

# 远一点：蟋蟀稍微糊一点（简单的两点平均，去掉最尖的那一点）
def soften(x):
    return 0.5 * x + 0.5 * np.roll(x, 1)


crickets_l = soften(crickets_l)
crickets_r = soften(crickets_r)

# ---------------------------------------------------------------- 猫头鹰
def hoot(dur, f0, f1):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = f0 + (f1 - f0) * (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    att = np.clip(t / 0.06, 0, 1)
    tone = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.05 * np.sin(3 * ph)
    return tone * env * att


def owl_call():
    parts = [(0.0, hoot(0.42, 395, 372)), (0.70, hoot(0.22, 388, 370)), (0.98, hoot(0.5, 392, 360))]
    n = int(SR * 2.4)
    s = np.zeros(n)
    for t0, h in parts:
        st = int(t0 * SR)
        s[st:st + h.size] += h
    # 远处的回声：几下衰减的延迟
    out = s.copy()
    for d, a in [(0.09, 0.35), (0.21, 0.2), (0.37, 0.12), (0.6, 0.06)]:
        k = int(d * SR)
        out[k:] += a * s[:n - k]
    # 远：去掉高频（一阶低通）
    y = np.zeros_like(out)
    alpha = 0.18
    for i in range(1, n):
        y[i] = y[i - 1] + alpha * (out[i] - y[i - 1])
    return y / (np.max(np.abs(y)) + 1e-9)


owl = owl_call()
for t0, pan, lv in [(17.0, -0.35, 0.34), (44.5, 0.4, 0.28)]:
    st = int(t0 * SR)
    add_wrap(L, owl * lv * (1 - pan) / 2 * 1.4, st)
    add_wrap(R, owl * lv * (1 + pan) / 2 * 1.4, st)

L = L + crickets_l
R = R + crickets_r

# ---------------------------------------------------------------- 电平：RMS 约 -24 dBFS，峰值留余量
st = np.stack([L, R], axis=1)
rms = np.sqrt(np.mean(st ** 2))
st *= (10 ** (-24 / 20)) / rms
peak = np.max(np.abs(st))
if peak > 0.6:
    st *= 0.6 / peak
pcm = (st * 32767).astype(np.int16)
wavfile.write(sys.argv[1], SR, pcm)
print("saved %s  %.1fs  rms=%.1f dBFS  peak=%.2f" % (sys.argv[1], N / SR, 20 * math.log10(np.sqrt(np.mean((pcm / 32768.0) ** 2))), np.max(np.abs(pcm)) / 32768))

if len(sys.argv) > 2:
    import scipy.signal as sg
    from PIL import Image
    mono = pcm.astype(float).mean(1) / 32768
    f, t, S = sg.spectrogram(mono, SR, nperseg=2048, noverlap=1024)
    S = 10 * np.log10(S + 1e-14)
    keep = f <= 8000
    S = S[keep][::-1]
    lo, hi = np.percentile(S, 5), np.max(S)
    img = np.clip((S - lo) / (hi - lo), 0, 1)
    im = Image.fromarray((img ** 0.8 * 255).astype(np.uint8)).resize((1200, 400))
    # 下面加一条波形包络
    env = np.abs(mono).reshape(-1, N // 1200)[:1200].max(1)
    wav = Image.new("L", (1200, 100), 0)
    px = wav.load()
    for x in range(1200):
        h = int(min(1.0, env[x] / 0.6) * 99)
        for y in range(99 - h, 100):
            px[x, y] = 200
    out = Image.new("L", (1200, 500), 0)
    out.paste(im, (0, 0))
    out.paste(wav, (0, 400))
    out.save(sys.argv[2])
