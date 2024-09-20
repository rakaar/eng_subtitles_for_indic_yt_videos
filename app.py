import streamlit as st
import os
import shutil
import logging
from dotenv import load_dotenv
from utils import (
    download_youtube_audio,
    split_audio_with_sliding_window,
    process_chunks_and_collect_transcripts,
    create_srt_file
)

# Load environment variables
load_dotenv()
SARVAM_KEY = os.getenv('SARVAM_KEY')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def format_timestamp(ms):
    """
    Formats milliseconds to SRT timestamp format.
    
    Parameters:
    - ms (int): Time in milliseconds.
    
    Returns:
    - str: Formatted timestamp (HH:MM:SS,mmm).
    """
    seconds, milliseconds = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def main():
    st.title("YouTube Subtitle Generator")
    st.write("""
    Upload a YouTube link and select the language of the video to generate subtitles.
    The app will process the audio, transcribe it, and create an `.srt` subtitle file for you to download.
    """)

    # Define language mapping
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

    # Create the form
    with st.form("subtitle_form"):
        youtube_link = st.text_input("Enter the YouTube link:")
        
        language_option = st.selectbox(
            "Select the language of the video:",
            options=[f"{num} - {lang}" for num, lang in num_to_language_mapping.items()],
            format_func=lambda x: x.split(" - ")[1] if " - " in x else x
        )
        
        submit_button = st.form_submit_button("Generate Subtitles")
    
    if submit_button:
        # Extract language number from selected option
        language_num = int(language_option.split(" - ")[0])
        language = num_to_language_mapping.get(language_num, 'Unknown')
        
        if language_num == 0:
            prompt = None
        else:
            prompt = f"{language} language audio"
        
        st.write("### Processing your request...")
        
        # Step 1: Clear necessary folders
        with st.spinner('Clearing previous files...'):
            clear_folder('audio_chunks')
            clear_folder('audio_files')
        
        # Step 2: Download audio from YouTube
        with st.spinner('Downloading audio from the YouTube video...'):
            try:
                downloaded_audio = download_youtube_audio(
                    youtube_link, 
                    output_path='audio_files', 
                    audio_format='mp3'
                )
                if downloaded_audio:
                    st.success(f"Downloaded audio file: `{downloaded_audio}`")
                else:
                    st.error("Failed to download audio file.")
                    st.stop()
            except Exception as e:
                st.error(f"Error downloading audio: {e}")
                st.stop()
        
        # Step 3: Split audio into sliding window chunks
        with st.spinner('Splitting audio into chunks...'):
            try:
                chunks = split_audio_with_sliding_window(
                    downloaded_audio,
                    output_dir='audio_chunks',
                    chunk_duration_ms=7000,       # 7 seconds
                    context_duration_ms=2000      # 2 seconds
                )
                st.success(f"Audio split into {len(chunks)} chunks.")
            except Exception as e:
                st.error(f"Error splitting audio: {e}")
                st.stop()
        
        # Step 4: Transcribe audio chunks using Sarvam API
        with st.spinner('Transcribing audio chunks...'):
            try:
                transcripts = process_chunks_and_collect_transcripts(
                    chunks, 
                    SARVAM_KEY, 
                    prompt=prompt
                )
                if transcripts:
                    st.success("Transcription completed successfully.")
                else:
                    st.error("No transcripts were generated.")
                    st.stop()
            except Exception as e:
                st.error(f"Error during transcription: {e}")
                st.stop()
        
        # Step 5: Create SRT file
        with st.spinner('Creating subtitle file...'):
            try:
                video_name = os.path.splitext(os.path.basename(downloaded_audio))[0]
                subtitle_filename = f'{video_name}.srt'
                create_srt_file(
                    transcripts, 
                    output_file=subtitle_filename, 
                    max_chars=42
                )
                st.success(f"Subtitle file `{subtitle_filename}` created successfully.")
            except Exception as e:
                st.error(f"Error creating SRT file: {e}")
                st.stop()
        
        # Step 6: Provide download link for SRT file
        st.markdown("### Download Your Subtitles")
        with open(subtitle_filename, 'rb') as f:
            subtitle_bytes = f.read()
            st.download_button(
                label="Download Subtitles (.srt)",
                data=subtitle_bytes,
                file_name=subtitle_filename,
                mime='text/plain'
            )
        
        # Step 7: Display the video
        st.markdown("### Watch the Video with Subtitles")
        st.info("""
        *Note*: Streamlit's `st.video` does not support uploading subtitle files for YouTube videos.
        To view subtitles, download the `.srt` file and upload it to your YouTube video manually.
        """)
        
        st.video(youtube_link)
    
    # Optional: Display the generated SRT content
    st.markdown("---")
    st.write("### Generated Subtitles Preview")
    if 'subtitle_filename' in locals() and os.path.exists(subtitle_filename):
        with open(subtitle_filename, 'r', encoding='utf-8') as f:
            srt_content = f.read()
            st.text_area("Subtitle File Content:", srt_content, height=300)
    else:
        st.write("No subtitles to display.")

if __name__ == "__main__":
    main()
