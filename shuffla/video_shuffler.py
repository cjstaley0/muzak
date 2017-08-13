import urllib3
from ffmpy import FFmpeg
from bs4 import BeautifulSoup
from random import randint
import time
from subprocess import call
import sys
from collections import OrderedDict

#def mix(audio1, audio2, video1, video2):
def mix():
    crush = 'acrusher=mode=lin:bits=5:samples=5'
    
    audio_options = {
        'crush': ''
    }
    try:
        os.remove('result.mp4')
    except Exception:
        print('cant remove')
    print('mixing')
    ff = FFmpeg(
        inputs = OrderedDict([('input070806.mp4', '-ss 10'), ('input071016.mp4', '-ss 10')]),
        outputs = {'result.mp4': ['-filter_complex', "[0:a]adelay=1000[x];[1:v]null[y]", '-map', "[x]", '-map', "[y]", '-t', '12']}
    )
    print(ff.cmd)
    ff.run()
    print('ran')
    result = 'result' + time.strftime('%H%M%S') + '.mp4'
    ff2 = FFmpeg(
        inputs = {'result.mp4': '-ss 1'},
        outputs = {result: '-c copy -t 10'}
    )
    print(ff2.cmd)
    ff2.run()
    
def inTimeLimit(time):
    splits = time.split(':')
    if len(splits)!= 2:
        return False
    if int(splits[0]) > 5:
        return False
    if int(splits[0]) == 0 and int(splits[1]) < 15:
        return False
    return True
    
def get_vid_list(query, url):
    http = urllib3.PoolManager()
    response = http.request('GET', url + '/results?search_query=' + query)
    result = response.data
    soup = BeautifulSoup(result, 'html.parser')
    links = soup.find_all('a')
    videos = list(filter(lambda x: x.get('href')[:6] == '/watch', links))
    videos = list(filter(lambda x: x.find('span', {'class' : 'video-time'}), videos))
    videos = list(filter(lambda x: inTimeLimit(x.find('span', {'class' : 'video-time'}).string), videos))
    return videos
    
def youtube_search(query):
    url = 'https://www.youtube.com'
    videos = get_vid_list(query, url)
    if len(videos) == 0:
        quit()
    else:
        print('getting vids')
        selected_vid = videos[randint(0, len(videos) - 1)]
        input = 'input' + time.strftime('%H%M%S') + '.mp4'
        print(input)
        call('youtube-dl -f mp4 ' + url + selected_vid.get('href') + ' -o ' + input, shell=True)
        time_string = selected_vid.find('span', {'class': 'video-time'}).string
        split = time_string.split(':')
        clip_seconds = int(split[-1]) + 60 * int(split[-2])
        if len(split) == 3:
            clip_seconds += 3600 * int(split[0])
        print('Time is ' + str(clip_seconds))
        return(input, randint(1, clip_seconds - 13))

def main():
    mix()
    search = 'bugs'
    #a1 = youtube_search(search)
    #a2 = youtube_search(search)
    #v1 = youtube_search(search)
    #v2 = youtube_search(search)
    #mix(a1, a2, v1, v2)
    
if __name__ == '__main__':
    main()