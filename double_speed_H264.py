#! python3
''' Formatted with yapf'''

import ffmpeg
import sys
import os
import youtube_dl

MAX_RETRIES = 5
MAX_HEIGHT = 1440
MAX_WIDTH = 2960
MAX_INPUT_FRAME_RATE = 60
MAX_OUTPUT_FRAME_RATE = 60
FILE_NAME_TEMPLATE = "%(uploader)s_%(title)s"
SPEED_FACTOR = 2.0
GOP_LENGTH_SECONDS = 10


def get_height(filename):
    try:
        probe = ffmpeg.probe(filename)
        video_stream = next((stream for stream in probe['streams']
                             if stream['codec_type'] == 'video'), None)
        height = int(video_stream['height'])
        return height
    except ffmpeg.Error as e:
        print(e.stderr)
        raise e


def get_frame_rate(filename):
    probe = ffmpeg.probe(filename)
    video_stream = next(
        (stream
         for stream in probe['streams'] if stream['codec_type'] == 'video'),
        None)
    fps = eval(video_stream['r_frame_rate'])
    return float(fps)


def download_videos(videos, opts, retries_remaining):
    result_list = []
    with youtube_dl.YoutubeDL(opts) as ydl:
        for url in videos:
            try:
                extracted_info = ydl.extract_info(url)
                if "_type" in extracted_info and "entries" in extracted_info and extracted_info[
                        "_type"] is 'playlist':
                    for entry in extracted_info["entries"]:
                        filename = ydl.prepare_filename(entry) + ".mkv"
                        if filename not in result_list:
                            result_list.append(filename)
                else:
                    filename = ydl.prepare_filename(extracted_info) + ".mkv"
                    if filename not in result_list:
                        result_list.append(filename)
            except:
                print(f'failed to download {url}')
                return download_videos(videos, opts, retries_remaining - 1)

    return result_list


def calculate_gop_size(framerate):
    return round(framerate * GOP_LENGTH_SECONDS / 2) * 2


def main():
    ydl_opts = {
        'format': 'bestvideo[fps<=%(fps)s]+bestaudio/best' % {
            "fps": MAX_INPUT_FRAME_RATE
        },
        'outtmpl': FILE_NAME_TEMPLATE,
        'restrictfilenames': True,
        'merge_output_format': 'mkv'
    }

    downloaded_videos = download_videos(sys.argv[1:], ydl_opts, MAX_RETRIES)

    for in_file_name in downloaded_videos:
        file_name_root = os.path.splitext(in_file_name)[0]
        destination_file = file_name_root + "_[%dx].mp4" % SPEED_FACTOR
        if os.path.isfile(destination_file):
            continue

        new_height = get_height(in_file_name)

        inputObject = ffmpeg.input(in_file_name,
                                   vaapi_device='/dev/dri/renderD128')
        v1 = inputObject['v'].setpts("PTS/%s" % SPEED_FACTOR)
        v1 = v1.filter('format', 'nv12').filter_(filter_name='hwupload')
        if (new_height > MAX_HEIGHT):
            v1 = v1.filter('scale_vaapi', -2, MAX_HEIGHT)

        a1 = inputObject['a'].filter('atempo', SPEED_FACTOR)

        temp_file_name = file_name_root + ".tmp"

        output_framerate = min(SPEED_FACTOR * get_frame_rate(in_file_name),
                               MAX_OUTPUT_FRAME_RATE)

        ffmpeg.output(v1,
                      a1,
                      temp_file_name,
                      format='mp4',
                      vcodec='h264_vaapi',
                      video_bitrate="8M",
                      vprofile='main',
                      g=calculate_gop_size(output_framerate),
                      acodec='aac',
                      audio_bitrate="192k",
                      r=output_framerate).global_args('-hide_banner').run(
                          overwrite_output=True)
        ffmpeg.input(temp_file_name).output(
            destination_file, codec='copy').global_args('-hide_banner').run(
                overwrite_output=True)
        os.remove(temp_file_name)


if __name__ == "__main__":
    main()
