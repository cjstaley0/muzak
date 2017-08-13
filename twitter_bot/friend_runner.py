import logging
import re
from random import randint
from subprocess import call
import time

import urllib3
from bs4 import BeautifulSoup
import tweepy


def make_friends(api): # Dead :( :(
   followers = api.followers_ids()
   rt_list = list(map(lambda x: x.id_str, api.retweets_of_me()))
   retweets = set([])
   for tweet in rt_list:
       retweets |= set(map(lambda x: x.user.id_str, api.retweets(tweet)))
   friends = api.friends_ids()
   to_follow = set(followers) | retweets - set(friends)
   for id in to_follow:
       api.create_friendship(id)
       logging.info('Added ' + api.get_user(id).screen_name)
       
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
    
def get_vid_list(query, url, type):
    http = urllib3.PoolManager()
    search = '/results?search_query='
    if type == 'playlist':
        search = '/playlist?list='
    response = http.request('GET', url + search + query)
    result = response.data
    soup = BeautifulSoup(result, 'html.parser')
    videos = soup.find_all('tr')
    if type == 'search':
        links = soup.find_all('a')
        videos = list(filter(lambda x: x.get('href')[:6] == '/watch', links))
        videos = list(filter(lambda x: x.find('span', {'class' : 'video-time'}), videos))
        videos = list(filter(lambda x: inTimeLimit(x.find('span', {'class' : 'video-time'}).string), videos))
    if type == 'playlist':
        videos = list(filter(lambda x: x.find('span', {'class' : 'yt-thumb-default'}), videos))
    return videos
    
def youtube_search(api, query, friend_list, type):
    url = 'https://www.youtube.com'
    logging.warn('searching youtube for ' + query)
    adjusted_query = query
    if type == 'search':
        adjusted_query = '"' + query.replace(' ', '+') + '"'
    videos = get_vid_list(adjusted_query, url, type)
    if len(videos) == 0:
        logging.warn('trying vid w/o quotes.')
        videos = get_vid_list(adjusted_query.replace('"', ''), url, type)
        if len(videos) == 0:
            logging.warn('failed to find youtube video, rerunning')
            return get_video_url(api, 'text', friend_list, type)
    selected_vid = videos[randint(0, len(videos) - 1)]
    input = 'input' + time.strftime('%H%M%S') + '.mp4'
    link = ""
    if type == 'search':
        link = url +  selected_vid.get('href')
    if type == 'playlist':
        link = url +  selected_vid.a.get('href')
    logging.warn('Selected ' + link + ', saving as ' + input)
    call('youtube-dl -f mp4 -o ' + input + ' ' + link, shell=True)
    time_string = ''
    if type == 'search':
        time_string = selected_vid.find('span', {'class': 'video-time'}).string
    if type == 'playlist':
        time_string = selected_vid.find('div', {'class': 'timestamp'}).span.string
    split = time_string.split(':')
    clip_seconds = int(split[-1]) + 60 * int(split[-2])
    if len(split) == 3:
        clip_seconds += 3600 * int(split[0])
    logging.info('Time is ' + str(clip_seconds))
    tag = query
    if type == 'playlist':
        tag = '#AntiMuzakSerum'
    return(input, get_start(clip_seconds), tag) 
    
def find_video_in_tweets(api, tweets, friend_list):
    logging.warn('checking ' + str(len(tweets)) + ' tweets')
    tweets_with_ees = list(filter(lambda x: hasattr(x, 'extended_entities'), tweets))
    logging.info('found ' + str(len(tweets_with_ees)) + ' tweets with ees')
    tweets_with_video = list(filter(lambda x: x.extended_entities['media'][0]['type'] == 'video'
                             and x.extended_entities['media'][0]['video_info']['duration_millis'] > 14000
                             and x.possibly_sensitive == False, tweets_with_ees))
    logging.warn('found ' + str(len(tweets_with_video)) + ' tweets with videos')
    if len(tweets_with_video) > 0:
        video = tweets_with_video[randint(0, len(tweets_with_video) -1)]
        variants = video.extended_entities['media'][0]['video_info']['variants']
        video_url = max(variants, key=lambda x: x.get('bitrate', 0))['url']
        video_len = int(video.extended_entities['media'][0]['video_info']['duration_millis'] / 1000)
        video_tags =  ' '.join(re.findall('#\w+', video.text))
        logging.warn('found video of len ' + str(video_len) + ' in tweet: ' + video_url)
        logging.warn('tags are ' + ' ' + video_tags)
        return (video_url, get_start(video_len), video_tags)
    else:
        logging.warn('Failed to find video, rerunning.')
        return get_video_url(api, 'popular', friend_list)
        
def hashtag_search(api, hashtag, friend_list):
    hash_tweets = []
    filtered_tag = hashtag + ' filter:native_video'
    for tweet in tweepy.Cursor(api.search, q=filtered_tag, count=200).items(600): 
        hash_tweets.append(tweet)
    return find_video_in_tweets(api, hash_tweets, friend_list)
    
def get_video_url(api, method, friend_list):
    logging.warn('trying type ' + method)
    if method != 'popular' and method != 'anti':
        friend_tweets = []
        for tweet in tweepy.Cursor(api.list_timeline, list_id=friend_list, count=200).items(600):
            friend_tweets.append(tweet)
        if method != 'friends':
            text = ' '.join(list(map(lambda x: x.text, friend_tweets)))
            if method == 'hashtag': #hashtag
                hashtags = list(set(re.findall('#\w+', text)))
                logging.info('|'.join(hashtags))
                try:
                    hashtag = hashtags[randint(0, len(hashtags) - 1)]
                except Exception:
                    logging.warn('Failed to find hashtag, rerunning.')
                    return get_video_url(api, 'popular', friend_list)
                logging.warn('Selected tag: ' + hashtag)
                return hashtag_search(api, hashtag, friend_list)
            else: # method == text
                tokens = re.findall(' (\w{4,})[\., ]', text)
                logging.info('|'.join(tokens))
                if len(tokens) < 10:
                    return get_video_url(api, 'text', friend_list)
                idx = randint(0, len(tokens) - 3)
                search_term = ' '.join(tokens[idx:idx + 3]).strip()
                return youtube_search(api, search_term, friend_list, 'search')
        else: # method == friends
            return find_video_in_tweets(api, friend_tweets, friend_list)
    elif method == 'popular': # method == popular
        usa_id = 23424977
        trends = api.trends_place(usa_id)[0]['trends']
        logging.info('Trending topics: ' + '|'.join(list(map(lambda x: x['name'], trends))))
        selected_trend = trends[randint(0, len(trends) - 1)]['name']
        logging.warn('Selected trend: ' + selected_trend)
        if selected_trend[0] == '#':
            return hashtag_search(api, selected_trend, friend_list)
        else:
            return youtube_search(api, selected_trend, friend_list, 'search')
    else: # method == anti
        search = 'PLejolwMSd8F-RbxPOKmoAYrDPwfEchcLU'
        return youtube_search(api, search, friend_list, 'playlist')
        