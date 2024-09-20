import yt_dlp
import os
from pydub import AudioSegment
import requests
import mimetypes
import math
import logging
from tqdm import trange, tqdm
import shutil

def download_youtube_video(youtube_link, output_path='video_files', video_format='mp4'):
    """
    Downloads the entire YouTube video using yt_dlp.
    
    Parameters:
    - youtube_link (str): URL of the YouTube video.
    - output_path (str): Directory to save the downloaded video.
    - video_format (str): Desired video format (e.g., 'mp4').
    
    Returns:
    - str: Path to the downloaded video file, or None if download failed.
    """
    ydl_opts = {
        'format': f'bestvideo[ext={video_format}]+bestaudio[ext=m4a]/best[ext={video_format}]',
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'merge_output_format': video_format,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_link, download=True)
            video_path = ydl.prepare_filename(info_dict)
            logging.info(f"Downloaded video: {video_path}")
            return video_path
    except Exception as e:
        logging.error(f"Failed to download video: {e}")
        return None



def download_youtube_audio(url, output_path='audio_files', audio_format='mp3'):
    """
    Downloads audio from a YouTube video.

    Parameters:
    - url (str): The URL of the YouTube video.
    - output_path (str): The directory where the audio will be saved.
    - audio_format (str): The desired audio format (e.g., 'mp3', 'm4a').

    Returns:
    - str: The path to the downloaded audio file.
    """
    # Ensure the output directory exists
    os.makedirs(output_path, exist_ok=True)
    
    # Set up yt_dlp options
    ydl_opts = {
        'format': 'bestaudio/best',  # Select the best available audio quality
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),  # Output template
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',  # Extract audio using FFmpeg
            'preferredcodec': audio_format,  # Desired audio format
            'preferredquality': '192',  # Audio quality
        }],
        'quiet': False,  # Set to True to suppress output
        'noplaylist': True,  # Only download single video, not playlist
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # Extract information and download
            info_dict = ydl.extract_info(url, download=True)
            
            # Prepare the filename
            filename = ydl.prepare_filename(info_dict)
            base, _ = os.path.splitext(filename)
            audio_file = f"{base}.{audio_format}"
            
            
            print(f"Audio downloaded successfully: {audio_file}")
            return audio_file
        except yt_dlp.utils.DownloadError as e:
            print(f"Error downloading audio: {e}")
            return None
        
# utils.py




