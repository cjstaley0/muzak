import os
from glob import glob
from subprocess import call
from random import randint

audio_dir = r'C:\Users\chris\Dropbox\antimuzak\shows'
video_dir = r'C:\Users\chris\Desktop\record videos'
audio_files = glob(audio_dir + '\*.mp3')
video_files = glob(video_dir + '\*.mp4')
for file in audio_files:
   print('processing file')
   video_file = video_files[randint(0, len(video_files) - 1)]
   call(r'ffmpeg -i "' + video_file + '" -i "' + file + r'" -map 1:a -map 0:v -c copy -shortest "' + file.split(".")[0] + r'.mp4"', shell=True)