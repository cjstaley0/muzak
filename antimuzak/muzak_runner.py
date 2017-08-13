import logging
import re
from random import randint
import sys
import pprint
import urllib3
from bs4 import BeautifulSoup
from subprocess import call
import time
import tweepy

def get_start(clip_len):
    return randint(1, clip_len - 13)

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
    search = '/playlist?list='
    response = http.request('GET', url + search + query)
    result = response.data
    soup = BeautifulSoup(result, 'html.parser')
    videos = soup.find_all('tr')
    video = list(filter(lambda x: x.find('span', {'class' : 'yt-thumb-default'}), videos))
    tag_list = soup.find('meta', property='og:description')['content'] 
    tags = tag_list.split(' ')
    return video, tags
    
def youtube_search(api, query):
    url = 'https://www.youtube.com'
    videos, tags = get_vid_list(query, url)
    selected_vid = videos[randint(0, len(videos) - 1)]
    input = 'input' + time.strftime('%H%M%S') + '.mp4'
    link = url + selected_vid.a.get('href')
    logging.warn('Selected ' + link + ', saving as ' + input)
    call('youtube-dl -f mp4 -o ' + input + ' ' + link, shell=True)
    time_string = selected_vid.find('div', {'class': 'timestamp'}).span.string
    split = time_string.split(':')
    clip_seconds = int(split[-1]) + 60 * int(split[-2])
    if len(split) == 3:
        clip_seconds += 3600 * int(split[0])
    logging.info('Time is ' + str(clip_seconds))
    return(input, get_start(clip_seconds), tags) 
    
def get_video_url(api, method):
    logging.warn('trying type ' + method)
    if method == 'audio':
        search = 'PLTlDM89-3cIDnsPmcX5w47mFyqBZCqT4O'
    else:
        search = 'PLTlDM89-3cID2-SBRaE4UuBd5PAMRcgJt'
    return youtube_search(api, search)
        