def split_audio_with_sliding_window(input_audio_path, output_dir='audio_chunks', 
                                   chunk_duration_ms=5000, context_duration_ms=500):
    """
    Splits audio into fixed-length subtitle chunks with overlapping context.
    
    Each chunk corresponds to a 7-second subtitle window and includes 2 seconds
    of audio before and after the subtitle window to provide context for translation.
    
    Parameters:
    - input_audio_path (str): Path to the input audio file.
    - output_dir (str): Directory to save the audio chunks.
    - chunk_duration_ms (int): Duration of each subtitle in milliseconds (e.g., 7000 ms for 7 seconds).
    - context_duration_ms (int): Duration of context to include before and after each chunk in ms (e.g., 2000 ms).
    
    Returns:
    - List of tuples: Each tuple contains (chunk_path, subtitle_start_time, subtitle_end_time)
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the audio file
    audio = AudioSegment.from_file(input_audio_path)
    total_duration = len(audio)  # in milliseconds
    
    # Calculate the number of chunks
    num_chunks = math.ceil(total_duration / chunk_duration_ms)
    
    final_chunks = []
    
    for i in trange(num_chunks):
        # Define subtitle timing
        subtitle_start = i * chunk_duration_ms
        subtitle_end = min((i + 1) * chunk_duration_ms, total_duration)
        
        # Define audio chunk timing with context
        chunk_start = max(subtitle_start - context_duration_ms, 0)
        chunk_end = min(subtitle_end + context_duration_ms, total_duration)
        
        # Extract the audio chunk
        chunk = audio[chunk_start:chunk_end]
        
        # Define chunk filename
        chunk_filename = f"chunk_{i+1}.mp3"
        chunk_path = os.path.join(output_dir, chunk_filename)
        
        # Export the audio chunk
        chunk.export(chunk_path, format="mp3")
        
        # Append to final chunks list
        final_chunks.append((chunk_path, subtitle_start, subtitle_end))
        
        # Log the creation
        # print(f"Created {chunk_filename}: {format_timestamp(subtitle_start)} to {format_timestamp(subtitle_end)}")
    
    return final_chunks


def send_to_sarvam_api(audio_file_path, api_key, prompt=None, model='saaras:v1'):
    """
    Sends an audio file to the Sarvam Speech To Text Translate API for transcription.

    Parameters:
    - audio_file_path (str): Path to the audio file to be transcribed.
    - api_key (str): Your Sarvam API subscription key.
    - prompt (str, optional): Prompt to assist the transcription.
    - model (str, optional): Model to be used. Defaults to 'saaras:v1'.

    Returns:
    - dict: The API response containing the transcript and language_code.
    """
    url = "https://api.sarvam.ai/speech-to-text-translate"

    headers = {
        'api-subscription-key': api_key
    }

    # Determine MIME type based on file extension
    mime_type, _ = mimetypes.guess_type(audio_file_path)
    if mime_type not in ['audio/mpeg', 'audio/wave', 'audio/wav', 'audio/x-wav']:
        print(f"Unsupported audio format: {mime_type}")
        return None

    with open(audio_file_path, 'rb') as f:
        files = {
            'file': (os.path.basename(audio_file_path), f, mime_type)
        }

        data = {
            'model': model
        }

        if prompt:
            data['prompt'] = prompt

        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            result = response.json()
            print(f"Transcription successful for {os.path.basename(audio_file_path)}")
            return result
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred for {os.path.basename(audio_file_path)}: {http_err} - {response.text}")
        except Exception as err:
            print(f"An error occurred for {os.path.basename(audio_file_path)}: {err}")

    return None

def process_chunks_and_collect_transcripts(chunks, api_key, prompt):
    """
    Processes each audio chunk and collects transcripts with timestamps.

    Parameters:
    - chunks (list): List of tuples containing (chunk_path, start_time, end_time).
    - api_key (str): Your Sarvam API subscription key.

    Returns:
    - List of dictionaries: Each dict contains 'start_time', 'end_time', and 'transcript'.
    """
    transcripts = []
    for chunk_path, start_ms, end_ms in tqdm(chunks):
        # print(f'Processing chunk: {chunk_path} from {start_ms/1000:.2f}s to {end_ms/1000:.2f}s')
        response = send_to_sarvam_api(chunk_path, api_key, prompt=prompt)
        if response and 'transcript' in response:
            transcript = response['transcript']
            transcripts.append({
                'start_time': start_ms,
                'end_time': end_ms,
                'transcript': transcript
            })
        else:
            transcripts.append({
                'start_time': start_ms,
                'end_time': end_ms,
                'transcript': '[Unintelligible]'
            })
    return transcripts

def format_timestamp(ms):
    """
    Formats milliseconds to SRT timestamp format.

    Parameters:
    - ms (int): Time in milliseconds.

    Returns:
    - str: Formatted timestamp.
    """
    seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def create_srt_file(transcripts, output_file='subtitles.srt', max_chars=42):
    """
    Creates an SRT file from transcripts with timestamps, ensuring readability.

    Parameters:
    - transcripts (list): List of dictionaries containing 'start_time', 'end_time', and 'transcript'.
    - output_file (str): Path to save the SRT file.
    - max_chars (int): Maximum number of characters per subtitle line.

    Returns:
    - None
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        subtitle_number = 1
        for entry in transcripts:
            start = format_timestamp(entry['start_time'])
            end = format_timestamp(entry['end_time'])
            text = entry['transcript'].replace('\n', ' ').strip()
            
            # Split text into multiple lines if it exceeds max_chars
            lines = []
            words = text.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= max_chars:
                    if current_line:
                        current_line += ' '
                    current_line += word
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            # Combine lines with newline characters
            formatted_text = '\n'.join(lines)
            
            # Write to SRT
            f.write(f"{subtitle_number}\n{start} --> {end}\n{formatted_text}\n\n")
            subtitle_number += 1
    print(f"SRT file created at {output_file}")


def get_language_prompt(language):
    """
    Generates a prompt based on the selected language.
    
    Parameters:
    - language (str): Selected language.
    
    Returns:
    - str or None: Prompt string or None if language is 'Unknown'.
    """
    if language.lower() == 'unknown':
        return None
    else:
        return f"{language} language audio"

def clear_folder(folder_path):
    """
    Clears all files and subdirectories in the specified folder.
    
    Parameters:
    - folder_path (str): Path to the folder to clear.
    
    Returns:
    - None
    """
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
            os.makedirs(folder_path, exist_ok=True)
            logging.info(f"Cleared folder: {folder_path}")
        except Exception as e:
            logging.error(f"Failed to clear folder {folder_path}. Reason: {e}")
            st.error(f"Failed to clear folder {folder_path}. Please check permissions.")
    else:
        os.makedirs(folder_path, exist_ok=True)
        logging.info(f"Created folder: {folder_path}")