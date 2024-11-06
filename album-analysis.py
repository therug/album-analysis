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
            # Extract controversy value from tr element
            controversy = float(row.get('data-controversial', 0))
            
            cells = row.find_all('td')
            if len(cells) < 4:
                continue

            # Extract album name and Spotify URL
            album_link = cells[0].find('a', {'class': 'link--no-style'})
            album_name = album_link.get_text(strip=True) if album_link else "Unknown Album"
            spotify_url = album_link.get('href', '') if album_link else ""

            artist = cells[1].get_text(strip=True)
            
            # Extract rating
            rating_div = cells[2].find('div', {'id': 'group-stats--listened-albums--rating'})
            rating = float(rating_div.get_text(strip=True)) if rating_div else 0
            
            # Extract votes
            votes = int(cells[3].get_text(strip=True))
            
            # Extract date
            date_td = row.find('td', {'id': 'group-stats--listened-albums--date'})
            date = parse_date(date_td.get_text(strip=True)) if date_td else None
            
            # Extract details link
            details_link = cells[2].find('a')
            details_url = details_link.get('href', '') if details_link else ""

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
    
    # Album Rankings with AgGrid
    st.header("Album Rankings")
    
    # Configure grid options
    gb = GridOptionsBuilder.from_dataframe(
        filtered_df[[
            'album', 'artist', 'rating', 'votes', 
            'controversy', 'date'
        ]]
    )
    
    # Enable multi-column sort
    gb.configure_default_column(sorteable=True)
    
    # Configure column properties
    gb.configure_column("rating", type=["numericColumn", "numberColumnFilter"])
    gb.configure_column("votes", type=["numericColumn", "numberColumnFilter"])
    gb.configure_column("controversy", type=["numericColumn", "numberColumnFilter"])
    gb.configure_column("date", type=["dateColumn", "dateColumnFilter"])
    
    # Enable multi-sorting with shift+click
    gb.configure_grid_options(enableMultiRowSelection=False, multiSortKey='shift')
    
    gridOptions = gb.build()
    
    # Display the grid
    grid_response = AgGrid(
        filtered_df[[
            'album', 'artist', 'rating', 'votes', 
            'controversy', 'date'
        ]],
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True,
        theme='streamlit'
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