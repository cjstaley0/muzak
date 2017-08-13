from bs4 import BeautifulSoup
import tweepy
from random import randint
import json
import video_runner
import os
from subprocess import call
import mimetypes
import urllib
import argparse
import logging
import friend_runner
from ffmpy import FFmpeg
import time
import glob
import traceback
import sys
from collections import OrderedDict
    
def connect():
    #Keep the "Consumer Secret" a secret. This key should never be human-readable in your application
    consumer_key = 'ZBXZillMnWl3ONqvOavIlmznw'
    consumer_secret = 'Yac9alcZMhau3ECpYNkQYhd1U7Qv8QAb4nJoTerrNyyfpWoDqj'
    access_token = '772160982424522752-Mfc3ym3z4WorL48ikxzLBFkLE29unsF'
    access_token_secret = 'h5DneSmTNOcbzgfkXg7wlJlP2XArwFrC5Zdhc7Cj1deoB'
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)
    return api
    
def video_upload(api, filename, *args, **kwargs):
    """ :reference https://dev.twitter.com/rest/reference/post/media/upload-chunked
        :allowed_param:
    """
    f = kwargs.pop('file', None)
    
    #@staticmethod
    def chunk_video(api, command, filename, max_size, form_field="media", chunk_size=1048576, f=None, media_id=None, segment_index=0):
        fp = None
        if command == 'init':
            if f is None:
                file_size = os.path.getsize(filename)
                try:
                    if file_size > (max_size * 1024):
                        raise TweepError('File is too big, must be less than %skb.' % max_size)
                except os.error as e:
                    raise TweepError('Unable to access file: %s' % e.strerror)

                # build the mulitpart-formdata body
                fp = open(filename, 'rb')
            else:
                f.seek(0, 2)  # Seek to end of file
                file_size = f.tell()
                if file_size > (max_size * 1024):
                    raise TweepError('File is too big, must be less than %skb.' % max_size)
                f.seek(0)  # Reset to beginning of file
                fp = f
        elif command != 'finalize':
            if f is not None:
                fp = f
            else:
                raise TweepError('File input for APPEND is mandatory.')

        # video must be mp4
        file_type = mimetypes.guess_type(filename)
        if file_type is None:
            raise TweepError('Could not determine file type')
        file_type = file_type[0]
        if file_type not in ['video/mp4']:
            raise TweepError('Invalid file type for video: %s' % file_type)

        BOUNDARY = b'Tw3ePy'
        body = list()
        if command == 'init':
            body.append(
                urllib.parse.urlencode({
                    'command': 'INIT',
                    'media_type': file_type,
                    'total_bytes': file_size
                }).encode('utf-8')
            )
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'
            }
        elif command == 'append':
            if media_id is None:
                raise TweepError('Media ID is required for APPEND command.')
            body.append(b'--' + BOUNDARY)
            body.append('Content-Disposition: form-data; name="command"'.encode('utf-8'))
            body.append(b'')
            body.append(b'APPEND')
            body.append(b'--' + BOUNDARY)
            body.append('Content-Disposition: form-data; name="media_id"'.encode('utf-8'))
            body.append(b'')
            body.append(str(media_id).encode('utf-8'))
            body.append(b'--' + BOUNDARY)
            body.append('Content-Disposition: form-data; name="segment_index"'.encode('utf-8'))
            body.append(b'')
            body.append(str(segment_index).encode('utf-8'))
            body.append(b'--' + BOUNDARY)
            body.append('Content-Disposition: form-data; name="{0}"; filename="{1}"'.format(form_field, os.path.basename(filename)).encode('utf-8'))
            body.append('Content-Type: {0}'.format(file_type).encode('utf-8'))
            body.append(b'')
            body.append(fp.read(chunk_size))
            body.append(b'--' + BOUNDARY + b'--')
            headers = {
                'Content-Type': 'multipart/form-data; boundary=Tw3ePy'
            }
        elif command == 'finalize':
            if media_id is None:
                raise TweepError('Media ID is required for FINALIZE command.')
            body.append(
                urllib.parse.urlencode({
                    'command': 'FINALIZE',
                    'media_id': media_id
                }).encode('utf-8')
            )
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'
            }
        body = b'\r\n'.join(body)
        # build headers
        headers['Content-Length'] = str(len(body))

        return headers, body, fp 
    
    # Initialize upload (Twitter cannot handle videos > 15 MB)
    headers, post_data, fp = chunk_video(api, 'init', filename, 15360, form_field='media', f=f)
    kwargs.update({ 'headers': headers, 'post_data': post_data })

    # Send the INIT request
    media_info = tweepy.binder.bind_api(
        api=api,
        path='/media/upload.json',
        method='POST',
        payload_type='media',
        allowed_param=[],
        require_auth=True,
        upload_api=True
    )(*args, **kwargs)

    # If a media ID has been generated, we can send the file
    if media_info.media_id:
        chunk_size = kwargs.pop('chunk_size', 1048576)
        fsize = os.path.getsize(filename)
        nloops = int(fsize / chunk_size) + (1 if fsize % chunk_size > 0 else 0)
        for i in range(nloops):
            headers, post_data, fp = chunk_video(api, 'append', filename, 15360, chunk_size=chunk_size, f=fp, media_id=media_info.media_id, segment_index=i)
            kwargs.update({ 'headers': headers, 'post_data': post_data, 'parser': tweepy.parsers.RawParser() })
            # The APPEND command returns an empty response body
            tweepy.binder.bind_api(
                api=api,
                path='/media/upload.json',
                method='POST',
                payload_type='media',
                allowed_param=[],
                require_auth=True,
                upload_api=True
            )(*args, **kwargs)
        # When all chunks have been sent, we can finalize.
        headers, post_data, fp = chunk_video(api, 'finalize', filename, 15360, media_id=media_info.media_id)
        kwargs.update({ 'headers': headers, 'post_data': post_data })
        # The FINALIZE command returns media information
        return tweepy.binder.bind_api(
            api=api,
            path='/media/upload.json',
            method='POST',
            payload_type='media',
            allowed_param=[],
            require_auth=True,
            upload_api=True
        )(*args, **kwargs)
    else:
        return media_info

