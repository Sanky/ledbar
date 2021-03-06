#!/usr/bin/python
# vim:et:sw=4:ts=4:sts=4

import pyaudio
import struct
import math
import numpy as np
import time
import sys
import getopt
from datetime import datetime

import ledbar

CHUNK_SIZE = 256
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

PIXELS = 20
LAZY = 0
SYMMETRIC = 0

HISTORY_SIZE = 8
MIN_FREQ = 30
MAX_FREQ = 12000


def print_usage():
    print '''\
USAGE:
    %s [-l] [-n number] [-s] [-h]
OPTIONS:
    -l              lazy mode
    -n number       number of controlled boxes
    -s              symmetric mode
    -h --help       show this help
''' % sys.argv[0]

try:
    opts, args = getopt.getopt(sys.argv[1:], 'n:lsh', ['help'])
except getopt.GetOptError:
    print_usage()
    sys.exit(1)
if len(args):
    print_usage()
    sys.exit(1)
for k, v in opts:
    if k == '-n':
        if not v.isdigit():
            print_usage()
            sys.exit(1)
        PIXELS = int(v)
    elif k == '-l':
        LAZY = 1
    elif k == '-s':
        SYMMETRIC = 1
    elif k == '-h' or k == '--help':
        print_usage()
        sys.exit(0)

if LAZY == 1:
    HISTORY_SIZE = 12
if SYMMETRIC == 1:
    EPIXELS = PIXELS / 2
else:
    EPIXELS = PIXELS
# EPIXELS: Effective pixels (for spectrum display)

SAMPLE_SIZE = CHUNK_SIZE*HISTORY_SIZE
FREQ_STEP = float(RATE) / (CHUNK_SIZE * HISTORY_SIZE)
PIXEL_FREQ_RANGE = math.pow(float(MAX_FREQ) / MIN_FREQ, 1.0/EPIXELS)


p = pyaudio.PyAudio()

stream = p.open(format = FORMAT,
                channels = CHANNELS,
                rate = RATE,
                input = True,
                frames_per_buffer = CHUNK_SIZE)

def get_color(volume):
    vol_thres = 200
    if volume <= vol_thres: return (0, 0, 0)
    p = 1-25/(volume-vol_thres)
    if p <= 0: return (0, 0, 0)
    if p >= 1: return (1.0, 1.0, 1.0)
    # Monochromatic mode:
    #p = p * p * p * p * p * p * p
    #return (p, p, 0) # or any other combination
    if LAZY == 1:
        p *= p
    else:
        p *= p * p
    if p <= 0.4: return (0, 0, p*2.5)
    elif p <= 0.7: return (0, (p-0.4)*3.33, 1.0-(p-0.4)*3.33)
    elif p <= 0.9: return ((p-0.7)*5.0, 1.0-(p-0.7)*5.0, 0.0)
    else: return (1.0, (p-0.9)*10.0, (p-0.9)*10.0)

l = ledbar.Ledbar(PIXELS)
history = []

history_diminish = np.array([[((i+1.0) / HISTORY_SIZE)**2] * CHUNK_SIZE for i in xrange(HISTORY_SIZE)])
window = np.array([0.5*(1-math.cos(2*math.pi*i/(SAMPLE_SIZE-1))) for i in xrange(SAMPLE_SIZE)])
work = True

nexttrig = 0

try:
    while work:
        try: data = stream.read(CHUNK_SIZE)
        except IOError: continue
        nowtrig = datetime.now().microsecond / 50000
        if (nowtrig == nexttrig):
            continue
        else:
            nexttrig = nowtrig
        if len(data) == 0: break
        indata = np.array(struct.unpack('%dh'%CHUNK_SIZE,data))
        history.append(indata)
        if len(history) > HISTORY_SIZE: history.pop(0)
        elif len(history) < HISTORY_SIZE: continue
        fft = np.fft.rfft(np.concatenate(history*history_diminish)*window)
        freq_limit = MIN_FREQ
        freq = 0
        i = 0
        while freq < freq_limit:
            i += 1
            freq += FREQ_STEP
        freq_limit *= PIXEL_FREQ_RANGE
        freq_steps = 1
        pixel = 0
        count = 0
        volumes = []
        while pixel < EPIXELS:
            total = 0.0
            while freq < freq_limit:
                total += abs(fft[i])**2
                i += 1; count += 1
                freq += FREQ_STEP
            volume = (total/count)**0.5
            volumes.append(volume/SAMPLE_SIZE*freq_steps)
            freq_limit *= PIXEL_FREQ_RANGE
            freq_steps += 1
            pixel += 1
            count = 0
        for pixel in xrange(EPIXELS):
            c = get_color(volumes[pixel])
            if SYMMETRIC == 1:
                l.set_pixel(PIXELS / 2 + pixel, c[0],  c[1], c[2])
                l.set_pixel(PIXELS / 2 - (pixel + 1), c[0],  c[1], c[2])
            else:
                l.set_pixel(pixel, c[0],  c[1], c[2])
        work = l.update()
        # time.sleep(0.05)
finally:
    stream.close()
    p.terminate()
