import os
import pathlib
import re
import json
from datetime import datetime
import subprocess as subp
import time

DEBUG = False
LINE_CLEAR = '\x1b[2K'
FOLDER_PATH = os.path.dirname(__file__)
DB_FILE_NAME = "db.json"
ROOT_FOLDER = 'D:/Movies/'
BLACKLISTED_FOLDERS = [
    "Flightplan",
    "Subtitles",
    "Featurettes",
    "Optimized for Mobile",
]

global movie_db
movie_db = {"list": [], "ignore": {"folders": BLACKLISTED_FOLDERS }}

def numberToTime(_t: int | float) -> str:
    return datetime.fromtimestamp(_t).strftime("%H:%M:%S")

def numberToDateTime(_t: int | float) -> str:
    return datetime.fromtimestamp(_t).strftime("%d/%m/%Y at %H:%M:%S")

def getDuration(_input: dict = {}) -> str:
    copy_stream = _input.copy()
    global formatted_time
    formatted_time = ""
    # print('\nSearching for duration...\n%s' % json.dumps(_input, indent=2))
    if "duration" in copy_stream:
        _temp = int(float(copy_stream["duration"]))
        return {'error': False, 'result': numberToTime(_temp)}

    elif "duration_ts" in copy_stream:
        _temp = int(copy_stream["duration_ts"]) / 1000
        return {'error': False, 'result': numberToTime(_temp)}

    elif "tags" in copy_stream:
        for _i, key in enumerate(copy_stream["tags"]):
            if str(key).lower().startswith("duration"):
                return {'error': False, 'result': copy_stream["tags"][key][0:8]}
    return {'error': True, 'result': ''}

def clearJSON(_json) -> dict:
    return json.loads(json.dumps(str(_json)))

def executeCMDShell(_cmd: list, debug=False, json_output=True) -> dict:
    _process = subp.run(
        args=_cmd,
        shell=True,
        capture_output=True,
        text=True,
        universal_newlines=True,
        timeout=40.0,
    )
    _output = clearJSON(_process.stdout) if json_output else _process.stdout
    _error = clearJSON(_process.stderr)
    if debug:
        print(
            "Command: %s\nResult: %s\nError: %s"
            % (" ".join(_cmd), _process.stdout, _process.stderr)
        )
    if _output:
        return _output
    else:
        return _error

def getRegexFromList(_list: list = []) -> str:
    _str = ""
    for _i, _v in enumerate(_list):
        _str = "".join([_str, "(", _v, ")", ("|" if _i < len(_list) - 1 else "")])
    return "".join(["(", _str, ")"])

regex = getRegexFromList(["mp4", "mkv", "avi", "webm"])

def splitPath(path:pathlib.Path)->list:
    return os.path.normpath(path).replace('\\','/').split('/')

def getParentFolder(path):
    return os.path.dirname(path).split('\\')[-1]


def debugJSON(name:str,data:dict={}):
    path = os.path.join('debug',name)
    with open(path,'w') as f:
        f.write( json.dumps(data, indent=2) )

def getMovieInfo(path:pathlib.Path)->dict:
    global movie_data
    global movie_duration
    movie_data = {
        'name': '',
        'ext': '',
        'size': '',
        'parent': '',
        'date': '',
        'audio': [],
        'subtitles': [],
        'video': {
            'h': 0,
            'w': 0,
            't': -1,
        },
        'error': False,
        'output': {}
    }
    
    movie_duration = { 'error': True, 'result': ''}

    ffmpeg_cmd = [
        "ffprobe",
        "-hide_banner",
        "-show_streams",
        "-print_format",
        "json",
        "-i"
    ]
    ffmpeg_cmd.append(path)
    cmd_output = executeCMDShell(ffmpeg_cmd)

    movie_data["name"] = os.path.basename(movie)[:-4]
    movie_data["ext"] = os.path.splitext(movie)[1][1:]
    movie_data["size"] = os.path.getsize(movie)
    movie_data["date"] = numberToDateTime( os.path.getmtime(movie) )
    movie_data["parent"] = getParentFolder(movie)

    ffmpeg_json = json.loads(cmd_output)

    if 'streams' in ffmpeg_json:
        if DEBUG:
            print('Streams: %d' % len(ffmpeg_json['streams']))
            debugJSON('streams.json',ffmpeg_json)
            
            for stream in ffmpeg_json['streams']:
                print(json.dumps(stream))

        for stream in ffmpeg_json['streams']:
            if 'codec_type' in stream:
                codec_type = stream['codec_type']
                del(stream['disposition'])
                
                if movie_duration['error']:
                    movie_duration = getDuration(stream)
                    movie_data['video']['t'] = movie_duration['result']

                if codec_type == 'audio':
                    if 'tags' in stream:
                        if 'language' in stream['tags']:
                            lang = stream['tags']['language'][0:2]
                            if not lang in movie_data['audio']:
                                if len(lang):
                                    movie_data['audio'].append(lang)
                        if DEBUG:
                            debugJSON('audio.json',stream)

                elif codec_type == 'video':
                    if 'profile' in stream:
                        if stream['codec_name'] in ['hevc','h264','mpeg4']:
                            # if stream['profile'] in ['High','Main','Main 10','Advanced Simple Profile']:
                            if movie_data['video']['h'] == 0:
                                movie_data['video']['h'] = stream['height']
                            if movie_data['video']['w'] == 0:
                                movie_data['video']['w'] = stream['width']
                        if DEBUG:
                            debugJSON('video.json',stream)

                elif codec_type == 'subtitle':
                    if 'tags' in stream:
                        if 'language' in stream['tags']:
                            lang_sub = stream['tags']['language'][0:2]

                            if not lang_sub in movie_data['subtitles']:
                                if len(lang_sub):
                                    movie_data['subtitles'].append(lang_sub)
                            if DEBUG:
                                debugJSON('subtitle.json',stream)


    movie_data['error'] = False if 'streams' in ffmpeg_json else True
    movie_data['output'] = {} if 'streams' in ffmpeg_json else cmd_output

    if DEBUG:
        debugJSON('data.json',movie_data)

    return movie_data

if __name__ == '__main__':
    files = [ file for file in pathlib.Path(ROOT_FOLDER).rglob("*") if not splitPath(file)[-2] in BLACKLISTED_FOLDERS and re.search(regex, str(file)) ]
    
    for index, movie in enumerate(files):
        file_name = os.path.basename(movie)[:-4]
        file_ext = os.path.splitext(movie)[1][1:]
        parentFolder = getParentFolder(movie)

        if not parentFolder in BLACKLISTED_FOLDERS:
        # if not parentFolder in BLACKLISTED_FOLDERS and file_name == 'The Menu':
            movie_data = getMovieInfo(movie)
            movie_data['index'] = index

            print('',end=LINE_CLEAR)
            print( '[%d/%d] Analysing %s ...' % ( index+1, len(files), file_name ), end='\r' )

            # movie_db['list'].append( json.loads(movie_data))
            movie_db['list'].append( movie_data )
            # if DEBUG:
            #     time.sleep(5)
    print()
        
    movie_db['list'].sort(key=lambda v: v['size'], reverse=True)

    with open(DB_FILE_NAME,'w') as file:
        file.write( json.dumps(movie_db,indent= 2) )

    print( 'Length: %d' % len(files))