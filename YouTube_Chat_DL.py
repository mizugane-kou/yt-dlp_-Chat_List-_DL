

#  ライブラリのインストール
#  pip install yt-dlp pytchat


import json
import re
from yt_dlp import YoutubeDL
import pytchat

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def download_chat(youtube_url):
    # 動画情報を取得
    ydl_opts = {'skip_download': True, 'writesubtitles': True}
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(youtube_url, download=False)
        video_id = info_dict.get("id", None)
        video_title = info_dict.get("title", None)

    # ファイル名を整形
    sanitized_title = sanitize_filename(video_title)

    # チャットデータを取得
    chat = pytchat.create(video_id=video_id)
    chat_data = []
    while chat.is_alive():
        for c in chat.get().items:
            chat_data.append(f"{c.datetime} {c.author.name}: {c.message}")

    # テキストデータを.txtファイルに書き出し
    with open(f"{sanitized_title}.txt", "w", encoding="utf-8") as f:
        for line in chat_data:
            f.write(line + "\n")

if __name__ == "__main__":
    youtube_url = input("配信のURLを入力してください: ")
    download_chat(youtube_url)
