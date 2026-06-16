import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(
    page_title="Boston Airbnb Dashboard",
    page_icon="🏙️",
    layout="wide"
)

alt.data_transformers.disable_max_rows()

FILE_ID = "1Q-bnOdbb5753U5FhSqWgCpmo-AsemeFW"
DATA_URL = f"https://drive.google.com/uc?export=download&id={FILE_ID}"
LOCAL_FILE = "listings.csv"

REVIEW_COLUMNS = [
    "review_scores_cleanliness",
    "review_scores_communication",
    "review_scores_location",
    "review_scores_value"
]

SCORE_LABELS = {
    "review_scores_cleanliness": "Cleanliness",
    "review_scores_communication": "Communication",
    "review_scores_location": "Location",
    "review_scores_value": "Value"
}

HOST_TENURE_ORDER = [
    "New Host (<2 years)",
    "Established Host (2-5 years)",
    "Veteran Host (5+ years)"
]

SCORE_ORDER = [
    "Cleanliness",
    "Communication",
    "Location",
    "Value"
]

BAR_TYPE_ORDER = [
    "Total Listings",
    "Estimated Occupied Listings"
]

REQUIRED_COLUMNS = [
    "neighbourhood_cleansed",
    "room_type",
    "availability_365",
    "hosts_time_as_user_years",
    "estimated_occupancy_l365d",
    "number_of_reviews",
    "host_is_superhost"
] + REVIEW_COLUMNS


@st.cache_data(show_spinner=False)
def load_data():
    # Load data
    try:
        data = pd.read_csv(DATA_URL)
    except Exception:
        data = pd.read_csv(LOCAL_FILE)

    return data


def check_columns(data):
    # Check columns
    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in data.columns
    ]

    if missing_columns:
        st.error("Missing required columns: " + ", ".join(missing_columns))
        st.stop()


