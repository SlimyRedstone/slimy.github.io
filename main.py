from flask import Flask, render_template, jsonify, request
import os
import json
import sys
import pathlib
import re
from datetime import datetime
import subprocess as subp


global movie_db
global MOVIE_ROOT_FOLDER
global USE_DB_FILE
global execute_modes

execute_modes = []
FOLDER_PATH = os.path.dirname(__file__)
# MOVIES_DB_PATH = os.path.join(FOLDER_PATH, "movie_db.json")
DB_FILE_NAME = "db.json"
DEBUG_DB_FILE_NAME = "db-debug.json"
VIDEO_EXT = ["mp4", "mkv", "avi", "webm"]
MOVIE_ROOT_FOLDER = ""
USE_DB_FILE = True
BLACKLISTED_FOLDERS = [
    "Flightplan",
    "Subtitles",
    "Featurettes",
    "Optimized for Mobile",
]
DEBUG = False
DEBUG_SERVER = True
DEBUG_DB_FILE = False

if len(sys.argv) >= 2:
    for _i, arg in enumerate(sys.argv):
        if _i >= 1:
            if arg != "-D":
                if arg == "-d":
                    _dir = str(sys.argv[_i + 1])
                    if os.path.isdir(_dir):
                        # print( os.path.abspath(_dir) )
                        MOVIE_ROOT_FOLDER = pathlib.Path(_dir)
                    else:
                        raise NotADirectoryError
                elif arg == "-r" or arg == "--reload":
                    execute_modes.append("reload")
                    if os.path.exists(DB_FILE_NAME):
                        os.remove(DB_FILE_NAME)
                elif arg == "-c" or arg == "--create-db":
                    execute_modes.append("create")
                    DEBUG_DB_FILE = True
                elif arg == "-R" or arg == "--read-from-debug-db":
                    execute_modes.append("readDb")

                USE_DB_FILE = False
else:
    # MOVIE_ROOT_FOLDER = os.path.join(FOLDER_PATH, "movies")
    print("Use -d PATH to point to the directory to analyze")
    print('Use -D PATH to use "%s" file' % DB_FILE_NAME)
    print("Use -r or --reload to reload the database")
    exit()


movie_db = {"list": [], "ignore": {"files": [], "folders": []}}

app = Flask(__name__, template_folder=".")


def getRegexFromList(_list: list = []) -> str:
    _str = ""
    for _i, _v in enumerate(_list):
        _str = "".join([_str, "(", _v, ")", ("|" if _i < len(_list) - 1 else "")])
    return "".join(["(", _str, ")"])


def getFileName(_path, _ext=True) -> str:
    _name = os.path.basename(_path).split("/")[-1]
    if not _ext:
        _name = os.path.splitext(_name)[0]
    return _name


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


def getParent(_path: str):
    return os.path.normpath(os.path.dirname(_path)).split("\\")[-1]


def clearJSON(_json) -> dict:
    return json.loads(json.dumps(str(_json)))


