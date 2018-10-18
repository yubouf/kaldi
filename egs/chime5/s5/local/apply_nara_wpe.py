#!/usr/bin/env python

from __future__ import print_function
import sys
import argparse
import numpy as np
from nara_wpe import wpe
from nara_wpe.utils import stft, istft
import soundfile as sf
from multiprocessing.pool import Pool
from functools import partial


def execute_wpe_block(input_files, output_files,
                      num_process=1,
                      block_size=30,
                      sampling_rate=16000,
                      delay=3,
                      iterations=5,
                      taps=10,
                      size=512,
                      shift=128,
                      window_length=None,
                      fading=True,
                      pad=True,
                      symmetric_window=False):
    """
    This function processes WPE block-wize.
      arguments:
        input_files: input wav filepaths [in/ch1.wav, in/ch2.wav, ...]
        output_files: output wav filepaths [out/ch1.wav, out/ch2.wav, ...]
      options:
        num_process: number of concurrent processes
        block_size: block size in seconds
      other options:
        for nara_wpe.utils.stft and nara_wpe.wpe
    """
    # parallel process funciton for each frequency bin
    wpe_one_freq = partial(wpe.wpe_v8,
                           iterations=iterations,
                           statistics_mode='full')
    pool = Pool(num_process)

    # load input files as shape (ch, sample)
    y = np.stack((sf.read(infile)[0] for infile in input_files), axis=0)
    # output buffer
    z = np.zeros_like(y)

    # number of samples in a block
    block_samples = block_size * sampling_rate
    start_sample = 0
    # first block
    block_y = y[:, 0:block_samples]
    # iteration for block
    while block_y.shape[1] > 0:
        print("processing {:.2f}%".format(100 * start_sample / y.shape[1]),
              file=sys.stderr, flush=True)
        # stft.shape is (ch, t, f) -> Y.shape is (f, ch, t)
        Y = stft(block_y, size=size, shift=shift, window_length=window_length,
                 fading=fading, pad=pad,
                 symmetric_window=symmetric_window).transpose(2, 0, 1)
        wpe_outs = pool.map(wpe_one_freq, (x for x in Y))
        # wpe_out.shape is (f, ch, t) -> Z.shape is (ch, t, f)
        Z = np.stack(wpe_outs, axis=0).transpose(1, 2, 0)
        # z.shape is (ch, sample)
        block_z = istft(Z, size=size, shift=shift)
        z[:, start_sample:start_sample + block_z.shape[1]] = block_z
        # set next block
        start_sample += block_samples
        block_y = y[:, start_sample:start_sample + block_samples]
    # save output files
    for i, outfile in enumerate(output_files):
        sf.write(outfile, z[i], sampling_rate)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Execute WPE')
    parser.add_argument('infile_template',
                        help='input file template, "{}" indicates the channel index')
    parser.add_argument('outfile_template',
                        help='output file template, "{}" indicates the channel index')
    parser.add_argument('num_channel', type=int,
                        help='number of channels')
    parser.add_argument('-n', '--num_process', type=int, default=1,
                        help='number of concurrent processes')
    args = parser.parse_args()
    input_files = [args.infile_template.format(c + 1) for c in range(args.num_channel)]
    output_files = [args.outfile_template.format(c + 1) for c in range(args.num_channel)]
    execute_wpe_block(input_files, output_files, num_process=args.num_process)
