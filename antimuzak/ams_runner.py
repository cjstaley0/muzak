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
import muzak_runner
from ffmpy import FFmpeg
import time
import glob
import traceback
import sys
from collections import OrderedDict
    
def connect():
    #Keep the "Consumer Secret" a secret. This key should never be human-readable in your application
    consumer_key = 'xxx'
    consumer_secret = 'xxx'
    access_token = 'xxx-xxx'
    access_token_secret = 'xxx'
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
    length = str(randint(0, 13) * 0.25 + 3)
    ff = FFmpeg(
        inputs = OrderedDict([(audio[0], '-ss ' + str(audio[1])), (video[0], '-ss ' + str(video[1]))]),
        outputs = {'result.mp4': '-map 0:a -map 1:v -c copy -t 8'}
    )
    logging.warn(ff.cmd)
    ff.run()
    
    result = 'result' + time.strftime('%H%M%S') + '.mp4'
    ff2 = FFmpeg(
        inputs = {'result.mp4': '-ss 1'},
        outputs = {result: '-c copy -t ' + length}
    )
    logging.info(ff2.cmd)
    ff2.run()
    file = open(result, 'rb')
    upload = video_upload(api, filename=result, file=file)
    media_id = [str(json.loads(upload)['media_id_string'])]
    tags = list(filter(lambda x: x, audio[2] + video[2]))
    tag = tags[randint(0, len(tags) - 1)]
    api.update_status(media_ids=media_id, status=tag)
    logging.info('uploaded ' + result)
    file.close()
    mp4 = glob.glob('*.mp4')
    logging.info('found files: ' + ','.join(mp4))
    for m in mp4:
        try:
            os.remove(m)
        except Exception:
            pass
    logging.warn('Finished at ' + time.strftime('%H:%M'))

def get_video(api, retries):
    try:
        logging.warn('AUDIO:')
        audio = muzak_runner.get_video_url(api, 'audio')
        logging.warn('*******************')
        logging.warn('VIDEO:')
        video = muzak_runner.get_video_url(api, 'video')
        mix(audio, video, api)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.warn('Mixing failed with exception ' + str(exc_value) + '.\n' + str(exc_traceback) + '\nTrying again.')
        if retries > 0:
            get_video(api, retries -1)

def main():
    logging.basicConfig(filename='ams.log', level=logging.WARN)
    logging.warn('------------------------------------------------------')
    logging.warn('Started at ' + time.strftime('%H:%M'))
    api = connect()
    get_video(api, 3)

if __name__ == '__main__':
    main()