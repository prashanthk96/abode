import re
import pandas as pd
import streamlit as st
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import requests
import random
import math

# Load temple data from Excel
@st.cache_data
def load_temple_data():
    return pd.read_excel("Thanjavur_Temples.xlsx")

temple_data = load_temple_data()

# Caching the distance matrix calculation for performance
@st.cache_data
def compute_distance_matrix(locations):    
    num_locations = len(locations)
    distance_matrix = [[0] * num_locations for i in range(num_locations)]
    for i in range(num_locations):
        for j in range(i, num_locations):
            distance = geodesic(locations[i], locations[j]).km
            distance_matrix[i][j] = distance
            distance_matrix[j][i] = distance
    return distance_matrix

def create_data_model(locations):
    data = {}
    num_locations = len(locations)
    data['locations'] = locations
    data['num_locations'] = num_locations
    data['distance_matrix'] = compute_distance_matrix(locations)
    return data

def tsp_solver(data_model, iterations=1000, temperature=10000, cooling_rate=0.95):
    def distance(point1, point2):
        return geodesic(point1, point2).km

    num_locations = data_model['num_locations']
    locations = data_model['locations']

    # Generate a starting solution
    current_solution = list(range(num_locations))
    random.shuffle(current_solution)

    # Compute distance of the starting solution
    current_distance = sum(distance(locations[current_solution[i - 1]], locations[current_solution[i]])
                           for i in range(num_locations))

    # Initialize best solution
    best_solution = current_solution[:]
    best_distance = current_distance

    for i in range(iterations):
        current_temperature = temperature * (cooling_rate ** i)

        # Generate a new solution by swapping two locations
        new_solution = current_solution[:]
        j, k = random.sample(range(num_locations), 2)
        new_solution[j], new_solution[k] = new_solution[k], new_solution[j]

        # Calculate new distance
        new_distance = sum(distance(locations[new_solution[i - 1]], locations[new_solution[i]])
                           for i in range(num_locations))

        delta = new_distance - current_distance
        if delta < 0 or random.random() < math.exp(-delta / current_temperature):
            current_solution = new_solution
            current_distance = new_distance

        if current_distance < best_distance:
            best_solution = current_solution[:]
            best_distance = current_distance

    # Create optimal route
    location_route = [locations[i] for i in best_solution]
    return location_route

def display_route(location_route, loc_df):
    rows = []
    distance_total = 0
    google_maps_url = "https://www.google.com/maps/dir/"
    
    for i, loc in enumerate(location_route[:-1]):
        next_loc = location_route[i + 1]
        distance = geodesic(loc, next_loc).kilometers
        distance_km_text = f"{distance:.2f} km"
        distance_total += distance

        a = loc_df.loc[loc_df['Coordinates'] == loc, 'Temple Name'].values[0]
        b = loc_df.loc[loc_df['Coordinates'] == next_loc, 'Temple Name'].values[0]
        rows.append((a, b, distance_km_text))
        
        # Add coordinates to the Google Maps URL in the required format
        google_maps_url += f"{loc[0]},{loc[1]}/"

    # Add final location to close the route
    google_maps_url += f"{location_route[-1][0]},{location_route[-1][1]}"

    # Display the route in a table
    df = pd.DataFrame(rows, columns=["From", "To", "Distance (km)"])
    st.write("### Route Details")
    st.dataframe(df)
    st.metric("Total Distance (km)", f"{distance_total:.2f}")

    # Display the Google Maps Link
    st.write("\n")
    st.write("### View Route on Google Maps")
    st.markdown(f"[Click here to view the route on Google Maps]({google_maps_url})")

    # Map display
    m = folium.Map(location=[location_route[0][0], location_route[0][1]], zoom_start=12)
    for loc in location_route:
        place_name = loc_df.loc[loc_df['Coordinates'] == loc, 'Temple Name'].values[0]
        folium.Marker(location=loc, popup=place_name).add_to(m)
    st_folium(m, width=700, height=500)

def main():
    st.title("Abode - Temple Trip Planner")
    
    # Sidebar filters
    st.sidebar.header("Filter Temples")
    selected_diety = st.sidebar.multiselect("Main Deity", options=temple_data["Main Deity"].unique(), default=temple_data["Main Deity"].unique())
    selected_highlight = st.sidebar.text_input("Search Highlights")

    # Apply filters
    filtered_data = temple_data[(temple_data["Main Deity"].isin(selected_diety))]
    if selected_highlight:
        filtered_data = filtered_data[filtered_data["Highlights"].str.contains(selected_highlight, case=False, na=False)]

    st.write("### Selected Temples", filtered_data)

    # Select temples for trip
    st.write("### Trip Planner")
    selected_temples = st.multiselect("Choose Temples for Route", options=filtered_data["Temple Name"].tolist())
    if st.checkbox("Create Trip") and selected_temples:
        st.session_state.trip_created = True
        trip_data = filtered_data[filtered_data["Temple Name"].isin(selected_temples)]
        locations = [(row["Latitude"], row["Longitude"]) for _, row in trip_data.iterrows()]
        loc_df = trip_data.copy()
        loc_df['Coordinates'] = list(zip(loc_df['Latitude'], loc_df['Longitude']))

        # Optimize route
        data_model = create_data_model(locations)
        location_route = tsp_solver(data_model)
        display_route(location_route, loc_df)

if __name__ == "__main__":
    main()