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

SCORE_ORDER = ["Cleanliness", "Communication", "Location", "Value"]
ROOM_TYPE_ORDER = ["Entire home/apt", "Private room", "Shared room", "Hotel room"]
BAR_TYPE_ORDER = ["Total Listings", "Estimated Occupied Listings"]

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

    data = data.dropna(subset=["neighbourhood_cleansed", "room_type"])

    numeric_columns = [
        "availability_365",
        "hosts_time_as_user_years",
        "estimated_occupancy_l365d",
        "number_of_reviews"
    ] + REVIEW_COLUMNS

    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    data["availability_365"] = data["availability_365"].clip(0, 365)

    return data


def check_columns(data):
    # Check columns
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in data.columns]

    if missing_columns:
        st.error("Missing required columns: " + ", ".join(missing_columns))
        st.stop()


def add_host_tenure_group(data):
    # Host tenure groups
    data = data.copy()

    data["host_tenure_group"] = pd.cut(
        data["hosts_time_as_user_years"],
        bins=[-1, 2, 5, 100],
        labels=HOST_TENURE_ORDER,
        right=False
    )

    return data.dropna(subset=["host_tenure_group"])


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
        filtered = filtered[filtered["host_is_superhost"] == "t"]

    if host_type == "Non-superhosts only":
        filtered = filtered[filtered["host_is_superhost"] == "f"]

    return filtered


def make_score_tenure_chart(data):
    # Review score chart
    chart_data = data.dropna(subset=["hosts_time_as_user_years"] + REVIEW_COLUMNS).copy()

    if chart_data.empty:
        return None

    chart_data = add_host_tenure_group(chart_data)

    chart_data = chart_data.melt(
        id_vars=["host_tenure_group"],
        value_vars=REVIEW_COLUMNS,
        var_name="score_type",
        value_name="score"
    )

    chart_data["score_type_clean"] = chart_data["score_type"].map(SCORE_LABELS)

    chart_data = chart_data.dropna(
        subset=["host_tenure_group", "score_type_clean", "score"]
    )

    chart_data = chart_data.groupby(
        ["host_tenure_group", "score_type_clean"],
        observed=False,
        as_index=False
    ).agg(
        average_score=("score", "mean"),
        listings=("score", "count")
    )

    chart_data = chart_data[chart_data["listings"] > 0]

    if chart_data.empty:
        return None

    host_legend = alt.selection_point(
        fields=["host_tenure_group"],
        bind="legend",
        empty=True,
        name="HostTenure"
    )

    chart = alt.Chart(chart_data).mark_bar(size=24).encode(
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
            scale=alt.Scale(domain=[4, 5])
        ),
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
            alt.value(0.12)
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
        height=420
    )

    return chart


