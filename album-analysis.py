import streamlit as st
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict
import altair as alt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# Configure the page
st.set_page_config(layout="wide", page_title="1001 Albums Analysis")

def get_spotify_urls(url: str) -> tuple:
    """Convert Spotify URL/URI to both web and app formats."""
    if not url or pd.isna(url):
        return "", ""
        
    # Extract the album ID regardless of format
    if url.startswith('spotify:album:'):
        album_id = url.split(':')[-1]
    elif 'open.spotify.com' in url:
        album_id = url.split('/')[-1].split('?')[0]
    else:
        return "", ""
        
    web_url = f'https://open.spotify.com/album/{album_id}'
    app_url = f'spotify:album:{album_id}'
    
    return web_url, app_url

def make_spotify_buttons(url):
    """Create both web and app buttons for Spotify."""
    web_url, app_url = get_spotify_urls(url)
    if not web_url or not app_url:
        return ""
        
    buttons = (
        f'<a href="{app_url}" target="_blank" style="text-decoration: none; margin-right: 8px;">'
        f'<span style="background-color: #1DB954; color: white; padding: 4px 8px; border-radius: 4px;">'
        f'🎵 Spotify App</span></a>'
        f'<a href="{web_url}" target="_blank" style="text-decoration: none;">'
        f'<span style="background-color: #1DB954; color: white; padding: 4px 8px; border-radius: 4px;">'
        f'🌐 Spotify Web</span></a>'
    )
    return buttons

def make_details_button(url):
    """Create a button for album details."""
    if pd.isna(url) or not url:
        return ""
    return (
        f'<a href="{url}" target="_blank" style="text-decoration: none;">'
        f'<span style="background-color: #FF4B4B; color: white; padding: 4px 8px; border-radius: 4px;">'
        f'📝 View</span></a>'
    )
# Add this after your imports
def fetch_album_details(url: str) -> Dict:
    """Fetch and parse album details from the given URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract relevant details
        details = {}
        
        # Get review text if it exists
        review_div = soup.find('div', class_='review')
        if review_div:
            details['review'] = review_div.get_text(strip=True)
            
        # Get individual ratings/comments
        ratings = []
        comments_section = soup.find('div', class_='comments')
        if comments_section:
            for comment in comments_section.find_all('div', class_='comment'):
                user = comment.find('span', class_='user').get_text(strip=True) if comment.find('span', class_='user') else 'Anonymous'
                rating = comment.find('span', class_='rating').get_text(strip=True) if comment.find('span', class_='rating') else 'No rating'
                text = comment.find('div', class_='text').get_text(strip=True) if comment.find('div', class_='text') else ''
                ratings.append({
                    'user': user,
                    'rating': rating,
                    'comment': text
                })
        details['ratings'] = ratings
        
        return details
    except Exception as e:
        st.error(f"Error fetching album details: {e}")
        return None

def parse_date(date_str: str) -> datetime:
    """Convert various date string formats to datetime."""
    try:
        # Remove timezone info and try to parse
        date_str = date_str.split('GMT')[0].strip()
        return datetime.strptime(date_str, '%a %b %d %Y %H:%M:%S')
    except ValueError as e:
        st.error(f"Error parsing date: {date_str}")
        st.error(f"Error: {e}")
        return None
    
def extract_album_data(*, html_content: str, group_url: str) -> List[Dict]:
    """Extract album data from HTML content.
    
    Args:
        html_content: The HTML content to parse
        group_url: The URL of the group page
    """
    base_url = "https://1001albumsgenerator.com/groups/"
    soup = BeautifulSoup(html_content, 'html.parser')
    albums = []

    rated_albums_header = soup.find('h2', string='Rated Albums')
    if not rated_albums_header:
        st.error("Could not find Rated Albums section")
        return albums

    table = rated_albums_header.find_next('table')
    if not table:
        st.error("Could not find albums table")
        return albums

    # Extract group name from the input URL
    try:
        group_name = group_url.split('groups/')[-1].split('/')[0]
    except Exception as e:
        st.error(f"Error extracting group name from URL: {e}")
        return albums

    for row in table.find_all('tr')[1:]:  # Skip header row
        try:
            controversy = float(row.get('data-controversial', 0))
            
            cells = row.find_all('td')
            if len(cells) < 4:
                continue

            album_link = cells[0].find('a', {'class': 'link--no-style'})
            album_name = album_link.get_text(strip=True) if album_link else "Unknown Album"
            spotify_url = album_link.get('href', '') if album_link else ""

            artist = cells[1].get_text(strip=True)
            
            rating = 0
            rating_cell = cells[2]
            rating_div = rating_cell.find('div', {'id': lambda x: x and 'rating' in x.lower()})
            if rating_div:
                try:
                    rating = float(rating_div.get_text(strip=True))
                except (ValueError, TypeError):
                    pass
            if rating == 0:
                try:
                    rating_text = rating_cell.get_text(strip=True)
                    import re
                    numbers = re.findall(r'\d+\.?\d*', rating_text)
                    if numbers:
                        rating = float(numbers[0])
                except (ValueError, TypeError):
                    pass
            
            votes = int(cells[3].get_text(strip=True))
            
            date_td = row.find('td', {'id': 'group-stats--listened-albums--date'})
            date = parse_date(date_td.get_text(strip=True)) if date_td else None
            
            details_link = cells[2].find('a')
            details_path = details_link.get('href', '') if details_link else ""

            # Debug details URL construction
            if details_path:
                album_id = details_path.split('/')[-1]
                details_url = f"{base_url}{group_name}/albums/{album_id}"
            else:
                details_url = ""

            album_data = {
                'album': album_name,
                'artist': artist,
                'rating': rating,
                'votes': votes,
                'date': date,
                'spotify_url': spotify_url,
                'details_url': details_url,
                'controversy': controversy
            }
            
            albums.append(album_data)

        except Exception as e:
            st.error(f"Error processing row: {e}")
            continue

    return albums

def create_dataframe(albums: List[Dict]) -> pd.DataFrame:
    """Create and enhance DataFrame from album data."""
    df = pd.DataFrame(albums)
    
    # Add derived columns
    df['year'] = pd.to_datetime(df['date']).dt.year
    df['month'] = pd.to_datetime(df['date']).dt.month
    df['decade'] = (df['year'] // 10) * 10
    
    # Rename controversy to controversy for consistency
    df = df.rename(columns={'controversy': 'controversy'})
    
    return df

def scrape_albums(url: str) -> pd.DataFrame:
    """Scrape and process albums from URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text
        # Pass both required arguments
        albums = extract_album_data(html_content=html_content, group_url=url)
        return create_dataframe(albums)
    except Exception as e:
        st.error(f"Error scraping data: {e}")
        return pd.DataFrame()

