import streamlit as st
import os
import logging
from utils import (
    download_youtube_audio,  # Assuming this is still used for audio extraction
    split_audio_with_sliding_window,
    process_chunks_and_collect_transcripts,
    create_srt_file,
    download_youtube_video,  # Newly added function
    get_language_prompt,
    clear_folder
)

# Load environment variables
SARVAM_KEY = st.secrets["SARVAM_KEY"]


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    st.title("YouTube Subtitle Generator, uses Sarvam Speech to Text API")
    st.write("""
    Enter a YouTube link and select the language of the video to generate subtitles.
    The app will process the video, transcribe the audio, and create an `.srt` subtitle file for you to download and view.
    """)
    
    # Language options
    language_options = [
        'Unknown',
        'Hindi',
        'Telugu',
        'Malayalam',
        'Kannada',
        'Bengali',
        'Marathi',
        'Odia',
        'Punjabi',
        'Tamil',
        'English',
        'Gujarati'
    ]
    
    # Create the form
    with st.form("subtitle_form"):
        youtube_link = st.text_input("Enter the YouTube link:")
        
        language_option = st.selectbox(
            "Select the language of the video:",
            options=language_options
        )
        
        submit_button = st.form_submit_button("Generate Subtitles")
    
    if submit_button:
        if not youtube_link:
            st.error("Please enter a valid YouTube link.")
            st.stop()
        
        language = language_option
        prompt = get_language_prompt(language)
        print(f"Prompt: {prompt}")
        
        st.write("### Processing your request...")
        
        # Step 1: Clear necessary folders
        with st.spinner('Clearing previous files...'):
            clear_folder('audio_chunks')
            clear_folder('audio_files')
            clear_folder('video_files')  # Ensure video_files folder is cleared as well
            # delete .srt files also
            for file in os.listdir():
                if file.endswith(".srt"):
                    os.remove(file)
        
        # Step 2: Download the entire YouTube video using yt_dlp
        with st.spinner('Downloading video from YouTube...'):
            try:
                downloaded_video, duration = download_youtube_video(youtube_link)

                if downloaded_video:
                    if duration > 1200:
                        st.error("Video length exceeds 20 minutes. Raghavendra doesn't have enough credits \
                                 But if u are excited to try. Mail to `raghavendra.kaushik.iitkgp@gmail.com`. He will recharge.")
                        st.stop()
                    st.success(f"Downloaded video file: `{downloaded_video}`")
                else:
                    st.error("Failed to download video file.")
                    st.stop()

            except Exception as e:
                st.error(f"Error downloading video: {e}")
                st.stop()
        
        # Step 3: Extract audio from the downloaded video
        with st.spinner('Extracting audio from the video...'):
            try:
                downloaded_audio = download_youtube_audio(youtube_link)
                if downloaded_audio:
                    st.success(f"Extracted audio file: `{downloaded_audio}`")
                else:
                    st.error("Failed to extract audio from the video.")
                    st.stop()
            except Exception as e:
                st.error(f"Error extracting audio: {e}")
                st.stop()
        
        # Step 4: Split audio into sliding window chunks
        with st.spinner('Splitting audio into chunks...'):
            try:
                chunks = split_audio_with_sliding_window(downloaded_audio)
                st.success(f"Audio split into {len(chunks)} chunks.")
            except Exception as e:
                st.error(f"Error splitting audio: {e}")
                st.stop()
        
        # Step 5: Transcribe audio chunks using Sarvam API
        with st.spinner('Transcribing audio chunks...'):
            try:
                transcripts = process_chunks_and_collect_transcripts(
                    chunks, 
                    SARVAM_KEY, 
                    prompt
                )
                if transcripts:
                    st.success("Transcription completed successfully.")
                else:
                    st.error("No transcripts were generated.")
                    st.stop()
            except Exception as e:
                st.error(f"Error during transcription: {e}")
                st.stop()
        
        # Step 6: Create SRT file
        with st.spinner('Creating subtitle file...'):
            try:
                video_name = os.path.splitext(os.path.basename(downloaded_video))[0]
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
        
        
        
        # Step 7: Display the video with subtitles
        st.markdown("### Watch the Video with Subtitles")
        st.info("""
        *Note*: To display subtitles within Streamlit's video player, ensure that the subtitles are in `.srt` or `.vtt` format.
        The subtitles will appear as closed captions in the video player.
        """)

        # Step 8: Provide download link for SRT file
        st.markdown("### Download Your Subtitles")
        try:
            with open(subtitle_filename, 'rb') as f:
                subtitle_bytes = f.read()
                st.download_button(
                    label="Download Subtitles (.srt)",
                    data=subtitle_bytes,
                    file_name=subtitle_filename,
                    mime='text/plain'
                )
        except Exception as e:
            st.error(f"Error reading subtitle file: {e}")

        print("Video paths")
        print(downloaded_video)

        print("Subtitle paths")
        print(subtitle_filename)

        try:
            st.video(downloaded_video, format="video/mp4", start_time=0, subtitles=subtitle_filename)
        except Exception as e:
            st.error(f"Error displaying video: {e}")
        
        # Optional: Display the generated SRT content
        st.markdown("---")
        st.write("### Generated Subtitles Preview")
        if os.path.exists(subtitle_filename):
            try:
                with open(subtitle_filename, 'r', encoding='utf-8') as f:
                    srt_content = f.read()
                    st.text_area("Subtitle File Content:", srt_content, height=300)
            except Exception as e:
                st.error(f"Error reading subtitle file: {e}")
        else:
            st.write("No subtitles to display.")

if __name__ == "__main__":
    main()
