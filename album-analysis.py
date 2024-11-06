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

st.set_page_config(layout="wide", page_title="1001 Albums Analysis")

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

def extract_album_data(html_content: str) -> List[Dict]:
    """Extract album data from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    albums = []

    # Find the rated albums section
    rated_albums_header = soup.find('h2', string='Rated Albums')
    if not rated_albums_header:
        st.error("Could not find Rated Albums section")
        return albums

    # Find the table after the header
    table = rated_albums_header.find_next('table')
    if not table:
        st.error("Could not find albums table")
        return albums

    for row in table.find_all('tr')[1:]:  # Skip header row
        try:
            cells = row.find_all('td')
            if len(cells) < 4:
                continue

            # Extract album name and Spotify URL
            album_link = cells[0].find('a', {'class': 'link--no-style'})
            album_name = album_link.get_text(strip=True) if album_link else "Unknown Album"
            spotify_url = album_link.get('href', '') if album_link else ""

            artist = cells[1].get_text(strip=True)
            
            # Extract rating
            rating_div = row.find('div', {'id': lambda x: x and x.startswith('group-stats--listened-albums--rating')})
            rating = float(rating_div.get_text(strip=True)) if rating_div else 0
            
            # Extract votes
            votes = int(cells[3].get_text(strip=True))
            
            # Extract date
            date = parse_date(cells[4].get_text(strip=True))
            
            # Extract details link
            details_link = row.find('a', string='Details')
            details_url = details_link.get('href', '') if details_link else ""

            album_data = {
                'album': album_name,
                'artist': artist,
                'rating': rating,
                'votes': votes,
                'date': date,
                'spotify_url': spotify_url,
                'details_url': details_url
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
    
    # Calculate controversialness (standard deviation of ratings)
    df['controversialness'] = df.groupby('album')['rating'].transform('std').fillna(0)
    
    return df

def scrape_albums(url: str) -> pd.DataFrame:
    """Scrape and process albums from URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        albums = extract_album_data(response.text)
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
    
    # Load data button
    if st.sidebar.button("Load/Refresh Data"):
        with st.spinner("Fetching album data..."):
            df = scrape_albums(url)
            st.session_state.df = df
            st.session_state.last_update = datetime.now()
    
    # Filter controls
    st.sidebar.header("Filters")
    min_rating = st.sidebar.slider("Minimum Rating", 0.0, 5.0, 0.0, 0.5)
    min_votes = st.sidebar.slider("Minimum Votes", 0, 10, 0)
    
    # Check if data is loaded
    if 'df' not in st.session_state:
        st.info("Click 'Load/Refresh Data' to start")
        return
        
    df = st.session_state.df
    
    # Apply filters
    filtered_df = df[
        (df['rating'] >= min_rating) &
        (df['votes'] >= min_votes)
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
    
    # Tables
    st.header("Album Rankings")
    tabs = st.tabs(["By Rating", "By Date", "By Votes", "Most Controversial"])
    
    with tabs[0]:
        st.dataframe(
            filtered_df.sort_values('rating', ascending=False)[['album', 'artist', 'rating', 'votes', 'date']]
        )
    
    with tabs[1]:
        st.dataframe(
            filtered_df.sort_values('date', ascending=False)[['album', 'artist', 'rating', 'votes', 'date']]
        )
    
    with tabs[2]:
        st.dataframe(
            filtered_df.sort_values('votes', ascending=False)[['album', 'artist', 'rating', 'votes', 'date']]
        )
    
    with tabs[3]:
        st.dataframe(
            filtered_df.sort_values('controversialness', ascending=False)[
                ['album', 'artist', 'rating', 'votes', 'controversialness', 'date']
            ]
        )
    
    # Artist Analysis
    st.header("Artist Analysis")
    artist_stats = filtered_df.groupby('artist').agg({
        'album': 'count',
        'rating': 'mean',
        'votes': 'sum'
    }).round(2).sort_values('album', ascending=False)
    
    st.dataframe(artist_stats)

if __name__ == "__main__":
    main()