def executeCMDShell(_cmd: list, debug=False, json_output=True) -> dict:
    _process = subp.run(
        args=_cmd,
        shell=True,
        capture_output=True,
        text=True,
        universal_newlines=True,
        timeout=20.0,
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


def getVideoInfos(_input: str | dict, from_debug=False) -> dict:
    global _output
    global return_db
    _output = {}
    return_db = {"duration": "", "video": {}, "audio": [], "subtitles": []}
    if not from_debug:
        _cmd = [
            "ffprobe",
            "-hide_banner",
            "-show_streams",
            "-print_format",
            "json",
            "-i",
        ]
        _cmd.append(_input)
        _output = executeCMDShell(_cmd)

        if DEBUG:
            with open("./movie.json", "w") as f:
                f.write(json.dumps(_output, indent=True))
    else:
        if type(_input) == "dict":
            _output = _input.copy()

    if "streams" in _input:
        for _i, data in enumerate(_input["streams"]):
            if "codec_type" in data:
                global _lang
                global _short_lang
                global _f_lang
                _lang = ""
                _short_lang = ""
                _f_lang = ""

                if data["codec_type"] == "audio":
                    if "tags" in data:

                        if not len(return_db["duration"]):
                            return_db["duration"] = getDuration(data["tags"])

                        if "language" in data["tags"]:
                            _lang = data["tags"]["language"][0:2]

                            if not _lang in return_db["audio"]:
                                if len(data["tags"]["language"]):
                                    return_db["audio"].append(_lang)

                elif data["codec_type"] == "video":
                    if data['codec_name'] in ['hevc', 'h264', 'mpeg4']:
                        if data['profile'] in ['High','Main','Main 10','Advanced Simple Profile']:
                            if not len(return_db["duration"]):
                                return_db["duration"] = getDuration(data)

                        if not 'height' in return_db['video']:
                            return_db["video"] = {
                                "height": data["height"],
                                "width": data["width"],
                            }

                elif data["codec_type"] == "subtitle":
                    if not len(return_db["duration"]):
                        return_db["duration"] = getDuration(data)
                    if "tags" in data:
                        if "language" in data["tags"] and "title" in data["tags"]:
                            _short_lang = data["tags"]["language"][0:2]
                            _lang = (
                                "".join(["+", data["tags"]["title"].lower()])
                                if "title" in data["tags"]
                                else ""
                            )
                            _f_lang = "".join([_short_lang, _lang])

                            if not _f_lang in return_db["subtitles"]:
                                if len(data["tags"]["language"]):
                                    return_db["subtitles"].append(_f_lang)

        # _return["duration"] = _duration
        return_db["error"] = False
        return_db["output"] = {}
    else:
        # print('❌\tError while analyzing "%s"' % _filename)
        # print(json.dumps(_output, indent=True))
        return_db["error"] = True
        return_db["output"] = _output

    # if type(_return['duration']) == "null"

    return return_db


def updateJSON(
    ignore_folder=BLACKLISTED_FOLDERS, _path=MOVIE_ROOT_FOLDER, _filter="size"
) -> dict:
    _json = movie_db
    _regex = r"\S\." + getRegexFromList(VIDEO_EXT)
    _files = [f for f in _path.rglob("*") if re.search(_regex, str(f))]

    for _i, _f in enumerate(_files):
        _file_path = os.path.normpath(os.path.join(_path, _f))
        _file_parts = _f.parts
        _is_path_dir = os.path.isdir(_file_path)
        _file_ext = os.path.splitext(_f)[1][1:]  # Removes the dot in the extension
        _file_name = _file_parts[-1]
        _parent_folder = getParent(_file_path)
        if _parent_folder in ignore_folder:
            print('Skipping file "%s"' % _file_name)
        else:
            # print('%s'%_parent_folder)
            _date = numberToDateTime(os.path.getmtime(_file_path))
            _infos = getVideoInfos(_file_path)
            print(
                '[%d of %d]\tAnalyzing file "%s" %s %s'
                % (
                    _i + 1,
                    len(_files),
                    _file_name,
                    "❌" if "error" in _infos and _infos["error"] else "✔️",
                    json.dumps(_infos["output"], indent=False)
                    if "output" in _infos
                    else "",
                )
            )
            if _file_ext in VIDEO_EXT:
                if not _file_name in _json["list"]:
                    _json["list"].append(
                        {
                            "name": _file_name,
                            "ext": _file_ext,
                            "size": os.path.getsize(_file_path),
                            "parent": getParent(_file_path),
                            "date": _date,
                            "audio": _infos["audio"],
                            "subtitles": _infos["subtitles"],
                            "video": {
                                "h": _infos["video"]["height"]
                                if "height" in _infos["video"]
                                else -1,
                                "w": _infos["video"]["width"]
                                if "width" in _infos["video"]
                                else -1,
                                "t": _infos["duration"]
                                if "duration" in _infos
                                and type(_infos["duration"]) == "string"
                                else "#Not Available",
                            },
                        }
                    )

    _json["list"].sort(key=lambda v: v[_filter], reverse=True)
    _json["error"] = False
    _json["ignore"]["folders"] = ignore_folder
    with open(DB_FILE_NAME, "w") as f:
        f.write(json.dumps(_json))
    # print(json.dumps(_json,indent=True))
    return _json


@app.route("/")
def wb_Root():
    return render_template("index.html")


@app.route("/json")
def wb_JSON():
    return jsonify(movie_db)


def createDebugDb():
    regex = r"\S\." + getRegexFromList(VIDEO_EXT)
    files = [f for f in MOVIE_ROOT_FOLDER.rglob("*") if re.search(regex, str(f))]
    global movies_data_json
    movies_data_json = {"list": []}
    cmd = ["ffprobe", "-hide_banner", "-show_streams", "-print_format", "json", "-i"]
    for index, file in enumerate(files):
        # if index != 0: break
        if not getParent(file) in BLACKLISTED_FOLDERS:
            file_path = os.path.normpath(
                os.path.join(MOVIE_ROOT_FOLDER, file.name)
            ).replace("\\", "/")
            temp_cmd = cmd.copy()
            temp_cmd.append(str(file_path))
            output = executeCMDShell(temp_cmd)
            if "streams" in output:
                movies_data_json["list"].append(
                    {
                        "index": index,
                        "name": getFileName(file, False),
                        "path": os.path.normpath(file).replace("\\", "/"),
                        "size": os.path.getsize(file),
                        "parent": getParent(file),
                        "ext": file.name.split(".")[-1],
                        "date": numberToDateTime(os.path.getmtime(file)),
                        "data": json.loads(clearJSON(output)),
                    }
                )
                # print("streams")
                # movies_data_json["list"][index]["data"] = output

            print(
                '[%s of %s]\tAnalyzing file "%s"'
                % (str(index + 1), str(len(files)), file.name)
            )

    with open(DEBUG_DB_FILE_NAME, "w") as f:
        f.write(json.dumps(movies_data_json, indent=4))


if __name__ == "__main__":
    if DEBUG_DB_FILE:
        createDebugDb()
    else:
        if "readDb" in execute_modes:
            debug_db = {}
            output_db = {
                "list": [],
                "error": False,
                "ignore": {"files": [], "folders": []},
            }
            with open(DEBUG_DB_FILE_NAME, "r") as f:
                debug_db = json.load(f)

            if "list" in debug_db:
                for index, movie in enumerate(debug_db["list"]):
                    # if index > 3: break
                    # if index != 0: break
                    if 'data' in movie:
                    # if "data" in movie and movie["name"] == "Arrival":
                        if "streams" in movie["data"]:
                            movie_data = getVideoInfos(movie["data"], True)
                            # for _iData, movie_data in enumerate(movie['data']):
                            output_db["list"].append(
                                {
                                    "name": movie["name"],
                                    "ext": movie["ext"],
                                    "size": movie["size"],
                                    "parent": movie["parent"],
                                    "date": movie["date"],
                                    "audio": movie_data["audio"],
                                    "subtitles": movie_data["subtitles"],
                                    "video": {
                                        "h": movie_data["video"]["height"]
                                        if "height" in movie_data["video"]
                                        else -1,
                                        "w": movie_data["video"]["width"]
                                        if "width" in movie_data["video"]
                                        else -1,
                                        "t": movie_data["duration"]
                                        if type(movie_data["duration"]) == str and len(movie_data["duration"])
                                        else "#Not Available",
                                    },
                                }
                            )
                            if not len(movie_data["duration"]):
                                print("Movie: %s, Value: %s"%(movie["name"], movie_data["duration"]))


                output_db["list"].sort(key=lambda v: v["size"], reverse=True)
                output_db["error"] = False
                output_db["ignore"]["folders"] = BLACKLISTED_FOLDERS

                with open(DB_FILE_NAME, "w") as f:
                    print("%s file updated" % DB_FILE_NAME)
                    f.write(json.dumps(output_db, indent=4))
        else:
            try:
                # if USE_DB_FILE:
                if not os.path.exists(DB_FILE_NAME):
                    print("No %s file" % DB_FILE_NAME)
                    movie_db = updateJSON()

                with open(DB_FILE_NAME, "r") as f:
                    print('Reading "%s" file' % DB_FILE_NAME)
                    movie_db = json.load(f)

                print("Starting server...")
                app.run(debug=DEBUG_SERVER, port=8081)
            except KeyboardInterrupt as kE:
                print("Server has been manually closed")
