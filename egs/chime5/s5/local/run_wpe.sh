#!/bin/bash

. ./cmd.sh
. ./path.sh

# Config:
cmd=run.pl
nt=8
nj=1

. utils/parse_options.sh || exit 1;

if [ $# != 2 ]; then
   echo "Wrong #arguments ($#, expected 2)"
   echo "Usage: local/run_wpe.sh [options] <wav-in-dir> <wav-out-dir>"
   echo "  --cmd <cmd>        # Command to run in parallel with"
   echo "  --nt <num-threads> # number of threads for processing one wav file"
   echo "  --nj <num-jobs>    # number of jobs splitted into parallel"
   exit 1;
fi

sdir=$1
odir=$2
array=$3
expdir=exp/wpe/`echo $odir | awk -F '/' '{print $NF}'`

# check if miniconda3 is installed
miniconda_dir=$HOME/miniconda3/
if [ ! -d $miniconda_dir ]; then
    echo "$miniconda_dir does not exist. Please run '../../../tools/extras/install_miniconda.sh' and '../../../tools/extras/install_wpe.sh';"
    exit 1
fi

# check if WPE is installed
result=`$HOME/miniconda3/bin/python -c "\
try:
    import nara_wpe
    print('1')
except ImportError:
    print('0')"`
if [ "$result" == "1" ]; then
    echo "WPE is installed"
else
    echo "WPE is not installed. Please run ../../../tools/extras/install_wpe.sh"
    exit 1
fi

# Set bash to 'debug' mode, it will exit on :
# -e 'error', -u 'undefined variable', -o ... 'error in pipeline', -x 'print commands',
set -e
set -u
set -o pipefail

mkdir -p $odir
mkdir -p $expdir/log


# wavfiles.list can be used as the name of the output files
output_wavfiles=$expdir/wavfiles.list
# select all the array data
find -L ${sdir} | grep -i u0 | awk -F "/" '{print $NF}' | sed -e "s/\.CH.\.wav//" | sort | uniq > $expdir/wavfiles.list


# split the list for parallel processing
# maximum number of jobs is the number of WAV files
nj_max=`wc -l $expdir/wavfiles.list | awk '{print $1}'`
[[ $nj -gt $nj_max ]] && nj=$nj_max

split_wavfiles=""
for n in `seq $nj`; do
  split_wavfiles="$split_wavfiles $output_wavfiles.$n"
done
utils/split_scp.pl $output_wavfiles $split_wavfiles || exit 1;

echo -e "applying WPE\n"
# making a shell script for each job
for n in `seq $nj`; do
cat << EOF > $expdir/log/wpe.$n.sh
while read line; do
  $HOME/miniconda3/bin/python local/apply_nara_wpe.py -n $nt $sdir/\$line.CH{}.wav $odir/\$line.CH{}.wav 4
done < $output_wavfiles.$n
EOF
done

chmod a+x $expdir/log/wpe.*.sh
$cmd --num-threads $nt JOB=1:$nj $expdir/log/wpe.JOB.log \
  $expdir/log/wpe.JOB.sh

echo "`basename $0` Done."
