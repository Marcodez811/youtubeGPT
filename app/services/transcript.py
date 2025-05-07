import requests
from bs4 import BeautifulSoup
from typing import List
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import Playlist
from langchain_text_splitters import RecursiveCharacterTextSplitter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

VID_PREFIX = 'https://www.youtube.com/watch?v='
LIST_PREFIX = 'https://www.youtube.com/playlist?list='
MALFORMED_ERROR = "The provided URL is malformed."
MISSING_ERROR = 'The provided URL is not present.'

class Transcript:
    def __init__(self, url: str, id: str, title: str, content: str, chunks: List[str]):
        self.url = url
        self.vid_id = id
        self.vid_title = title
        self.content = content
        self.chunks = chunks

def get_video_title(url: str):
    """Gets the video title from the given YouTube link."""
    assert url, MISSING_ERROR
    assert url.startswith(VID_PREFIX), MALFORMED_ERROR
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        title_tag = soup.find('title')
        return title_tag.text.split(' - YouTube')[0]
    except Exception as e:
        print(f"Failed to fetch title for {url}: {e}")
        return ""

def get_video_id(url: str):
    """Gets the video id from the given YouTube link."""
    assert url, MISSING_ERROR
    assert url.startswith(VID_PREFIX), MALFORMED_ERROR
    return url.split(VID_PREFIX)[1].split('&')[0]

def get_playlist_title(url: str):
    """Gets the playlist id from the given YouTube link."""
    assert url, "URL is missing"
    assert url.startswith(LIST_PREFIX), MALFORMED_ERROR
    return Playlist(url).title

def get_video_content(vid_id: str):
    """Gets the video transcript from the given YouTube link."""
    client = YouTubeTranscriptApi()
    t = client.get_transcript(vid_id)
    return t

def chunk(text: str, chunk_size: int, chunk_overlap: int):
    """Create chunks of transcripts"""
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", "(?<=\. )", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return list(map(lambda x: x.replace('\n', ' '), text_splitter.split_text(text)))

def build_transcript_from_url(url: str):
    assert url, MISSING_ERROR
    assert url.startswith(VID_PREFIX), MALFORMED_ERROR
    vid_id = get_video_id(url)
    vid_name = get_video_title(url)
    vid_content = ' '.join(map(lambda x: x['text'], get_video_content(vid_id)))
    chunks = chunk(vid_content, 300, 30)
    return Transcript(url, vid_id, vid_name, vid_content, chunks)

def load_pipeline(url: str, is_list: bool):
    """Loads the provided url through the pipeline to create actual transcript intstances."""
    assert url, MISSING_ERROR
    assert (
        url.startswith(VID_PREFIX) and len(url) > len(VID_PREFIX)
    ) or (
        url.startswith(LIST_PREFIX) and len(url) > len(LIST_PREFIX)
    ), MALFORMED_ERROR

    if is_list:
        playlist = Playlist(url)
        lst = list()
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = [executor.submit(build_transcript_from_url, vid) for vid in playlist]
            for future in as_completed(futures):
                transcript_data = future.result()
                if transcript_data:
                    lst.append(transcript_data)
        return lst
    transcript_data = build_transcript_from_url(url)
    return transcript_data