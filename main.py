import os
import pathlib
import re
import json
from datetime import datetime
import subprocess as subp

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
    _d = _input.copy()
    global _ftime
    _ftime = ""
    if "duration" in _d:
        _temp = int(float(_d["duration"]))
        _ftime = numberToTime(_temp)
        # print("# %s"%_ftime)
    elif "duration_ts" in _d:
        _temp = int(_d["duration_ts"]) / 1000
        _ftime = numberToTime(_temp)
    if "tags" in _d and len(_ftime) < 1:
        # _d = _d["tags"]
        for _i, _v in enumerate(_d["tags"]):
            if _v.lower().startswith("duration"):
                _ftime = _d["tags"][_v][0:8]
    return _ftime

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

def getMovieInfo(path:pathlib.Path)->dict:
    movie_data = {
        'name': '',
        'ext': '',
        'size': '',
        'parent': '',
        'date': '',
        'audio': [],
        'subtitles': [],
        'video': {
            'h': -1,
            'w': -1,
            't': -1,
        },
        'error': False,
        'output': {}
    }
    
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
        for index, stream in enumerate(ffmpeg_json['streams']):
            if 'codec_type' in stream:
                codec_type = stream['codec_type']
                
                match (codec_type):
                    case 'audio': 
                        if 'tags' in stream:
                            if movie_data['video']['t'] != -1:
                                movie_data['video']['t'] = getDuration(stream['tags'])
                            
                            if 'language' in stream['tags']:
                                lang = stream['tags']['language'][0:2]
                                if not lang in movie_data['audio']:
                                    if len(lang):
                                        movie_data['audio'].append(lang)
                        break

                    case 'video':
                        if 'profile' in stream:
                            if stream['codec_name'] in ['hevc','h264','mpeg4']:
                                if stream['profile'] in ['High','Main','Main 10','Advanced Simple Profile']:
                                    if movie_data['video']['t'] == -1:
                                        movie_data["video"]['t'] = getDuration(stream)
                                
                                if movie_data['video']['h'] == -1:
                                    movie_data['video']['h'] = stream['height']
                                if movie_data['video']['w'] == -1:
                                    movie_data['video']['w'] = stream['width']
                        break

                    case 'subtitle':
                        if movie_data['video']['t'] != -1:
                            movie_data['video']['t'] = getDuration(stream)

                        if 'tags' in stream:
                            if 'language' in stream['tags']  and  'title' in stream['tags']:
                                lang_sub = stream['tags']['language'][0:2]
                                _lang = (
                                    "".join(["+", stream["tags"]["title"].lower()])
                                    if "title" in stream["tags"]
                                    else ""
                                )
                                formatted_sub = ''.join([lang_sub, _lang])

                                if not formatted_sub in movie_data['subtitles']:
                                    if len(stream['tags']['language']):
                                        movie_data['subtitles'].append(formatted_sub)
                        break

    movie_data['error'] = False if 'streams' in ffmpeg_json else True
    movie_data['output'] = {} if 'streams' in ffmpeg_json else cmd_output
    return movie_data

if __name__ == '__main__':
    files = [ file for file in pathlib.Path(ROOT_FOLDER).rglob("*") if not splitPath(file)[-2] in BLACKLISTED_FOLDERS and re.search(regex, str(file)) ]
    
    for index, movie in enumerate(files):
        file_name = os.path.basename(movie)[:-4]
        file_ext = os.path.splitext(movie)[1][1:]
        parentFolder = getParentFolder(movie)

        if not parentFolder in BLACKLISTED_FOLDERS:
            movie_data = getMovieInfo(movie)
            movie_data['index'] = index

            print('',end=LINE_CLEAR)
            print( '[%d/%d] Analysing %s ...' % ( index+1, len(files), file_name ), end='\r' )

            # movie_db['list'].append( json.loads(movie_data))
            movie_db['list'].append( movie_data )
    print()
        
    with open('ffmpeg.json','w') as file:
        file.write( json.dumps(movie_db,indent= 2) )

    print( 'Length: %d' % len(files))