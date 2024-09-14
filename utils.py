import yt_dlp
import os
from pydub import AudioSegment, silence
import requests
import mimetypes

def download_youtube_audio(url, output_path='downloads', audio_format='mp3'):
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
        


def split_audio_on_silence(input_audio_path, output_dir='audio_chunks', 
                           min_silence_len=1000, silence_thresh=-40, 
                           keep_silence=500, max_chunk_duration=7000):
    """
    Splits audio into chunks based on silence and maximum duration.
    
    Parameters:
    - input_audio_path (str): Path to the input audio file.
    - output_dir (str): Directory to save the audio chunks.
    - min_silence_len (int): Minimum length of silence in ms.
    - silence_thresh (int): Silence threshold in dBFS.
    - keep_silence (int): Amount of silence to keep at the beginning and end of each chunk in ms.
    - max_chunk_duration (int): Maximum duration of each chunk in ms (e.g., 7000 ms for 7 seconds).
    
    Returns:
    - List of tuples: Each tuple contains (chunk_path, start_time, end_time)
    """
    os.makedirs(output_dir, exist_ok=True)
    audio = AudioSegment.from_file(input_audio_path)
    
    print("Splitting audio into chunks based on silence...")
    initial_chunks = silence.split_on_silence(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        keep_silence=keep_silence
    )
    
    final_chunks = []
    current_time = 0  # in milliseconds
    
    for i, chunk in enumerate(initial_chunks):
        chunk_duration = len(chunk)
        start_time = current_time
        end_time = current_time + chunk_duration
        
        # If chunk is longer than max_chunk_duration, split it further
        if chunk_duration > max_chunk_duration:
            num_subchunks = chunk_duration // max_chunk_duration + 1
            subchunk_duration = chunk_duration / num_subchunks
            for j in range(num_subchunks):
                sub_start = j * subchunk_duration
                sub_end = (j + 1) * subchunk_duration
                subchunk = chunk[int(sub_start):int(sub_end)]
                
                subchunk_filename = f"chunk_{i+1}_{j+1}.mp3"
                subchunk_path = os.path.join(output_dir, subchunk_filename)
                subchunk.export(subchunk_path, format="mp3")
                
                sub_start_time = start_time + int(sub_start)
                sub_end_time = start_time + int(sub_end)
                
                final_chunks.append((subchunk_path, sub_start_time, sub_end_time))
                print(f"Created {subchunk_filename}: {sub_start_time/1000:.2f}s to {sub_end_time/1000:.2f}s")
                
            current_time += chunk_duration + keep_silence
        else:
            # Export the chunk as is
            chunk_filename = f"chunk_{i+1}.mp3"
            chunk_path = os.path.join(output_dir, chunk_filename)
            chunk.export(chunk_path, format="mp3")
            
            final_chunks.append((chunk_path, start_time, end_time))
            print(f"Created {chunk_filename}: {start_time/1000:.2f}s to {end_time/1000:.2f}s")
            
            # Update the current time
            current_time = end_time + keep_silence  # Adding kept silence to avoid overlap
    
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
    for chunk_path, start_ms, end_ms in chunks:
        print(f'Processing chunk: {chunk_path} from {start_ms/1000:.2f}s to {end_ms/1000:.2f}s')
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