def clean_data(data):
    # Clean data
    data = data.copy()

    data = data.dropna(
        subset=[
            "neighbourhood_cleansed",
            "room_type"
        ]
    )

    numeric_columns = [
        "availability_365",
        "hosts_time_as_user_years",
        "estimated_occupancy_l365d",
        "number_of_reviews"
    ] + REVIEW_COLUMNS

    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data["availability_365"] = data["availability_365"].clip(0, 365)

    data["host_is_superhost_clean"] = (
        data["host_is_superhost"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    return data


def apply_sidebar_filters(data):
    # Sidebar filters
    st.sidebar.header("Filters")

    room_types = sorted(data["room_type"].dropna().unique())

    selected_room_types = st.sidebar.multiselect(
        "Room type",
        room_types,
        default=room_types
    )

    neighborhoods = sorted(data["neighbourhood_cleansed"].dropna().unique())

    neighborhood_mode = st.sidebar.radio(
        "Neighborhoods",
        ["All neighborhoods", "Choose neighborhoods"]
    )

    if neighborhood_mode == "Choose neighborhoods":
        selected_neighborhoods = st.sidebar.multiselect(
            "Pick neighborhoods",
            neighborhoods,
            default=neighborhoods[:6]
        )
    else:
        selected_neighborhoods = neighborhoods

    host_type = st.sidebar.selectbox(
        "Host type",
        ["All hosts", "Superhosts only", "Non-superhosts only"]
    )

    days_available = st.sidebar.slider(
        "Days available",
        min_value=0,
        max_value=365,
        value=(0, 365)
    )

    max_reviews = int(data["number_of_reviews"].max())

    min_reviews = st.sidebar.slider(
        "Minimum number of reviews",
        min_value=0,
        max_value=max_reviews,
        value=0
    )

    filtered = data[
        data["room_type"].isin(selected_room_types)
        & data["neighbourhood_cleansed"].isin(selected_neighborhoods)
        & data["availability_365"].between(days_available[0], days_available[1])
        & (data["number_of_reviews"] >= min_reviews)
    ].copy()

    if host_type == "Superhosts only":
        filtered = filtered[
            filtered["host_is_superhost_clean"].isin(["t", "true", "1"])
        ]

    if host_type == "Non-superhosts only":
        filtered = filtered[
            filtered["host_is_superhost_clean"].isin(["f", "false", "0"])
        ]

    st.sidebar.caption(f"{len(filtered):,} listings after filters")

    return filtered


def make_score_tenure_chart(data):
    # Review score chart
    df_scores = data.dropna(
        subset=["hosts_time_as_user_years"] + REVIEW_COLUMNS
    ).copy()

    if df_scores.empty:
        return None

    df_scores.loc[
        df_scores["hosts_time_as_user_years"] < 2,
        "host_tenure_group"
    ] = "New Host (<2 years)"

    df_scores.loc[
        (df_scores["hosts_time_as_user_years"] >= 2)
        & (df_scores["hosts_time_as_user_years"] < 5),
        "host_tenure_group"
    ] = "Established Host (2-5 years)"

    df_scores.loc[
        df_scores["hosts_time_as_user_years"] >= 5,
        "host_tenure_group"
    ] = "Veteran Host (5+ years)"

    score_data = df_scores.melt(
        id_vars=["host_tenure_group"],
        value_vars=REVIEW_COLUMNS,
        var_name="score_type",
        value_name="score"
    )

    score_data["score_type_clean"] = score_data["score_type"].map(SCORE_LABELS)

    score_data = score_data.dropna(
        subset=[
            "host_tenure_group",
            "score_type_clean",
            "score"
        ]
    )

    if score_data.empty:
        return None

    score_summary = score_data.groupby(
        ["host_tenure_group", "score_type_clean"],
        as_index=False
    ).agg(
        average_score=("score", "mean"),
        listings=("score", "count")
    )

    score_summary = score_summary[score_summary["listings"] > 0].copy()

    if score_summary.empty:
        return None

    score_floor = min(4.5, score_summary["average_score"].min() - 0.05)
    score_floor = max(0, score_floor)

    score_summary["score_floor"] = score_floor

    host_legend = alt.selection_point(
        fields=["host_tenure_group"],
        bind="legend",
        empty=True,
        name="HostTenureSelect"
    )

    chart = alt.Chart(score_summary).mark_bar().encode(
        x=alt.X(
            "score_type_clean:N",
            title="Review Score Type",
            sort=SCORE_ORDER,
            axis=alt.Axis(labelAngle=0)
        ),
        xOffset=alt.XOffset(
            "host_tenure_group:N",
            sort=HOST_TENURE_ORDER
        ),
        y=alt.Y(
            "average_score:Q",
            title="Average Review Score",
            scale=alt.Scale(
                domain=[score_floor, 5],
                zero=False
            )
        ),
        y2=alt.Y2("score_floor:Q"),
        color=alt.Color(
            "host_tenure_group:N",
            title="Host Tenure",
            sort=HOST_TENURE_ORDER,
            scale=alt.Scale(
                domain=HOST_TENURE_ORDER,
                range=["#cfe8f3", "#73add1", "#2166ac"]
            ),
            legend=alt.Legend(
                orient="bottom",
                columns=1,
                labelLimit=0,
                titleLimit=0
            )
        ),
        opacity=alt.condition(
            host_legend,
            alt.value(1),
            alt.value(0.04)
        ),
        tooltip=[
            alt.Tooltip("score_type_clean:N", title="Score Type"),
            alt.Tooltip("host_tenure_group:N", title="Host Tenure"),
            alt.Tooltip("average_score:Q", title="Average Score", format=".2f"),
            alt.Tooltip("listings:Q", title="Listings")
        ]
    ).add_params(
        host_legend
    ).properties(
        title="Average Review Scores by Host Tenure",
        width=850,
        height=450
    )

    return chart


def make_room_type_chart(data):
    # Neighborhood brushing chart
    neighborhood_brush = alt.selection_interval(
        encodings=["y"],
        empty=True,
        name="NeighborhoodBrush"
    )

    room_legend = alt.selection_point(
        fields=["room_type"],
        bind="legend",
        empty=True,
        name="RoomTypeSelect"
    )

    neighborhood_filter = alt.Chart(data).mark_bar().encode(
        x=alt.X(
            "count():Q",
            title="Number of Listings"
        ),
        y=alt.Y(
            "neighbourhood_cleansed:N",
            sort="-x",
            title="Neighborhood"
        ),
        color=alt.condition(
            neighborhood_brush,
            alt.value("black"),
            alt.value("lightgray")
        ),
        tooltip=[
            alt.Tooltip("neighbourhood_cleansed:N", title="Neighborhood"),
            alt.Tooltip("count():Q", title="Listings")
        ]
    ).add_params(
        neighborhood_brush
    ).properties(
        title="Brush Neighborhoods",
        width=400,
        height=550
    )

    room_type_availability = alt.Chart(data).mark_bar().encode(
        x=alt.X(
            "room_type:N",
            title="Room Type",
            axis=alt.Axis(labelAngle=0)
        ),
        y=alt.Y(
            "mean(availability_365):Q",
            title="Average Days Available Per Year"
        ),
        color=alt.Color(
            "room_type:N",
            title="Room Type",
            legend=alt.Legend(
                orient="bottom",
                labelLimit=0,
                titleLimit=0
            )
        ),
        opacity=alt.condition(
            room_legend,
            alt.value(1),
            alt.value(0.04)
        ),
        tooltip=[
            alt.Tooltip("room_type:N", title="Room Type"),
            alt.Tooltip(
                "mean(availability_365):Q",
                title="Average Days Available",
                format=".1f"
            ),
            alt.Tooltip("count():Q", title="Listings")
        ]
    ).add_params(
        room_legend
    ).transform_filter(
        neighborhood_brush
    ).properties(
        title="Average Yearly Availability by Room Type for Brushed Neighborhoods",
        width=550,
        height=400
    )

    return neighborhood_filter | room_type_availability


def make_occupancy_chart(data):
    # Occupancy chart
    occupancy = data.groupby(
        "neighbourhood_cleansed",
        as_index=False
    ).agg(
        total_listings=("neighbourhood_cleansed", "size"),
        occupied_days=("estimated_occupancy_l365d", "sum")
    )

    occupancy["avg_daily_occupied_listings"] = occupancy["occupied_days"] / 365

    total_data = occupancy.copy()
    total_data["bar_type"] = "Total Listings"
    total_data["listing_count"] = total_data["total_listings"]
    total_data["bar_order"] = 0

    occupied_data = occupancy.copy()
    occupied_data["bar_type"] = "Estimated Occupied Listings"
    occupied_data["listing_count"] = occupied_data["avg_daily_occupied_listings"]
    occupied_data["bar_order"] = 1

    occupancy_long = pd.concat(
        [total_data, occupied_data],
        ignore_index=True
    )

    bar_legend = alt.selection_point(
        fields=["bar_type"],
        bind="legend",
        empty=True,
        name="BarTypeSelect"
    )

    chart = alt.Chart(occupancy_long).mark_bar().encode(
        x=alt.X(
            "listing_count:Q",
            title="Number of Listings",
            stack=None,
            axis=alt.Axis(labelAngle=-30)
        ),
        y=alt.Y(
            "neighbourhood_cleansed:N",
            sort=alt.EncodingSortField(
                field="total_listings",
                order="descending"
            ),
            title="Neighborhood"
        ),
        color=alt.Color(
            "bar_type:N",
            title="Bar Meaning",
            sort=BAR_TYPE_ORDER,
            scale=alt.Scale(
                domain=BAR_TYPE_ORDER,
                range=["lightgray", "steelblue"]
            ),
            legend=alt.Legend(
                orient="bottom",
                labelLimit=0,
                titleLimit=0,
                columns=2
            )
        ),
        opacity=alt.condition(
            bar_legend,
            alt.value(1),
            alt.value(0.04)
        ),
        order=alt.Order(
            "bar_order:Q",
            sort="ascending"
        ),
        tooltip=[
            alt.Tooltip("neighbourhood_cleansed:N", title="Neighborhood"),
            alt.Tooltip("bar_type:N", title="Bar Meaning"),
            alt.Tooltip("listing_count:Q", title="Listings", format=".1f"),
            alt.Tooltip("total_listings:Q", title="Total Listings"),
            alt.Tooltip(
                "avg_daily_occupied_listings:Q",
                title="Estimated Occupied Listings",
                format=".1f"
            )
        ]
    ).add_params(
        bar_legend
    ).properties(
        title="Total Listings vs. Estimated Occupied Listings by Neighborhood",
        width=800,
        height=600
    )

    return chart


def show_metrics(data):
    # Summary numbers
    col1, col2, col3, col4 = st.columns(4)

    listings = len(data)
    neighborhoods = data["neighbourhood_cleansed"].nunique()
    average_availability = data["availability_365"].mean()
    average_rating = data["review_scores_value"].mean()

    col1.metric("Listings", f"{listings:,}")
    col2.metric("Neighborhoods", f"{neighborhoods:,}")
    col3.metric("Avg. Days Available", f"{average_availability:.0f} days")
    col4.metric("Avg. Value Score", f"{average_rating:.2f}")


def style_chart(chart):
    # Chart styling
    return chart.configure_axis(
        labelFontSize=13,
        titleFontSize=15
    ).configure_title(
        fontSize=20
    ).configure_legend(
        labelFontSize=13,
        titleFontSize=15,
        symbolSize=160
    )


def main():
    # Dashboard title
    st.title("Boston Airbnb Listings Dashboard")

    st.markdown(
        "This dashboard looks at how Boston Airbnb listings differ by host experience, "
        "room type, availability, and neighborhood activity. The main pattern to watch is "
        "whether neighborhoods with more listings also have stronger estimated occupancy."
    )

    data = load_data()
    check_columns(data)
    data = clean_data(data)

    filtered_data = apply_sidebar_filters(data)

    if filtered_data.empty:
        st.warning("No listings match the current filters.")
        st.stop()

    show_metrics(filtered_data)

    st.divider()

    st.subheader("1. Host experience and review scores")
    st.markdown(
        "Review scores are clustered near the high end, so small differences can still matter. "
        "Click a host tenure group in the legend to focus on that group."
    )

    score_chart = make_score_tenure_chart(filtered_data)

    if score_chart is None:
        st.info("Not enough review score data for the selected filters.")
    else:
        st.altair_chart(
            style_chart(score_chart),
            width="stretch"
        )

    st.divider()

    st.subheader("2. Availability by room type")
    st.markdown(
        "Brush across one or more neighborhoods on the left to compare room type availability on the right. "
        "Click a room type in the legend to focus the chart."
    )

    st.altair_chart(
        style_chart(make_room_type_chart(filtered_data)),
        width="stretch"
    )

    st.divider()

    st.subheader("3. Listings compared with estimated occupancy")
    st.markdown(
        "The gray bar shows total listings, while the blue bar estimates how many listings are occupied on an average day. "
        "Click the legend to focus on one bar type."
    )

    st.altair_chart(
        style_chart(make_occupancy_chart(filtered_data)),
        width="stretch"
    )

    st.caption("Source: Boston Airbnb listings loaded from Google Drive.")


if __name__ == "__main__":
    main()
