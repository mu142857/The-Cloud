"""河流章的流水声（替换 audio/sfx/river_flow.wav，room.json 的 ambient 名字不变）。
11-04 作者嫌森林的白噪音难听；原来的 river_flow（tools/river_sfx.py 的 _river）也是一直铺到 8 kHz 的宽频噪声，一起换掉。
合成，12 秒无缝循环，单声道：
  - 水的底子：频域整形的周期噪声（250~900 Hz 一个软鼓包，1.8 kHz 以上很快压掉），首尾天然接得上；
    音量跟着一条慢慢起伏的包络（周期整除 12 秒）。
  - 水泡的咕嘟声：一颗颗短的、音高往上滑的衰减正弦（气泡共振 500~1600 Hz，20~45 毫秒），每秒 7~10 颗，很轻，
    绕回开头的那几颗加在开头（循环不断）。
用法：python3 tools/river_flow_soft.py 输出.wav [频谱图.png]
"""
import sys, math
import numpy as np
import scipy.io.wavfile as wavfile

SR = 44100
SEC = 12
N = SR * SEC
rng = np.random.default_rng(1104)


def shaped_noise(shape_fn, seed):
    r = np.random.default_rng(seed)
    f = np.fft.rfftfreq(N, 1.0 / SR)
    spec = shape_fn(f) * np.exp(1j * r.uniform(0, 2 * np.pi, f.size))
    spec[0] = 0
    x = np.fft.irfft(spec, N)
    return x / (np.max(np.abs(x)) + 1e-12)


def body_shape(f):
    f = np.maximum(f, 1.0)
    hump = np.exp(-((np.log(f) - np.log(480.0)) / 0.7) ** 2)
    low_cut = 1.0 / (1.0 + (90.0 / f) ** 4)
    high_cut = 1.0 / (1.0 + (f / 1500.0) ** 6)
    return (0.25 / np.sqrt(f / 100.0) + hump) * low_cut * high_cut


t = np.arange(N) / SR
env = 0.8 + 0.12 * np.sin(2 * np.pi * t / 12 + 0.7) + 0.08 * np.sin(2 * np.pi * t / 4 + 2.1)
x = shaped_noise(body_shape, 5) * env * 0.6

# 水泡：f(t) = f0 * (1 + 上滑)，指数衰减
def bubble(f0, dur):
    n = int(SR * dur)
    tt = np.arange(n) / SR
    f = f0 * (1.0 + 0.9 * tt / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    a = np.exp(-tt / (dur * 0.35)) * np.clip(tt / 0.002, 0, 1)
    return np.sin(ph) * a


bub = np.zeros(N)
tt = 0.0
while tt < SEC:
    f0 = rng.uniform(500, 1600)
    b = bubble(f0, rng.uniform(0.02, 0.045)) * rng.uniform(0.04, 0.11) * (900.0 / f0) ** 0.5
    st = int(tt * SR)
    idx = (np.arange(b.size) + st) % N
    np.add.at(bub, idx, b)
    tt += rng.exponential(1.0 / 8.5)
x = x + bub

rms = np.sqrt(np.mean(x ** 2))
x *= (10 ** (-21 / 20)) / rms
if np.max(np.abs(x)) > 0.7:
    x *= 0.7 / np.max(np.abs(x))
pcm = (x * 32767).astype(np.int16)
wavfile.write(sys.argv[1], SR, pcm)
print("saved %s %.1fs rms=%.1f dBFS peak=%.2f" % (sys.argv[1], N / SR, 20 * math.log10(np.sqrt(np.mean((pcm / 32768.0) ** 2))), np.max(np.abs(pcm)) / 32768))

if len(sys.argv) > 2:
    import scipy.signal as sg
    from PIL import Image
    f, tm, S = sg.spectrogram(pcm / 32768.0, SR, nperseg=2048, noverlap=1024)
    S = 10 * np.log10(S + 1e-14)[f <= 8000][::-1]
    img = np.clip((S + 110) / 70, 0, 1)
    Image.fromarray((img * 255).astype(np.uint8)).resize((600, 200)).save(sys.argv[2])
