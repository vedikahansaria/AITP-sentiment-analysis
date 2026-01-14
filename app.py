!pip install -q gradio google-api-python-client pandas requests vaderSentiment
import gradio as gr
import pandas as pd
from googleapiclient.discovery import build
from urllib.parse import urlparse, parse_qs
import requests
import os

# --- CONFIGURATION ---
YOUTUBE_API_KEY = "AIzaSyCzMFq2EwWvuzDzH5xVwfbw2KJuV1hg134"
NEWS_API_KEY = "31ef85e87dcc4a96a07972751c87f901"

# YouTube Video Choices
VIDEO_CHOICES = [
    ("Negative Video 1", "https://www.youtube.com/watch?v=mSXpZtKw8x4"),
    ("Negative Video 2", "https://www.youtube.com/watch?v=PJgfu1TKVow"),
    ("Positive Video 1", "https://www.youtube.com/watch?v=lQo8iLymfoY"),
    ("Positive Video 2", "https://www.youtube.com/watch?v=P-GglbXx8n0")
]

# --- FUNCTION 1: YOUTUBE LOGIC ---
def get_video_id(url):
    """Extracts Video ID."""
    if not url: return None
    parsed_url = urlparse(url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            p = parse_qs(parsed_url.query)
            return p['v'][0]
        if parsed_url.path[:7] == '/embed/':
            return parsed_url.path.split('/')[2]
        if parsed_url.path[:3] == '/v/':
            return parsed_url.path.split('/')[2]
    return None

def fetch_youtube_comments(video_url, progress=gr.Progress()):
    """Fetches up to 120 comments from YouTube."""
    comments_data = []
    MAX_COMMENTS = 120

    try:
        video_id = get_video_id(video_url)
        if not video_id:
            raise ValueError("Invalid YouTube URL.")

        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

        request = youtube.commentThreads().list(
            part="snippet,replies",
            videoId=video_id,
            maxResults=100,
            textFormat="plainText"
        )

        page_count = 0
        progress(0, desc="Starting YouTube fetch...")

        while request:
            page_count += 1
            progress(0.1, desc=f"Fetching page {page_count}...")
            response = request.execute()

            for item in response.get('items', []):
                if len(comments_data) >= MAX_COMMENTS: break

                top_comment = item['snippet']['topLevelComment']['snippet']
                comments_data.append({
                    'Type': 'Top Level',
                    'Author': top_comment.get('authorDisplayName'),
                    'Text': top_comment.get('textDisplay'),
                    'Likes': top_comment.get('likeCount'),
                    'Published At': top_comment.get('publishedAt')
                })

                if 'replies' in item and len(comments_data) < MAX_COMMENTS:
                    for reply in item['replies']['comments']:
                        if len(comments_data) >= MAX_COMMENTS: break
                        reply_snip = reply['snippet']
                        comments_data.append({
                            'Type': 'Reply',
                            'Author': reply_snip.get('authorDisplayName'),
                            'Text': reply_snip.get('textDisplay'),
                            'Likes': reply_snip.get('likeCount'),
                            'Published At': reply_snip.get('publishedAt')
                        })

            if len(comments_data) >= MAX_COMMENTS: break
            if 'nextPageToken' in response:
                request = youtube.commentThreads().list_next(request, response)
            else:
                break

        if not comments_data:
            return pd.DataFrame(), None, "No comments found."

        df = pd.DataFrame(comments_data).head(MAX_COMMENTS)
        csv_filename = "youtube_comments.csv"
        df.to_csv(csv_filename, index=False)
        return df, csv_filename, f"Success! Fetched {len(df)} comments."

    except Exception as e:
        return pd.DataFrame(), None, f"Error: {str(e)}"

# --- FUNCTION 2: NEWSAPI LOGIC ---
def fetch_iphone_news(progress=gr.Progress()):
    """Fetches 5+ articles about iPhone from NewsAPI."""
    news_data = []

    try:
        progress(0, desc="Connecting to NewsAPI...")

        # Endpoint for "Everything"
        url = "https://newsapi.org/v2/everything"

        params = {
            'q': 'iphone',           # Topic
            'language': 'en',        # Language
            'sortBy': 'publishedAt', # Sort by newest
            'pageSize': 10,          # Get 10 to ensure we have 5+
            'apiKey': NEWS_API_KEY
        }

        response = requests.get(url, params=params)
        data = response.json()

        if response.status_code != 200:
            raise ValueError(f"API Error: {data.get('message', 'Unknown error')}")

        articles = data.get('articles', [])

        if not articles:
            return pd.DataFrame(), None, "No articles found."

        for article in articles:
            news_data.append({
                'Source': article['source']['name'],
                'Title': article['title'],
                'Published At': article['publishedAt'],
                'Description': article['description'],
                'URL': article['url']
            })

        df = pd.DataFrame(news_data)
        csv_filename = "iphone_news.csv"
        df.to_csv(csv_filename, index=False)

        return df, csv_filename, f"Success! Fetched {len(df)} articles about iPhone."

    except Exception as e:
        return pd.DataFrame(), None, f"Error: {str(e)}"

# --- GRADIO INTERFACE ---
with gr.Blocks(title="Data Scraper Suite") as demo:
    gr.Markdown("## 🕵️‍♂️ Data Scraper Suite")

    with gr.Tabs():
        # TAB 1: YOUTUBE
        with gr.TabItem("📺 YouTube Comments"):
            gr.Markdown("Select a video to fetch 120 comments.")

            # UPDATED: Changed back to Dropdown
            yt_dropdown = gr.Dropdown(
                choices=VIDEO_CHOICES,
                label="Select Video",
                value=VIDEO_CHOICES[0][1]
            )

            yt_btn = gr.Button("Fetch Comments", variant="primary")
            yt_status = gr.Textbox(label="Status", interactive=False)
            with gr.Row():
                yt_df = gr.Dataframe(label="Comments", wrap=True, interactive=False)
                yt_file = gr.File(label="Download CSV")

            yt_btn.click(
                fn=fetch_youtube_comments,
                inputs=[yt_dropdown],
                outputs=[yt_df, yt_file, yt_status]
            )

        # TAB 2: NEWS
        with gr.TabItem("📰 iPhone News"):
            gr.Markdown("Fetch the latest news articles about **iPhone**.")
            news_btn = gr.Button("Fetch iPhone News", variant="primary")
            news_status = gr.Textbox(label="Status", interactive=False)
            with gr.Row():
                news_df = gr.Dataframe(label="News Articles", wrap=True, interactive=False)
                news_file = gr.File(label="Download CSV")

            news_btn.click(
                fn=fetch_iphone_news,
                inputs=[],
                outputs=[news_df, news_file, news_status]
            )

demo.launch(debug=True)

!pip install -q gradio pandas supabase plotly vaderSentiment

import gradio as gr
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- 1. CONFIGURATION ---
SUPABASE_URL = "YOUR_SUPABASE_PROJECT_URL"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_KEY"

# Initialize Tools
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    analyzer = SentimentIntensityAnalyzer()
except Exception as e:
    print(f"⚠️ Init Error: {e}")

# --- 2. LOGIC ---
def refresh_dashboard():
    try:
        # 1. Fetch Data
        response = supabase.table("comments").select("*").execute()
        data = response.data
        
        if not data:
            return None, pd.DataFrame(), pd.DataFrame(), "⚠️ Table is empty."

        df = pd.DataFrame(data)
        
        # 2. FIX MISSING SCORES (Self-Healing)
        def fix_score(row):
            current_score = row.get('sentiment_score')
            text = str(row.get('text', ''))
            if pd.isna(current_score) or current_score == "":
                return analyzer.polarity_scores(text)['compound']
            return current_score

        df['sentiment_score'] = df.apply(fix_score, axis=1)
        df['sentiment_score'] = pd.to_numeric(df['sentiment_score'], errors='coerce')

        # 3. Create Labels
        def get_label(score):
            if pd.isna(score): return "Neutral"
            if score >= 0.05: return "Positive"
            elif score <= -0.05: return "Negative"
            else: return "Neutral"
        
        df['sentiment_label'] = df['sentiment_score'].apply(get_label)

        # 4. Handle Timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        
        # --- CHART ---
        if df['timestamp'].notna().sum() > 0:
            x_axis = "timestamp"
            title = "Sentiment Trends Over Time"
        else:
            x_axis = df.index
            title = "Sentiment Distribution (Dates Missing)"

        fig = px.scatter(
            df, 
            x=x_axis, 
            y="sentiment_score", 
            color="sentiment_label",
            hover_data=["text", "author"],
            title=title,
            color_discrete_map={"Positive": "green", "Negative": "red", "Neutral": "gray"}
        )

        # --- DRILL DOWN (SAME COLUMNS FOR BOTH) ---
        # We define the columns exactly once so they are identical
        display_cols = ['text', 'author', 'sentiment_score', 'sentiment_label']
        
        df_sorted = df.sort_values(by="sentiment_score", ascending=False)
        
        # Top 2 Positive (Head of list)
        top_pos = df_sorted.head(2)[display_cols]
        
        # Top 2 Negative (Tail of list)
        top_neg = df_sorted.tail(2)[display_cols]

        return fig, top_pos, top_neg, f"✅ Fixed & Loaded {len(df)} comments!"

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, pd.DataFrame(), pd.DataFrame(), f"❌ Error: {str(e)}"

# --- 3. UI ---
with gr.Blocks(title="Market Pulse Portal", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 💓 Market Pulse Engine")
    
    with gr.Row():
        refresh_btn = gr.Button("🔄 Sync & Fix Data", variant="primary")
        status_box = gr.Textbox(label="Status", interactive=False)
    
    with gr.Tabs():
        with gr.TabItem("Chart"):
            pulse_chart = gr.Plot()
        with gr.TabItem("Reviews"):
            # Explicitly setting headers to match the 'display_cols' list
            gr.Markdown("### 🌟 Top Positive")
            pos_out = gr.Dataframe(headers=["Comment", "Author", "Score", "Label"], wrap=True)
            
            gr.Markdown("### 🔻 Top Negative")
            neg_out = gr.Dataframe(headers=["Comment", "Author", "Score", "Label"], wrap=True)

    refresh_btn.click(fn=refresh_dashboard, inputs=[], outputs=[pulse_chart, pos_out, neg_out, status_box])

app.launch()