def make_room_type_chart(data):
    # Neighborhood brushing chart
    neighborhood_counts = data.groupby(
        "neighbourhood_cleansed",
        as_index=False
    ).size().rename(columns={"size": "listings"})

    availability_by_room = data.groupby(
        ["neighbourhood_cleansed", "room_type"],
        as_index=False
    ).agg(
        average_availability=("availability_365", "mean"),
        listings=("room_type", "count")
    )

    neighborhood_brush = alt.selection_interval(
        encodings=["y"],
        empty=True,
        name="NeighborhoodBrush"
    )

    room_legend = alt.selection_point(
        fields=["room_type"],
        bind="legend",
        empty=True,
        name="RoomType"
    )

    neighborhood_chart = alt.Chart(neighborhood_counts).mark_bar().encode(
        x=alt.X(
            "listings:Q",
            title="Number of Listings"
        ),
        y=alt.Y(
            "neighbourhood_cleansed:N",
            sort=alt.EncodingSortField(
                field="listings",
                order="descending"
            ),
            title="Neighborhood"
        ),
        color=alt.condition(
            neighborhood_brush,
            alt.value("#333333"),
            alt.value("#d9d9d9")
        ),
        tooltip=[
            alt.Tooltip("neighbourhood_cleansed:N", title="Neighborhood"),
            alt.Tooltip("listings:Q", title="Listings")
        ]
    ).add_params(
        neighborhood_brush
    ).properties(
        title="Brush Neighborhoods",
        width=390,
        height=520
    )

    room_chart = alt.Chart(availability_by_room).mark_bar().encode(
        x=alt.X(
            "room_type:N",
            title="Room Type",
            sort=ROOM_TYPE_ORDER,
            axis=alt.Axis(labelAngle=0)
        ),
        y=alt.Y(
            "average_availability:Q",
            title="Average Days Available"
        ),
        color=alt.Color(
            "room_type:N",
            title="Room Type",
            sort=ROOM_TYPE_ORDER,
            legend=alt.Legend(
                orient="bottom",
                labelLimit=0,
                titleLimit=0
            )
        ),
        opacity=alt.condition(
            room_legend,
            alt.value(1),
            alt.value(0.12)
        ),
        tooltip=[
            alt.Tooltip("neighbourhood_cleansed:N", title="Neighborhood"),
            alt.Tooltip("room_type:N", title="Room Type"),
            alt.Tooltip(
                "average_availability:Q",
                title="Average Days Available",
                format=".1f"
            ),
            alt.Tooltip("listings:Q", title="Listings")
        ]
    ).add_params(
        room_legend
    ).transform_filter(
        neighborhood_brush
    ).properties(
        title="Average Days Available by Room Type for Brushed Neighborhoods",
        width=560,
        height=380
    )

    return neighborhood_chart | room_chart


def make_occupancy_chart(data):
    # Estimated occupancy chart
    occupancy = data.groupby(
        "neighbourhood_cleansed",
        as_index=False
    ).agg(
        total_listings=("neighbourhood_cleansed", "count"),
        occupied_days=("estimated_occupancy_l365d", "sum")
    )

    occupancy["avg_daily_occupied_listings"] = occupancy["occupied_days"] / 365

    occupancy_long = occupancy.melt(
        id_vars=[
            "neighbourhood_cleansed",
            "total_listings",
            "avg_daily_occupied_listings"
        ],
        value_vars=[
            "total_listings",
            "avg_daily_occupied_listings"
        ],
        var_name="bar_type_raw",
        value_name="listing_count"
    )

    occupancy_long["bar_type"] = occupancy_long["bar_type_raw"].replace(
        {
            "total_listings": "Total Listings",
            "avg_daily_occupied_listings": "Estimated Occupied Listings"
        }
    )

    bar_legend = alt.selection_point(
        fields=["bar_type"],
        bind="legend",
        empty=True,
        name="BarType"
    )

    chart = alt.Chart(occupancy_long).mark_bar().encode(
        x=alt.X(
            "listing_count:Q",
            title="Number of Listings",
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
            alt.value(0.12)
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
        width=850,
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
        labelFontSize=12,
        titleFontSize=14
    ).configure_title(
        fontSize=18
    ).configure_legend(
        labelFontSize=12,
        titleFontSize=14,
        symbolSize=150
    )


def main():
    # Dashboard title
    st.title("Boston Airbnb Listings Dashboard")

    st.markdown(
        "This dashboard looks at how Boston Airbnb listings differ by host experience, "
        "room type, availability, and neighborhood activity. The main thing to watch is "
        "whether neighborhoods with more listings also have stronger estimated occupancy."
    )

    data = load_data()
    check_columns(data)

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
            use_container_width=True
        )

    st.divider()

    st.subheader("2. Availability by room type")
    st.markdown(
        "Brush across one or more neighborhoods on the left to compare room type availability on the right. "
        "Click a room type in the legend to focus the chart."
    )

    st.altair_chart(
        style_chart(make_room_type_chart(filtered_data)),
        use_container_width=True
    )

    st.divider()

    st.subheader("3. Listings compared with estimated occupancy")
    st.markdown(
        "The gray bar shows total listings, while the blue bar estimates how many listings are occupied on an average day. "
        "Click the legend to focus on one bar type."
    )

    st.altair_chart(
        style_chart(make_occupancy_chart(filtered_data)),
        use_container_width=True
    )

    st.caption("Source: Boston Airbnb listings loaded from Google Drive.")


if __name__ == "__main__":
    main()