def main():
    st.title("1001 Albums Generator Analysis")
    
    # Sidebar for controls
    st.sidebar.header("Controls")
    
    # URL Input
    url = st.sidebar.text_input(
        "Enter your 1001 Albums Generator group URL:",
        value="https://1001albumsgenerator.com/groups/pompey-pixel-pals",
        help="Enter the URL of your group's page"
    )
    
    # Auto-load data on first page load
    if 'df' not in st.session_state:
        with st.spinner("Fetching album data..."):
            df = scrape_albums(url)
            st.session_state.df = df
            st.session_state.last_update = datetime.now()
    
    # Load data button
    if st.sidebar.button("Load/Refresh Data"):
        with st.spinner("Fetching album data..."):
            df = scrape_albums(url)
            st.session_state.df = df
            st.session_state.last_update = datetime.now()
    
    # Check if data is loaded
    if 'df' not in st.session_state:
        st.info("Click 'Load/Refresh Data' to start")
        return
        
    df = st.session_state.df
        
    # Filter controls with dynamic ranges based on data
    st.sidebar.header("Filters")
    
    # Rating filter
    rating_min = float(df['rating'].min())
    rating_max = float(df['rating'].max())
    rating_range = st.sidebar.slider(
        "Rating Range",
        min_value=rating_min,
        max_value=rating_max,
        value=(rating_min, rating_max),
        step=0.5
    )
    
    # Votes filter
    votes_min = int(df['votes'].min())
    votes_max = int(df['votes'].max())
    votes_range = st.sidebar.slider(
        "Votes Range",
        min_value=votes_min,
        max_value=votes_max,
        value=(votes_min, votes_max),
        step=1
    )
    
    # Controversy filter
    controversy_min = float(df['controversy'].min())
    controversy_max = float(df['controversy'].max())
    controversy_range = st.sidebar.slider(
        "Controversy Range",
        min_value=controversy_min,
        max_value=controversy_max,
        value=(controversy_min, controversy_max),
        step=0.1
    )
    
    # Apply all filters
    filtered_df = df[
        (df['rating'].between(rating_range[0], rating_range[1])) &
        (df['votes'].between(votes_range[0], votes_range[1])) &
        (df['controversy'].between(controversy_range[0], controversy_range[1]))
    ]
    
    # Display last update time
    if 'last_update' in st.session_state:
        st.sidebar.text(f"Last updated: {st.session_state.last_update.strftime('%H:%M:%S')}")    
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Album Ratings Over Time")
        
        # Create time series chart
        chart = alt.Chart(filtered_df).mark_circle().encode(
            x='date:T',
            y='rating:Q',
            size='votes:Q',
            color='rating:Q',
            tooltip=['album', 'artist', 'rating', 'votes']
        ).interactive()
        
        st.altair_chart(chart, use_container_width=True)
        
    with col2:
        st.header("Rating Distribution")
        hist = alt.Chart(filtered_df).mark_bar().encode(
            x=alt.X('rating:Q', bin=True),
            y='count()',
        ).interactive()
        
        st.altair_chart(hist, use_container_width=True)
    
    # Statistics
    st.header("Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Albums", len(filtered_df))
    with col2:
        st.metric("Average Rating", f"{filtered_df['rating'].mean():.2f}")
    with col3:
        st.metric("Total Votes", filtered_df['votes'].sum())
    with col4:
        st.metric("Highest Rated", f"{filtered_df.nlargest(1, 'rating')['album'].iloc[0]}")
        
    # Album Rankings with Sorting Options
    st.header("Album Rankings")
    
    # Sorting controls
    sort_cols = ['album', 'artist', 'rating', 'votes', 'controversy', 'date']
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        primary_sort = st.selectbox(
            "Primary Sort",
            options=sort_cols,
            index=sort_cols.index('rating')
        )
    
    with col2:
        primary_ascending = st.selectbox(
            "Primary Direction",
            options=['Descending', 'Ascending'],
            index=0
        )
    
    with col3:
        secondary_sort = st.selectbox(
            "Secondary Sort",
            options=['None'] + sort_cols,
            index=0
        )
    
    with col4:
        secondary_ascending = st.selectbox(
            "Secondary Direction",
            options=['Descending', 'Ascending'],
            index=0
        )
    
    # Create a DataFrame with both display text and URLs
    display_df = filtered_df.copy()
    
    # Apply sorting
    if secondary_sort != 'None':
        display_df = display_df.sort_values(
            by=[primary_sort, secondary_sort],
            ascending=[
                primary_ascending == 'Ascending',
                secondary_ascending == 'Ascending'
            ]
        )
    else:
        display_df = display_df.sort_values(
            by=[primary_sort],
            ascending=[primary_ascending == 'Ascending']
        )
    
    # Create button columns
    display_df['spotify'] = display_df['spotify_url'].apply(make_spotify_buttons)
    display_df['details'] = display_df['details_url'].apply(make_details_button)
    
    # Convert date to formatted string
    display_df['date'] = pd.to_datetime(display_df['date']).dt.strftime('%Y-%m-%d')
    
    # Format numeric columns
    display_df['rating'] = display_df['rating'].round(1)
    display_df['controversy'] = display_df['controversy'].round(2)
    
    # Create the final display DataFrame with desired columns
    final_df = display_df[[
        'album', 'artist', 'rating', 'votes', 
        'controversy', 'date', 'spotify', 'details'
    ]]
    
    # Display the table with HTML
    st.write(
        final_df.to_html(
            escape=False,
            index=False,
            classes=[
                'dataframe', 
                'hover', 
                'stripe'
            ]
        ),
        unsafe_allow_html=True
    )
    
    # Add custom CSS for better table styling
    st.markdown(
        """
        <style>
        .dataframe {
            width: 100%;
            border-collapse: collapse;
        }
        .dataframe th {
            background-color: #f0f2f6;
            padding: 8px;
            text-align: left;
            border-bottom: 2px solid #ddd;
        }
        .dataframe td {
            padding: 8px;
            border-bottom: 1px solid #ddd;
        }
        .dataframe tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .dataframe tr:hover {
            background-color: #f5f5f5;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # Update instructions
    st.caption("Click 'Spotify App' to open in desktop app (if installed) or 'Spotify Web' to open in browser. Click 'View' to see album details.")
    
    # Create container for album details
    details_container = st.container()
    
    # Artist Analysis
    st.header("Artist Analysis")
    artist_stats = filtered_df.groupby('artist').agg({
        'album': 'count',
        'rating': 'mean',
        'votes': 'sum'
    }).round(2).sort_values('album', ascending=False)
    
    st.dataframe(artist_stats)

# End of main function
if __name__ == "__main__":
    main()