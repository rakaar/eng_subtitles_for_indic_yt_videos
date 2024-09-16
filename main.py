from dotenv import load_dotenv
import os
from utils import download_youtube_audio,split_audio_on_silence, process_chunks_and_collect_transcripts, create_srt_file

load_dotenv()

SARVAM_KEY = os.getenv('SARVAM_KEY')

# empty the audio_chunks folder
print('Emptying audio_chunks folder...')
try:
    os.system('rm -rf audio_chunks/*')
except Exception as e:
    raise Exception('Error emptying audio_chunks folder. Delete all files in folder manually and try again.') from e

# take youtube link as input
youtube_link = input("Enter the youtube link: ")


# take language of video as input
# hi-IN: Hindi, bn-IN: Bengali, kn-IN: Kannada, ml-IN: Malayalam, mr-IN: Marathi, od-IN: Odia, pa-IN: Punjabi, ta-IN: Tamil, te-IN: Telugu, gu-IN: Gujarati, en-IN: English
num_to_language_mapping = {
    0: 'Unknown',
    1: 'Hindi',
    2: 'Telugu',
    3: 'Malayalam',
    4: 'Kannada',
    5: 'Bengali',
    6: 'Marathi',
    7: 'Odia',
    8: 'Punjabi',
    9: 'Tamil',
    10: 'English',
    11: 'Gujarati'
}

print("""
Language of the video and the number to be entered:
    Unknow language: 0
    Hindi: 1
    Telugu: 2
    Malayalam: 3
    Kannada: 4
    Bengali: 5
    Marathi: 6
    Odia: 7
    Punjabi: 8
    Tamil: 9
    English: 10
    Gujarati: 11
      """)
language_num = int(input("Enter the language number: "))

if language_num not in num_to_language_mapping.keys():
    language_num = 0

sys_prompt = 'If unable to translate, then return [Unable to translate]'
if language_num == 0:
    prompt = sys_prompt
else:
    prompt = f"This is a {num_to_language_mapping[language_num]} language audio clip from a Youtube Video. {sys_prompt}"


print('The prompt to assist is:')
print(prompt)

# Download audio from the youtube video
print('Downloading audio from the youtube video...')
downloaded_audio = download_youtube_audio(youtube_link, output_path='audio_files', audio_format='mp3')
if downloaded_audio:
    print(f"Downloaded audio file path: {downloaded_audio}")
else:
    raise Exception("Failed to download audio file")


# Split audio into chunks
print('Splitting audio into chunks...')
if downloaded_audio:
    try:
        chunks = split_audio_on_silence(
            downloaded_audio,
            output_dir='audio_chunks',
            min_silence_len=1000,
            silence_thresh=-40,
            keep_silence=500
        )
    except Exception as e:
        raise Exception(f"Failed to split audio into chunks: {e}")
else:
    raise Exception("Download audio file not found")

# Send API request to Sarvam for transcribing the audio chunks
print('Sending API request to Sarvam for transcribing the audio chunks...')
try:
    transcripts = process_chunks_and_collect_transcripts(chunks, SARVAM_KEY, prompt=prompt)
except Exception as e:
    raise Exception(f"Failed to collect transcripts: {e}")


# create subtitle file named subtitles.srt'
video_name = downloaded_audio.split('/')[-1].rstrip('.mp3')
subtitle_filename = f'{video_name}.srt'
print(f'Creating subtitle file named {subtitle_filename}')

if transcripts:
    try:
        create_srt_file(transcripts, output_file=subtitle_filename, max_chars=42)
    except Exception as e:
        raise Exception(f"Failed to create srt file: {e}")
else:
    raise Exception("No transcripts found")