def mix(audio, video, api):
    logging.info('audio is ' + audio[0])
    logging.info('video is ' + video[0])
    try:
        os.remove('result.mp4')
    except Exception:
        logging.warn('Cannot remove result file')
    ff = FFmpeg(
        inputs = OrderedDict([(audio[0], '-ss ' + str(audio[1])), (video[0], '-ss ' + str(video[1]))]),
        outputs = {'result.mp4': '-map 0:a -map 1:v -c copy -t 8'}
    )
    logging.warn(ff.cmd)
    ff.run()
    
    result = 'result' + time.strftime('%H%M%S') + '.mp4'
    ff2 = FFmpeg(
        inputs = {'result.mp4': '-ss 1'},
        outputs = {result: '-c copy -t 6'}
    )
    logging.info(ff2.cmd)
    ff2.run()
    file = open(result, 'rb')
    upload = video_upload(api, filename=result, file=file)
    media_id = [str(json.loads(upload)['media_id_string'])]
    api.update_status(media_ids=media_id, status=audio[2] + ' ' + video[2])
    logging.info('uploaded ' + result + ' with tags: ' + audio[2] + ' ' + video[2])
    file.close()
    mp4 = glob.glob('*.mp4')
    logging.info('found files: ' + ','.join(mp4))
    for m in mp4:
        try:
            os.remove(m)
        except Exception:
            pass
    logging.warn('Finished at ' + time.strftime('%H:%M'))
        
def pick_type(usage):
    choose = randint(0,7)
    a_map = {0: 'friends', 1: 'friends', 2: 'friends', 3: 'popular', 4: 'text', 5: 'text', 6: 'hashtag', 7: 'hashtag'}
    v_map = {0: 'friends', 1: 'popular', 2: 'popular', 3: 'popular', 4: 'text', 5: 'text', 6: 'hashtag', 7: 'hashtag'}
    choice = a_map[choose]
    if usage == 'video':
        choice = v_map[choose]
    return choice

def get_video(api, friend_list, retries):
    try:
        logging.warn('AUDIO:')
        audio = friend_runner.get_video_url(api, pick_type('audio'), friend_list)
        logging.warn('*******************')
        logging.warn('VIDEO:')
        video = friend_runner.get_video_url(api, pick_type('video'), friend_list)
        mix(audio, video, api)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.warn('Mixing failed with exception ' + str(exc_value) + '.\n' + str(exc_traceback) + '\nTrying again.')
        if retries > 0:
            get_video(api, friend_list, retries -1)

def main():
    logging.basicConfig(filename='bot.log', level=logging.WARN)
    logging.warn('------------------------------------------------------')
    logging.warn('Started at ' + time.strftime('%H:%M'))
    api = connect()
    friends = api.followers_ids()
    retweeted = api.retweets_of_me(count=10)
    retweeters = list(map(lambda x: x.user.id, retweeted))
    friend_list = 783558672660123648
    list_members = []
    for member in tweepy.Cursor(api.list_members, list_id=friend_list).items():
        list_members.append(member.id)
    for friend in friends:
        if friend not in list_members:
            try:
                api.add_list_member(list_id=friend_list, user_id=friend)
                logging.warn('Added friend ' + str(friend) + ' to friend list.')
            except Exception as e:
                logging.warn('Could not add friend ' + str(friend) + ' to friend list: ' + str(e))
                pass
    for retweeter in retweeters:
        if retweeter not in list_members:
            try:
                api.add_list_member(list_id=friend_list, user_id=retweeter)
                logging.warn('Added retweeter ' + str(retweeter) + ' to friend list.')
            except Exception as e:
                logging.warn('Could not add retweeter ' + str(retweeter) + ' to friend list: ' + str(e))
                pass
    logging.warn('Friend list has ' + str(api.get_list(list_id=friend_list).member_count) + ' friends.')
    get_video(api, friend_list, 3)
    
if __name__ == '__main__':
    main()